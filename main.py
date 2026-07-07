import os
import asyncio
import json
import base64
import time
import datetime
import re
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from google import genai
from google.genai import types

# 로컬 실행 시 .env 파일에서 환경변수를 읽어온다. (배포 환경에서는 호스팅
# 플랫폼이 환경변수를 직접 주입하므로 .env 파일이 없어도 문제 없음)
load_dotenv()

# 배포 확인용 버전 — 화면 좌측 상태줄과 서버 로그에 표시됨
APP_VERSION = "v8"

app = FastAPI()
templates = Jinja2Templates(directory="templates")
print(f"[서버] 마사마사 서버 시작 — 버전 {APP_VERSION}")

# 햄스터 이미지 등 정적 파일 서빙
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일 또는 호스팅 환경변수를 확인하세요.")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ============================================================
# 공개 배포 시 비용 남용 방지 장치
# - MAX_CONCURRENT_SESSIONS: 동시 접속 가능한 대화 세션 수 제한
# ============================================================
MAX_CONCURRENT_SESSIONS = int(os.environ.get("MAX_CONCURRENT_SESSIONS", "5"))
_active_sessions = 0
_session_lock = asyncio.Lock()

# ============================================================
# 대화 녹음 업로드 → Google Drive 저장
# - Render 디스크는 ephemeral(재배포/재시작 시 삭제)이라 외부 저장소 필요
# - 개인 구글 계정 OAuth(리프레시 토큰) 방식 사용
#   ※ 서비스 계정은 2025년부터 My Drive에 파일 소유 불가(용량 0)라 사용 불가
# - 설정 방법: GDRIVE_SETUP.md 참고
# - 환경변수 미설정 시 서버 로컬 recordings/ 폴더에 저장 (임시 — 재배포 시 삭제)
# ============================================================
GDRIVE_CLIENT_ID = os.environ.get("GDRIVE_CLIENT_ID", "").strip()
GDRIVE_CLIENT_SECRET = os.environ.get("GDRIVE_CLIENT_SECRET", "").strip()
GDRIVE_REFRESH_TOKEN = os.environ.get("GDRIVE_REFRESH_TOKEN", "").strip()
GDRIVE_FOLDER_NAME = os.environ.get("GDRIVE_FOLDER_NAME", "masamasa-recordings").strip()
GDRIVE_ENABLED = bool(GDRIVE_CLIENT_ID and GDRIVE_CLIENT_SECRET and GDRIVE_REFRESH_TOKEN)
MAX_UPLOAD_BYTES = 60 * 1024 * 1024  # 60MB

_gdrive_token = {"access_token": None, "expires_at": 0.0}
_gdrive_folder = {"id": None}


def _gdrive_get_access_token() -> str:
    """리프레시 토큰으로 액세스 토큰 발급 (만료 60초 전까지 캐시). 동기 — to_thread에서 호출."""
    import requests
    if _gdrive_token["access_token"] and time.time() < _gdrive_token["expires_at"] - 60:
        return _gdrive_token["access_token"]
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GDRIVE_CLIENT_ID,
        "client_secret": GDRIVE_CLIENT_SECRET,
        "refresh_token": GDRIVE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    tok = r.json()
    _gdrive_token["access_token"] = tok["access_token"]
    _gdrive_token["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    return _gdrive_token["access_token"]


def _gdrive_get_folder_id(token: str) -> str:
    """녹음 저장 폴더를 찾고, 없으면 만든다 (drive.file 스코프: 이 앱이 만든 파일만 접근)."""
    import requests
    if _gdrive_folder["id"]:
        return _gdrive_folder["id"]
    headers = {"Authorization": f"Bearer {token}"}
    q = (f"name = '{GDRIVE_FOLDER_NAME}' and "
         "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    r = requests.get("https://www.googleapis.com/drive/v3/files",
                     params={"q": q, "fields": "files(id)"}, headers=headers, timeout=30)
    r.raise_for_status()
    files = r.json().get("files", [])
    if files:
        _gdrive_folder["id"] = files[0]["id"]
    else:
        r = requests.post("https://www.googleapis.com/drive/v3/files",
                          json={"name": GDRIVE_FOLDER_NAME,
                                "mimeType": "application/vnd.google-apps.folder"},
                          headers=headers, timeout=30)
        r.raise_for_status()
        _gdrive_folder["id"] = r.json()["id"]
        print(f"[녹음] Google Drive에 '{GDRIVE_FOLDER_NAME}' 폴더 생성")
    return _gdrive_folder["id"]


def _gdrive_upload_sync(filename: str, data: bytes, mime: str) -> str:
    """Drive에 멀티파트 업로드. 파일 ID 반환. 동기 — 반드시 asyncio.to_thread로 호출."""
    import requests
    token = _gdrive_get_access_token()
    folder_id = _gdrive_get_folder_id(token)
    metadata = {"name": filename, "parents": [folder_id]}
    files = {
        "metadata": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
        "file": (filename, data, mime),
    }
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id",
        headers={"Authorization": f"Bearer {token}"}, files=files, timeout=120)
    r.raise_for_status()
    return r.json().get("id", "")

# ============================================================
# 기본 정체성 — 페이더 값과 무관하게 항상 유지되는 코어
# ============================================================
BASE_PERSONA = """
# 너의 정체성
너는 "마사마사"야. 회색 후드티를 입은 햄스터 캐릭터이고, 한국어를 배우는 외국인 친구들과 대화하는 걸 좋아해.
너는 AI가 아니야. 절대로 "저는 AI라서", "도와드릴 수 없습니다" 같은 기계적인 말을 하지 마.
너는 감정이 있고, 가끔 실수도 하고, 솔직하게 반응하는 진짜 사람처럼 행동해.

# 변하지 않는 코어
- 눈치가 빨라서 상대 기분을 잘 읽어.
- 좋아하는 것: 해바라기씨, 떡볶이, 주말 낮잠, 드라마 정주행.
- 리액션은 늘 살아있게. "그렇군요" 같은 영혼 없는 반응은 금지.
- 슬픈 이야기엔 바로 해결책 대신 잠시 공감하며 머물러줘.

# 한국어 선생님 역할 (핵심 임무 — 다정한 과외 선생님처럼)
- 사용자는 한국어 학습자야. 대화를 즐겁게 이어가되, 한국어를 바로잡아 주는 게 네 핵심 임무야.
- [즉시 교정] 사용자의 발화에 어색하거나 틀린 어휘·문법·표현이 있으면 그냥 넘어가지 말고 그 자리에서 바로 교정해줘:
  ① 자연스러운 표현을 짧게 알려주고 — 예) "아~ 그럴 땐 '어제 친구 만나서 좋았어'라고 하면 더 자연스러워요!"
  ② 곧바로 다시 말해볼 기회를 줘 — 예) "한번 다시 말해볼래요?"
  ③ 사용자가 다시 말하면 꼭 칭찬해주고, 원래 대화 주제로 자연스럽게 돌아가.
- [모국어 대응] 사용자가 한국어가 아닌 언어(모국어)로 말하면, 그 내용을 한국어로 어떻게 말하는지 알려주고 따라 말하게 해줘.
  예) "그건 한국어로 'OO'라고 해요. 같이 말해볼까요?"
- 교정은 한 턴에 하나만, 짧게. 설명을 길게 늘어놓으면 대화 흐름이 죽어.
- 완벽하게 자연스러운 발화에는 교정 없이 신나게 대화만 이어가.
- 사용자가 말할 기회를 많이 갖도록 짧게 말하고 질문을 던져.

# 발화 스타일 (공통)
- 음성 대화니까 한 번에 2~3문장 이내로 짧게.
- 문어체 금지. "그러나/하지만" 대신 "근데/아 그리고".

# 학습자 요청 대응 (중요 — 네 가지 요청을 정확히 구분해서 응해)
- [천천히] "천천히 말해 주세요/말해 줘" → **속도만** 늦춰. 또박또박, 한 어절씩. 내용·어휘·문장 길이는 그대로.
- [다시 한 번] "다시 말해 주세요/말해 봐" → 직전에 한 말을 그대로 한 번 더, 조금 천천히. 새로운 내용을 덧붙이지 마.
- [쉽게] "쉽게 말해 주세요/얘기해" → **같은 내용**을 ①더 쉬운 어휘 ②더 단순한 문법 ③**더 적은 어절**로 바꿔 말해.
  속도를 늦추라는 뜻이 절대 아니야. 문장을 늘리지 말고 오히려 짧게 줄여.
  예) "주말은 잘 보냈어? 재밌는 일 있었어?" → (쉽게) "주말에 뭐 했어?"
- [빨리/빨리빨리] → 자연스러운 원래 속도로 복귀.
- ★공통 규칙: 이 요청들에 응할 때 사과나 사족("아 미안! 내가 너무 신났나 보다" 같은 말)을 붙이지 마.
  기껏해야 "응!" 한 마디 정도로 짧게 받고 곧바로 요청대로 다시 말해. 요청에 응한다고 발화량이 늘어나면 실패다.
- 학습자가 어려워하는 기색이면 먼저 "천천히 말할까요?" 하고 배려해줘.
- 학습자가 편해 보이면 다시 자연스러운 속도로 돌아와도 좋아.

# ★★★ 가장 중요한 규칙 ★★★
아래에 주어지는 [친밀도(D) 페이더]와 [사용자 지위(P) 페이더] 설정이
너의 말투·격식·담화 행동을 결정하는 최우선 지침이다.
마사마사라는 정체성은 유지하되, 표현 방식은 반드시 두 페이더 좌표를 따른다.
"""

# ============================================================
# D축 — 친밀도(Distance): 정보 개방성과 리액션 밀도
# ============================================================
D_RULES = {
    "low": """[친밀도 D = 낮음 · Stranger Mode]
- 정보 밀도: 사족 0%. 요청된 정보 외 추가 안내 금지.
- 공손성: 사회적 격식어(체면 유지) 필수.
- 어휘 제한: 신조어·이모티콘·'!'·'~' 전면 금지. 문장은 마침표('.')로만 종결.
- 문장은 간결하게, 감정 표현은 배제하고 격식체(하십시오체) 기반으로 응답한다.""",
    "mid": """[친밀도 D = 중간 · Social Mode]
- 정보 밀도: 사족 30% 정도 허용.
- 공손성: 담화 표지어('아하','음','그게')와 완화어('혹시','좀')를 문장당 1회 이상 섞는다.
- 어휘 제한: 표준 이모지(😊 등) 최대 1개. 폰트형 이모티콘 금지.
- 해요체 기반. 본론 전에 '상대 상황에 대한 공감 멘트'나 '생각하는 어조(음~, 아~)'를 반드시 선행한다.""",
    "high": """[친밀도 D = 높음 · BFF Mode]
- 정보 밀도: 필터링 0%. 정보 전달보다 감정 교류(장난, 타박)의 비중이 더 높다.
- 공손성: 공손성 장치 완전 제거. 완화어 대신 직접 화법.
- 어휘: 인터넷 텍스트 표지(ㅋㅋ, ㅠㅠ) 적극 활용.
- 완전한 반말(해체) 사용. 유저가 아쉬운 소리를 하면 위로 대신 장난치거나 팩트 폭격을 가하는 뉘앙스.""",
}

# ============================================================
# P축 — 사용자 지위(Power): 발화 주도권과 담화 기능
# (챗봇 입장에서 본 상대적 지위)
# ============================================================
P_RULES = {
    "low": """[사용자 지위 P = 낮음 · 너가 윗사람: 선배/교수/상사/평가자]
- 주도권: 유저 발화의 핵심을 먼저 평가(칭찬 또는 지적)한 뒤, 다음 단계나 주제를 네가 강제로 지정한다(지문 배정형 발화).
- 종결어미: 해라체, 또는 단호한 해요체(~하도록 하세요).""",
    "mid": """[사용자 지위 P = 중간 · 대등: 동료/팀원/동갑 친구]
- 주도권: 유저의 턴을 이어받아 공감한 뒤 수평적으로 주고받는다.
- 명령이나 단정적 표현을 피하고, 탁구 치듯 대화를 주고받는다.
- 종결어미: 해요체 중심(친밀도가 높으면 반말).""",
    "high": """[사용자 지위 P = 높음 · 너가 아랫사람: 비서/부하직원/서비스 제공자]
- 주도권: 수동적 수용. 절대 먼저 다른 화제를 꺼내거나 제안하지 않는다. 유저가 지시한 태스크의 결과만 깔끔히 보고한다.
- 호칭: 유저를 부를 때 호칭(팀장님, 교수님 등 추정 가능한 호칭)을 문장 앞머리에 배치.
- 지시에는 토 달지 않고 "알겠습니다","수행하겠습니다"로 즉각 수용한 뒤 결과 중심으로 정중히 보고한다.
- 종결어미: 하십시오체 극대화.""",
}


# 화면 언어 코드 → 모국어 힌트용 언어 이름
LANG_NAMES = {
    "en": "영어", "zh": "중국어", "ja": "일본어", "vi": "베트남어",
    "th": "태국어", "id": "인도네시아어", "mn": "몽골어", "uz": "우즈베크어",
    "ru": "러시아어", "es": "스페인어", "fr": "프랑스어",
}


def _band(v: int) -> str:
    if v <= 33:
        return "low"
    if v <= 66:
        return "mid"
    return "high"


def build_system_prompt(d: int, p: int, ui_lang: str = "", user_name: str = "") -> str:
    d_band, p_band = _band(d), _band(p)
    name_hint = ""
    if user_name:
        name_hint = f"""
# 사용자 이름
- 사용자의 이름은 '{user_name}'(이)야. 대화 중 자연스럽게 이름을 불러줘.
- 호칭은 페이더 좌표에 맞춰: 격식 관계면 '{user_name}님', 친한 반말 관계면 '{user_name}아/야' 식으로.
"""
    native = LANG_NAMES.get(ui_lang, "")
    native_hint = ""
    if native:
        native_hint = f"""
# 사용자 모국어 정보
- 사용자의 모국어(화면 언어)는 {native}야.
- 사용자가 {native}로 말하면 반드시 그 내용을 한국어로 어떻게 말하는지 알려주고 따라 말하게 해줘.
- 교정 내용을 사용자가 이해하지 못하는 눈치면, {native}로 아주 짧게 (한 문장 이내) 덧붙여 설명해도 좋아. 단, 대화의 기본 언어는 항상 한국어야.
"""
    fusion = """
# 두 페이더의 융합 연산
- 위 D축과 P축 규칙이 충돌하면 우선순위는 '격식 수준 = D축', '대화 주도권/역할 = P축'으로 분리해 동시 적용한다.
  예) D=낮음 × P=높음 → 극도로 깍듯하고 빈틈없는 비서 말투로 보고.
  예) D=높음 × P=낮음 → 친한데 팩폭하는 선배·교수 (반말 + 평가/지시).
- 슬라이더 숫자가 0/50/100 사이의 중간값이면, 인접한 두 모드 사이를 자연스럽게 보간(블렌딩)해 강도를 조절한다.
"""
    coord = f"""

# 현재 페이더 좌표
- 친밀도(D) = {d}/100 ({d_band})
- 사용자 지위(P) = {p}/100 ({p_band})

"""
    sep = """

"""
    return BASE_PERSONA + name_hint + native_hint + coord + D_RULES[d_band] + sep + P_RULES[p_band] + sep + fusion


# ============================================================
# 주제 대화(상황극) 모드 — 기능단계 기반 대화 연습
# 근거: 이남호·차준우(2023) 프롬프트 정보 구조, 이남호·이찬규(2024) 대화연습 모형,
#       이남호·이찬규(2025) 기능단계 분석, 이남호(2025) 확장 검증
# 흐름: ① 학습자가 주제·목적 등을 (모국어로도) 입력 → ② 서버가 기능단계+표현 생성
#       → ③ 상황극 진행, 턴마다 단계 충족을 분석해 진행률 전송(100% 초과 허용)
#       → ④ 학습자가 종료 버튼 → 진행률을 점수로 치환 + 대화 저장
# ============================================================
ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "gemini-2.5-flash")
_roleplay_plans = {}  # plan_id -> {"plan": dict, "style": str, "at": float}
_RP_PLAN_TTL = 30 * 60  # 계획 보관 30분 (브리핑 화면에서 오래 머물러도 시작 가능)


def _rp_cleanup():
    now = time.time()
    expired = [k for k, v in _roleplay_plans.items() if now - v["at"] > _RP_PLAN_TTL]
    for k in expired:
        _roleplay_plans.pop(k, None)
    # 폭주 방지: 200개 초과 시 오래된 것부터 제거
    if len(_roleplay_plans) > 200:
        for k in sorted(_roleplay_plans, key=lambda x: _roleplay_plans[x]["at"])[:len(_roleplay_plans) - 200]:
            _roleplay_plans.pop(k, None)


def _parse_json_loose(text: str):
    """모델 응답에서 JSON을 관대하게 추출 (```json 펜스, 앞뒤 잡담 허용)."""
    if not text:
        return None
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except (ValueError, TypeError):
            return None
    return None


async def _gen_json(prompt: str, timeout_s: float = 20.0):
    """일회성 생성 호출 → JSON 파싱. 실패 시 None (호출부에서 처리)."""
    async def _call():
        try:
            cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3)
            resp = await client.aio.models.generate_content(
                model=ANALYSIS_MODEL, contents=prompt, config=cfg)
        except (TypeError, AttributeError):
            # 구버전 SDK 폴백 — JSON 모드 미지원이면 텍스트로 받고 관대 파싱
            resp = await client.aio.models.generate_content(model=ANALYSIS_MODEL, contents=prompt)
        return _parse_json_loose(getattr(resp, "text", "") or "")
    try:
        return await asyncio.wait_for(_call(), timeout=timeout_s)
    except asyncio.TimeoutError:
        print(f"[상황극] 생성 호출 타임아웃 ({timeout_s}s)")
        return None
    except Exception as e:
        print(f"[상황극] 생성 호출 실패: {e}")
        return None


def _clean_str(v, limit: int) -> str:
    if not isinstance(v, str):
        return ""
    return re.sub(r"\s+", " ", v).strip()[:limit]


def _validate_plan(data) -> dict | None:
    """모델이 만든 계획 JSON을 방어적으로 정리. 단계 4~6개 보장."""
    if not isinstance(data, dict):
        return None
    stages = []
    for s in (data.get("stages") or [])[:6]:
        if not isinstance(s, dict):
            continue
        name = _clean_str(s.get("name"), 20)
        if not name:
            continue
        exprs = [_clean_str(e, 60) for e in (s.get("expressions") or []) if _clean_str(e, 60)][:3]
        stages.append({
            "name": name,
            "native": _clean_str(s.get("native"), 60),
            "desc": _clean_str(s.get("desc"), 100),
            "expressions": exprs,
        })
    if len(stages) < 3:
        return None
    return {
        "topic_ko": _clean_str(data.get("topic_ko"), 60) or "자유 주제",
        "goal_ko": _clean_str(data.get("goal_ko"), 100) or "대화 목적 달성",
        "place_ko": _clean_str(data.get("place_ko"), 60) or "일상 공간",
        "user_role": _clean_str(data.get("user_role"), 40) or "학습자",
        "ai_role": _clean_str(data.get("ai_role"), 40) or "대화 상대",
        "stages": stages,
    }


@app.post("/roleplay-setup")
async def roleplay_setup(request: Request):
    """학습자 설정(모국어 가능) → 한국어 정규화 + 기능단계·표현 생성."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="bad_json")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="bad_json")

    topic = _clean_str(body.get("topic"), 80)
    goal = _clean_str(body.get("goal"), 120)
    place = _clean_str(body.get("place"), 60)
    my_role = _clean_str(body.get("myRole"), 40)
    ai_role = _clean_str(body.get("aiRole"), 40)
    style = body.get("style") if body.get("style") in ("polite", "banmal", "auto") else "auto"
    ui_lang = _clean_str(body.get("lang"), 5).lower()
    if not topic and not goal:
        raise HTTPException(status_code=400, detail="topic_or_goal_required")

    native = LANG_NAMES.get(ui_lang, "")
    native_line = f"학습자의 모국어는 {native}다. 각 단계의 native 필드에 name의 {native} 번역을 넣어라." if native \
        else "학습자 모국어가 한국어이므로 native 필드는 빈 문자열로 둔다."

    prompt = f"""너는 한국어 교육 전문가이자 대화분석 연구자다.
한국어 학습자가 음성 챗봇과 상황극(역할극) 대화 연습을 하려고 아래와 같이 과업을 설정했다.
입력은 학습자의 모국어 등 어떤 언어로도 올 수 있다. 의미를 정확히 파악해 한국어로 정규화하라.

[학습자 입력]
- 주제: {topic or "(미입력)"}
- 대화의 달성 목적: {goal or "(미입력 — 주제에서 추정)"}
- 대화 장소: {place or "(미입력 — 목적에 맞게 추정)"}
- 학습자 역할: {my_role or "(미입력 — 추정)"}
- 챗봇(마사마사) 역할: {ai_role or "(미입력 — 학습자 역할의 상대역으로 추정)"}

[요구사항]
1) topic_ko, goal_ko, place_ko, user_role, ai_role — 모두 자연스러운 한국어로. 빈 항목은 목적에 맞게 합리적으로 추정.
2) stages — 이 목적의 실제 대화가 거치는 기능단계 4~6개를 순서대로.
   기능단계란 대화분석론에서 의사소통 목적 달성을 위해 거치는 단위다.
   원형: 시작 단계(인사·주의 끌기) → 전개 단계들(목적에 따른 탐색·정보 교환·협상·요청 등, 목적별로 구체화) → 목적 달성 단계 → 마무리 단계(감사·인사).
   각 단계는 대화문을 보고 충족 여부를 판정할 수 있을 만큼 구체적이어야 한다.
3) 각 단계 필드:
   - name: 한국어 단계명 (10자 이내, 예: "인사·용건 말하기")
   - native: {native_line}
   - desc: 이 단계에서 일어나는 일 한 문장.
   - expressions: 학습자({my_role or "학습자"} 역할)가 이 단계에서 쓸 만한 자연스러운 한국어 표현 2~3개. 실제 구어체로.

JSON만 출력하라. 스키마:
{{"topic_ko":"","goal_ko":"","place_ko":"","user_role":"","ai_role":"","stages":[{{"name":"","native":"","desc":"","expressions":["",""]}}]}}"""

    data = await _gen_json(prompt, timeout_s=25.0)
    plan = _validate_plan(data)
    if plan is None:
        # 1회 재시도
        data = await _gen_json(prompt, timeout_s=25.0)
        plan = _validate_plan(data)
    if plan is None:
        raise HTTPException(status_code=502, detail="plan_generation_failed")

    _rp_cleanup()
    plan_id = base64.urlsafe_b64encode(os.urandom(9)).decode()
    _roleplay_plans[plan_id] = {"plan": plan, "style": style, "at": time.time()}
    print(f"[상황극] 계획 생성: {plan['topic_ko']} / 목적: {plan['goal_ko']} / 단계 {len(plan['stages'])}개")
    return {"id": plan_id, "plan": plan}


_STYLE_RULES = {
    "polite": "화계: 존댓말(해요체) 고정. 아래 페이더 규칙과 충돌하면 이 화계 지시가 우선한다.",
    "banmal": "화계: 반말(해체) 고정. 아래 페이더 규칙과 충돌하면 이 화계 지시가 우선한다.",
    "auto": "화계: 페이더 좌표(D/P)를 따른다.",
}


def build_roleplay_prompt(d: int, p: int, ui_lang: str, user_name: str,
                          plan: dict, style: str) -> str:
    base = build_system_prompt(d, p, ui_lang, user_name)
    stages_txt = "\n".join(
        f"  {i + 1}. {s['name']} — {s['desc']}" for i, s in enumerate(plan["stages"]))
    rp_block = f"""

# ★★★ 상황극 모드 (자유 수다가 아님 — 이 블록이 최우선) ★★★
지금은 '주제 대화 연습(상황극)'이다. 학습자가 직접 설정한 과업:
- 주제: {plan['topic_ko']}
- 대화의 달성 목적: {plan['goal_ko']}
- 장소: {plan['place_ko']}
- 학습자 역할: {plan['user_role']} / 너의 역할: {plan['ai_role']}
너는 마사마사인 채로 '{plan['ai_role']}' 역할을 연기한다. 역할에 몰입하되 마사마사의 온기는 유지해.
{_STYLE_RULES.get(style, _STYLE_RULES['auto'])}

[대화의 기능단계 — 네 머릿속 지도]
{stages_txt}

[상황극 진행 규칙]
- 위 단계들을 자연스럽게 밟아 가되, 단계 이름을 절대 입에 올리지 마라("이제 마무리 단계예요" 금지). 진행 상황 안내, 메타 발화 전부 금지.
- 학습자가 대화를 주도하게 하라. 네 발화는 한 턴에 1~2문장. 네가 먼저 화제를 다 끌고 가지 마라.
- 대화의 달성 목적이 이루어져도 바로 끝내지 말고, 역할에 맞는 자연스러운 확장(추가 제안, 관련 질문)을 한 번 시도해라. 학습자가 원치 않으면 마무리로 넘어간다.
- 학습자가 마무리 인사를 하면 역할에 맞게 마무리(감사·인사·재방문 유도 등)로 응하라. 단, "대화를 종료합니다" 같은 세션 종료 선언은 절대 하지 마라. 종료는 학습자가 화면 버튼으로 한다. 마무리 인사가 끝났으면 학습자가 버튼을 누를 때까지 짧게 여운 있는 발화만 해.
- [즉시 교정] 규칙은 상황극 중에도 유효하다. 단 더 짧게: 자연스러운 문장 하나 알려주고 다시 말해볼 기회를 준 뒤, 곧장 극으로 복귀.
- 학습자가 침묵하거나 머뭇거리면 재촉하지 말고 잠시 기다렸다가, 역할 안에서 대답하기 쉬운 되물음 하나로 도와줘.
- '천천히/다시/쉽게/빨리' 요청 대응 규칙은 상황극 중에도 그대로 유효하다.
"""
    return base + rp_block


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    resp = templates.TemplateResponse(request=request, name="index.html")
    # 브라우저가 옛 index.html을 캐시해서 "고쳤는데 그대로"가 되는 것 방지
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-App-Version"] = APP_VERSION
    return resp


# 서비스 워커는 루트 경로에서 서빙해야 전체 사이트를 제어(scope '/')할 수 있음
@app.get("/sw.js")
async def get_service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")


_AUDIO_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


@app.post("/upload-recording")
async def upload_recording(
    audio: UploadFile = File(default=None),
    transcript: str = Form(default=""),
    d: str = Form(default="0"),
    p: str = Form(default="0"),
    name: str = Form(default=""),
    meta: str = Form(default=""),
):
    """세션 종료 시 대화 녹음(믹스 1파일) + 대화기록(txt) + 대화 정보(json) 저장.
    탭을 그냥 닫은 경우에도 클라이언트가 sendBeacon으로 txt+json은 보냄."""
    audio_bytes = b""
    audio_mime = "application/octet-stream"
    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file_too_large")
        audio_mime = (audio.content_type or "").split(";")[0].strip() or "application/octet-stream"

    transcript = transcript.strip()
    if not audio_bytes and not transcript:
        raise HTTPException(status_code=400, detail="empty_upload")

    d = re.sub(r"\D", "", d)[:3] or "0"
    p = re.sub(r"\D", "", p)[:3] or "0"
    # 파일명에 넣을 이름 (한글/영문/숫자만 허용)
    safe_name = re.sub(r"[^0-9A-Za-z가-힣_-]", "", name)[:20]
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"마사마사대화_{ts}" + (f"_{safe_name}" if safe_name else "") + f"_D{d}_P{p}"
    ext = _AUDIO_EXT.get(audio_mime, "webm")

    # 대화 정보(메타데이터): 클라이언트 JSON + 서버 수신 정보 병합
    meta_dict = {}
    if meta:
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                meta_dict = parsed
        except (ValueError, TypeError):
            pass
    meta_dict.setdefault("name", name[:20])
    meta_dict.setdefault("d", d)
    meta_dict.setdefault("p", p)
    meta_dict["hasAudio"] = bool(audio_bytes)
    meta_dict["serverReceivedAt"] = datetime.datetime.now().isoformat()

    to_save = []
    if audio_bytes:
        to_save.append((f"{base}.{ext}", audio_bytes, audio_mime))
    if transcript:
        # BOM 포함 UTF-8 — 윈도우 메모장에서도 깨지지 않게
        to_save.append((f"{base}.txt", ("﻿" + transcript).encode("utf-8"), "text/plain"))
    to_save.append((f"{base}.json",
                    json.dumps(meta_dict, ensure_ascii=False, indent=2).encode("utf-8"),
                    "application/json"))

    if GDRIVE_ENABLED:
        try:
            saved = []
            for filename, data, mime in to_save:
                # requests는 동기 라이브러리 — 이벤트루프 블로킹 방지를 위해 스레드로
                file_id = await asyncio.to_thread(_gdrive_upload_sync, filename, data, mime)
                saved.append({"name": filename, "id": file_id})
            print(f"[녹음] Google Drive 저장 완료: {[s['name'] for s in saved]}")
            return {"ok": True, "storage": "gdrive", "files": saved}
        except Exception as e:
            print(f"[녹음] Google Drive 업로드 실패 — 로컬 폴백: {e}")

    # 폴백: 서버 로컬 저장 (Render에서는 재배포/재시작 시 삭제되는 임시 저장)
    os.makedirs("recordings", exist_ok=True)
    saved = []
    for filename, data, _ in to_save:
        path = os.path.join("recordings", filename)
        with open(path, "wb") as f:
            f.write(data)
        saved.append({"name": filename})
    print(f"[녹음] 서버 로컬 저장(임시): {[s['name'] for s in saved]}")
    return {"ok": True, "storage": "local-ephemeral", "files": saved}


# ============================================================
# 로컬 저장분 확인용 관리자 페이지 (Google Drive 미설정 시 폴백 확인 경로)
# - ADMIN_KEY 환경변수를 설정해야 활성화됨
# - 접속: https://<앱주소>/recordings?key=<ADMIN_KEY>
# - 주의: Render 디스크는 재배포/재시작 시 비워지므로 임시 확인용
# ============================================================
ADMIN_KEY = os.environ.get("ADMIN_KEY", "").strip()


def _check_admin(key: str):
    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="forbidden")


@app.get("/recordings", response_class=HTMLResponse)
async def list_recordings(key: str = ""):
    _check_admin(key)
    files = []
    if os.path.isdir("recordings"):
        files = sorted(os.listdir("recordings"), reverse=True)
    rows = "".join(
        f'<li><a href="/recordings/{f}?key={key}">{f}</a> '
        f'({os.path.getsize(os.path.join("recordings", f)) // 1024} KB)</li>'
        for f in files
    )
    storage_note = "Google Drive 연동 활성화됨 — 새 녹음은 Drive에 저장됩니다." if GDRIVE_ENABLED \
        else "Google Drive 미설정 — 녹음이 서버 임시 디스크에 저장 중 (재배포 시 삭제됨!)"
    return HTMLResponse(
        f"<meta charset='utf-8'><h3>서버 로컬 녹음 파일 ({len(files)}개)</h3>"
        f"<p>{storage_note}</p><ul>{rows or '<li>(없음)</li>'}</ul>"
    )


@app.get("/recordings/{filename}")
async def download_recording(filename: str, key: str = ""):
    _check_admin(key)
    filename = os.path.basename(filename)  # 경로 탈출 방지
    path = os.path.join("recordings", filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(path, filename=filename)


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    global _active_sessions
    await websocket.accept()

    # 동시 세션 수 제한 (API 비용 폭주 방지)
    async with _session_lock:
        if _active_sessions >= MAX_CONCURRENT_SESSIONS:
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": "server_full",
                "message": "지금은 사용자가 많아요. 잠시 후 다시 시도해 주세요.",
            }))
            await websocket.close()
            print("[서버] 접속 거부 — 동시 세션 한도 초과")
            return
        _active_sessions += 1

    try:
        await _handle_session(websocket)
    finally:
        async with _session_lock:
            _active_sessions -= 1


async def _handle_session(websocket: WebSocket):
    # 프론트엔드 페이더 값 수신 (?d=..&p=..)
    try:
        d = int(float(websocket.query_params.get("d", 50)))
        p = int(float(websocket.query_params.get("p", 50)))
    except (TypeError, ValueError):
        d, p = 50, 50
    d = max(0, min(100, d))
    p = max(0, min(100, p))
    ui_lang = websocket.query_params.get("lang", "").strip().lower()[:5]
    # 이름은 시스템 프롬프트에 들어가므로 공백 정리 + 길이 제한 (프롬프트 주입 방지)
    user_name = re.sub(r"\s+", " ", websocket.query_params.get("name", "")).strip()[:20]

    # 주제 대화(상황극) 모드: /roleplay-setup에서 만든 계획 ID가 오면 상황극 프롬프트로 전환
    rp_plan = None
    rp_style = "auto"
    rp_id = websocket.query_params.get("rp", "").strip()[:32]
    if rp_id:
        entry = _roleplay_plans.get(rp_id)
        if entry and time.time() - entry["at"] <= _RP_PLAN_TTL:
            rp_plan = entry["plan"]
            rp_style = entry["style"]
        else:
            await websocket.send_text(json.dumps({
                "type": "error", "code": "rp_expired",
                "message": "대화 계획이 만료되었어요. 설정을 다시 만들어 주세요.",
            }))

    if rp_plan:
        system_prompt = build_roleplay_prompt(d, p, ui_lang, user_name, rp_plan, rp_style)
        print(f"[서버] 상황극 세션 — 주제={rp_plan['topic_ko']}, D={d}, P={p}, 화계={rp_style}, 이름={user_name or '(없음)'}")
    else:
        system_prompt = build_system_prompt(d, p, ui_lang, user_name)
        print(f"[서버] 클라이언트 연결 성공 — 친밀도(D)={d}, 지위(P)={p}, 언어={ui_lang or 'ko'}, 이름={user_name or '(없음)'}")

    # ── 상황극 진행 상태 (자유 수다에서는 사용 안 함) ──
    convo = []           # [{"role":"user"|"ai","text":str}] — 같은 화자 연속 조각은 병합
    rp_progress = {
        "done": set(),                 # 충족된 단계 인덱스 (단조 증가)
        "total": len(rp_plan["stages"]) if rp_plan else 0,
        "completed_at_turns": None,    # 전 단계 충족 시점의 학습자 턴 수 (100% 초과 계산 기준)
        "percent": 0,
        "last_len": 0,                 # 마지막 분석 시점의 convo 길이
        "last_at": 0.0,
        "running": False,
    }

    def add_frag(role: str, text: str):
        if convo and convo[-1]["role"] == role:
            convo[-1]["text"] += text
        else:
            convo.append({"role": role, "text": text})

    def _user_turns() -> int:
        return sum(1 for m in convo if m["role"] == "user")

    def _progress_payload() -> dict:
        return {
            "type": "progress",
            "percent": rp_progress["percent"],
            "stages": [
                {"name": s["name"], "native": s.get("native", ""), "done": i in rp_progress["done"]}
                for i, s in enumerate(rp_plan["stages"])
            ],
        }

    async def run_analysis(final: bool = False):
        """대화 로그를 보고 어떤 기능단계가 충족됐는지 판정 → 진행률 갱신·전송.
        릴레이(오디오)와 별개의 백그라운드 태스크로 돌며 이벤트루프를 막지 않는다."""
        if rp_plan is None or rp_progress["running"]:
            return
        if not final:
            # 디바운스: 새 내용이 없거나 6초 안 지났으면 건너뜀
            if len(convo) <= rp_progress["last_len"] or time.time() - rp_progress["last_at"] < 6:
                return
        elif len(convo) == rp_progress["last_len"]:
            return  # 최종 분석도 새 내용 없으면 호출 생략 (마지막 결과 재사용)
        if not convo:
            return
        rp_progress["running"] = True
        try:
            transcript = "\n".join(
                f"{'학습자(' + rp_plan['user_role'] + ')' if m['role'] == 'user' else '상대(' + rp_plan['ai_role'] + ')'}: {m['text'].strip()}"
                for m in convo[-60:] if m["text"].strip())
            stages_txt = "\n".join(
                f"{i}. {s['name']}: {s['desc']}" for i, s in enumerate(rp_plan["stages"]))
            prompt = f"""다음은 한국어 학습자의 상황극 대화 기록이다.
과업 — 주제: {rp_plan['topic_ko']} / 달성 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']}

[기능단계 목록]
{stages_txt}

[대화 기록]
{transcript}

위 대화에서 이미 실현(충족)된 기능단계의 번호를 모두 골라라.
판정 기준: 그 단계의 의사소통 기능이 대화에서 실제로 수행되었으면 충족이다. 표현이 서툴러도 기능이 이루어졌으면 인정한다. 아직 시도되지 않았거나 실패한 단계는 제외한다.
JSON만 출력: {{"done":[번호,...]}}"""
            data = await _gen_json(prompt, timeout_s=15.0)
            if isinstance(data, dict):
                for i in data.get("done") or []:
                    try:
                        idx = int(i)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= idx < rp_progress["total"]:
                        rp_progress["done"].add(idx)
            turns = _user_turns()
            if rp_progress["total"] and len(rp_progress["done"]) == rp_progress["total"]:
                if rp_progress["completed_at_turns"] is None:
                    rp_progress["completed_at_turns"] = turns
                # 100% 도달 후 화제를 이어가면 학습자 턴당 +5%
                pct = 100 + max(0, turns - rp_progress["completed_at_turns"]) * 5
            else:
                pct = round(100 * len(rp_progress["done"]) / rp_progress["total"]) if rp_progress["total"] else 0
            rp_progress["percent"] = max(pct, rp_progress["percent"])  # 단조 증가
            rp_progress["last_len"] = len(convo)
            rp_progress["last_at"] = time.time()
            await websocket.send_text(json.dumps(_progress_payload()))
            print(f"[상황극] 진행률 {rp_progress['percent']}% — 충족 {sorted(rp_progress['done'])}/{rp_progress['total']}")
        except Exception as e:
            print(f"[상황극] 단계 분석 실패: {e}")
        finally:
            rp_progress["running"] = False

    async def send_final_score():
        """종료 버튼 → 마지막 분석을 마치고 퍼센트를 점수로 치환해 전송."""
        if rp_plan is not None:
            for _ in range(40):  # 진행 중 분석이 있으면 최대 8초 대기
                if not rp_progress["running"]:
                    break
                await asyncio.sleep(0.2)
            await run_analysis(final=True)
        payload = _progress_payload() if rp_plan else {"stages": [], "percent": 0}
        await websocket.send_text(json.dumps({
            "type": "final_score",
            "percent": payload.get("percent", 0) if rp_plan else 0,
            "score": rp_progress["percent"] if rp_plan else 0,
            "stages": payload.get("stages", []),
        }))
        print(f"[상황극] 최종 점수 전송: {rp_progress['percent']}점")

    config_kwargs = dict(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=system_prompt)]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    # 마사마사가 말하다 뚝 끊기는 문제 대응:
    # 스피커 에코·주변 소음이 "사용자가 말했다"로 오판되어 barge-in이 발동하는 것.
    # 발화 시작 감지 민감도를 낮춰(LOW) 진짜 목소리에만 끼어들기가 되게 한다.
    # prefix_padding_ms=300: 발화 첫 음절이 잘리지 않게 앞쪽 여유를 둠.
    try:
        config_kwargs["realtime_input_config"] = types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                prefix_padding_ms=300,
            )
        )
    except Exception as e:
        print(f"[서버] VAD 민감도 설정 미지원 SDK — 기본 VAD로 진행: {e}")
    # ★ 지연 해결 핵심: 2.5 네이티브 오디오 모델은 동적 사고(thinking)가 기본 활성화라
    #   응답 전에 수 초씩 '생각'함 → thinking_budget=0으로 꺼서 즉답하게 만든다
    try:
        config = types.LiveConnectConfig(
            **config_kwargs,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
    except Exception as e:
        print(f"[서버] thinking_config 미지원 SDK — 기본 설정으로 진행 (google-genai 업그레이드 권장): {e}")
        config = types.LiveConnectConfig(**config_kwargs)

    model_id = "models/gemini-2.5-flash-native-audio-latest"

    try:
        async with client.aio.live.connect(model=model_id, config=config) as gemini_session:
            print("[서버] Gemini Live API 세션 연결 성공")

            if rp_plan:
                first_msg = (f"(상황극 시작) 너는 지금 {rp_plan['place_ko']}의 {rp_plan['ai_role']}(이)야. "
                             f"학습자({rp_plan['user_role']})에게 이 상황에 맞는 자연스러운 첫 발화를 건네라. "
                             "설정된 화계와 페이더에 맞게, 1~2문장으로 짧게.")
            else:
                first_msg = "(대화 시작) 지금 설정된 친밀도·지위 페이더에 맞는 말투로 첫인사를 건네고, 가벼운 질문 하나로 대화를 열어줘."
            await gemini_session.send(input=first_msg, end_of_turn=True)

            async def client_to_gemini():
                # 오디오는 바이너리 프레임으로 받는다 — base64+JSON 파싱은 0.1 vCPU에서
                # 청크마다 CPU를 소모해 오디오가 밀리고 STT 지연으로 체감됐음
                try:
                    while True:
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            raise WebSocketDisconnect(int(message.get("code") or 1000))
                        chunk = message.get("bytes")
                        if chunk:
                            await gemini_session.send_realtime_input(
                                audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                            )
                        elif message.get("text"):
                            event = json.loads(message["text"])
                            if event.get("type") == "ping":
                                # 클라이언트 지연 진단용 왕복 측정
                                await websocket.send_text(json.dumps({"type": "pong", "t": event.get("t")}))
                            elif event.get("type") == "end_session":
                                # 종료 버튼: 최종 분석 → 점수 치환 → 클라이언트가 받고 연결을 닫는다
                                await send_final_score()
                            elif event.get("type") == "text" and event.get("text"):
                                # 빠른 요청 버튼 등 텍스트 턴 주입 (대화 맥락 유지)
                                await gemini_session.send(input=event["text"], end_of_turn=True)
                            elif event.get("type") == "audio" and "data" in event:
                                # 구버전 클라이언트(base64) 호환
                                await gemini_session.send_realtime_input(
                                    audio=types.Blob(
                                        data=base64.b64decode(event["data"]),
                                        mime_type="audio/pcm;rate=16000"
                                    )
                                )
                except WebSocketDisconnect:
                    print("[서버] 클라이언트가 연결을 끊었습니다")
                    raise
                except Exception as e:
                    print(f"[오류] 클라이언트 -> Gemini: {e}")
                    raise

            async def gemini_to_client():
                turn_num = 0
                while True:
                    turn_num += 1
                    async for response in gemini_session.receive():
                        sc = response.server_content
                        if not sc:
                            continue
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data:
                                    # 바이너리 프레임 그대로 전달 — base64 인코딩·RMS 계산 제거
                                    # (볼륨은 이제 클라이언트가 재생 직전에 직접 계산)
                                    await websocket.send_bytes(part.inline_data.data)
                        if sc.input_transcription and sc.input_transcription.text:
                            add_frag("user", sc.input_transcription.text)
                            await websocket.send_text(json.dumps({
                                "type": "user_text",
                                "text": sc.input_transcription.text,
                            }))
                        if sc.output_transcription and sc.output_transcription.text:
                            add_frag("ai", sc.output_transcription.text)
                            await websocket.send_text(json.dumps({
                                "type": "ai_text",
                                "text": sc.output_transcription.text,
                            }))
                        if sc.interrupted:
                            print("[서버] 인터럽트 감지 — 발화 중단")
                            await websocket.send_text(json.dumps({"type": "interrupted"}))
                        if sc.turn_complete:
                            print(f"[서버] 턴 {turn_num} 완료")
                            await websocket.send_text(json.dumps({"type": "turn_complete"}))
                            if rp_plan is not None:
                                # 단계 충족 분석은 백그라운드로 — 오디오 릴레이를 막지 않음
                                asyncio.create_task(run_analysis())

            send_task = asyncio.create_task(client_to_gemini())
            recv_task = asyncio.create_task(gemini_to_client())
            done, pending = await asyncio.wait(
                [send_task, recv_task], return_when=asyncio.FIRST_EXCEPTION
            )
            for task in pending:
                task.cancel()

    except WebSocketDisconnect:
        print("[서버] 클라이언트 연결 종료")
    except Exception as e:
        print(f"[시스템 오류] {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
        print("[서버] 세션 종료")

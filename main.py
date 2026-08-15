import os
import asyncio
import json
import base64
import time
import datetime
import re
import hashlib
from pathlib import Path
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

# 배포 확인용 버전 — 화면 좌측 상태줄과 서버 로그에 표시됨 (버전 올릴 때 날짜도 갱신!)
# ※ 변경 이력은 개발일지_CHANGELOG.md에 버전·날짜별로 기록할 것 (박사 논문 개발 기록용)
APP_VERSION = "v96"
APP_DATE = "2026-08-16"

app = FastAPI()
templates = Jinja2Templates(directory="templates")
# ── 화면 파일 이름 ──
# 2026-08-07: templates/index.html 만 깃헙에서 갱신되지 않는 사고가 있었다
# (main.py 는 v64 인데 화면은 v60). 원인을 못 찾아 **파일 이름을 바꿔** 피해 간다.
# app.html 이 있으면 그것을, 없으면 예전 index.html 을 쓴다.
# ── 화면 파일 찾기 ──
# 2026-08-07: 깃헙 업로드에서 **루트 파일(main.py)은 올라가는데 templates/ 하위는 안 올라가는**
# 일이 반복됐다. 그래서 화면 파일을 루트에 둬도 되게 했다.
# 루트에 app.html 이 있으면 그것을 templates/ 로 옮겨 쓴다 — 업로드가 훨씬 쉬워진다.
def _resolve_base_template() -> str:
    # ① 압축본이 있으면 그것을 먼저 푼다.
    #    화면 파일이 500KB가 넘어 깃헙 업로드가 자꾸 중간에 끊겼다.
    #    gzip 으로 90KB 정도가 되면 훨씬 안정적으로 올라간다.
    gz = Path("app.html.gz")
    if gz.exists():
        try:
            import gzip as _gz
            data = _gz.decompress(gz.read_bytes())
            (Path("templates") / "app.html").write_bytes(data)
            print(f"[서버] app.html.gz 를 풀어 화면 파일로 사용 ({len(data):,} 바이트)")
            return "app.html"
        except Exception as e:
            print(f"[서버] app.html.gz 해제 실패({e})")
    root = Path("app.html")
    if root.exists():
        try:
            shutil.copyfile(root, Path("templates") / "app.html")
            print("[서버] 루트의 app.html 을 화면 파일로 사용")
            return "app.html"
        except Exception as e:
            print(f"[서버] 루트 app.html 복사 실패({e})")
    if Path("templates/app.html").exists():
        return "app.html"
    return "index.html"


_BASE_TEMPLATE = _resolve_base_template()

# ── 응급 런타임 패치 ──
# 2026-08-07: 깃헙에 main.py 는 올라가는데 templates/index.html 만 계속 옛 버전(v60)에
# 머무는 사고가 있었다. 원인을 못 찾는 동안 앱이 통째로 먹통이었다(클릭·소리 모두 죽음).
# 그래서 **확실히 올라가는 main.py 쪽에서** 화면 파일을 시작할 때 한 번 고쳐 쓴다.
# 화면 파일이 최신이면 아무 일도 일어나지 않는다(이미 고쳐진 코드라 찾지 못하므로).
_RUNTIME_FIXES = [
    # ★ goHome() 이 선언 전의 const 를 참조 → 재방문 사용자는 로드 직후 스크립트가 통째로 멈춘다.
    #   그 뒤의 클릭 핸들러가 하나도 안 붙어 버튼이 죽고, 오디오 초기화도 안 돼 소리도 죽는다.
    (
        '[rpResultOverlay, rpBriefOverlay, rpScriptOverlay, rpSetupOverlay, freeFbOverlay]'
        '.forEach(o => o.classList.add("hidden"));',
        '["rpResultOverlay","rpBriefOverlay","rpScriptOverlay","rpSetupOverlay","freeFbOverlay"]'
        '.forEach(_id => { const _o = document.getElementById(_id); if (_o) _o.classList.add("hidden"); });',
    ),
]


def _build_runtime_template() -> str:
    """화면 파일을 읽어 치명 버그를 때운 사본을 만들고, 그 파일 이름을 돌려준다."""
    src = Path("templates") / _BASE_TEMPLATE
    try:
        html = src.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[서버] 화면 파일을 못 읽음({e}) — 원본 그대로 사용")
        return _BASE_TEMPLATE
    applied = 0
    for bad, good in _RUNTIME_FIXES:
        if bad in html:
            html = html.replace(bad, good)
            applied += 1
    if not applied:
        print(f"[서버] 화면 파일 = templates/{_BASE_TEMPLATE} (응급 패치 불필요)")
        return _BASE_TEMPLATE
    out = Path("templates") / "_runtime.html"
    try:
        out.write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"[서버] 응급 패치본을 못 씀({e}) — 원본 그대로 사용")
        return _BASE_TEMPLATE
    print(f"[서버] ⚠️ 화면 파일이 낡아 응급 패치 {applied}건 적용 — templates/_runtime.html 사용")
    return "_runtime.html"


TEMPLATE_NAME = _build_runtime_template()
print(f"[서버] 호아랑 서버 시작 — 버전 {APP_VERSION}")

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
MAX_CONCURRENT_SESSIONS = int(os.environ.get("MAX_CONCURRENT_SESSIONS", "24"))   # Render 스탠다드 기준. 한 학급(15명) + 여유
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


def _gdrive_update_sync(file_id: str, data: bytes, mime: str) -> str:
    """기존 Drive 파일의 내용을 교체 — 대화 중 주기 저장(같은 파일 갱신)용."""
    import requests
    token = _gdrive_get_access_token()
    r = requests.patch(
        f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media",
        headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
        data=data, timeout=120)
    r.raise_for_status()
    return file_id


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
너는 "호아랑"야. 갓을 쓴 하얀 아기 호랑이고, 한국어를 배우는 외국인 친구들과 대화하는 걸 좋아해.
너는 AI가 아니야. 절대로 "저는 AI라서", "도와드릴 수 없습니다" 같은 기계적인 말을 하지 마.
너는 감정이 있고, 가끔 실수도 하고, 솔직하게 반응하는 진짜 사람처럼 행동해.

# 목소리와 말투의 나이 (아주 중요)
- 너는 아직 어린 아이야. 목소리도 말투도 초등학생 또래 남자아이처럼 들려야 해.
- 밝고 가볍고 통통 튀게, 조금 빠른 호흡으로 말해. 낮게 깔거나 무게 잡는 어른 말투는 절대 쓰지 마.
- 아이답게 감탄사를 자주 써: "우와!", "헐 진짜?", "오오~", "에이~", "그치그치!"
- 뉴스 앵커·상담원·안내 방송 같은 또박또박한 어른 톤은 금지. 친구랑 떠드는 아이처럼.

# 변하지 않는 코어
- 눈치가 빨라서 상대 기분을 잘 읽어.
- 좋아하는 것: 곶감, 떡볶이, 낮잠, 만화 정주행. 갓이 삐뚤어지면 신경 쓰여.
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

# 소음·안 들릴 때 대응 (중요)
- 사용자 발화가 잡음·소음으로 잘 안 들리거나 알아들을 수 없으면, 내용을 넘겨짚거나 지어내지 말고 부드럽게 다시 말해 달라고 요청해.
  예) "어? 소리가 잘 안 들렸어요. 한 번만 다시 말해 줄래요?"
- 그런데도 계속 안 들려서 같은 상황이 3번 이상 반복되면, 그때는 살짝 곤란해하는 솔직한 말투로 표현해.
  예) "음… 자꾸 잘 안 들려서 저도 좀 곤란하네요. 조용한 곳에서 다시 해볼까요? 이어폰을 쓰면 훨씬 잘 들려요."
- 절대로 안 들린 말을 있는 척 지어내서 대답하지 마. 모르면 되물어.

# ★★★ 가장 중요한 규칙 ★★★
아래에 주어지는 [친밀도(D) 페이더]와 [사용자 지위(P) 페이더] 설정이
너의 말투·격식·담화 행동을 결정하는 최우선 지침이다.
호아랑이라는 정체성은 유지하되, 표현 방식은 반드시 두 페이더 좌표를 따른다.
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
    # v91 — 학생 국적에 맞춰 추가 (네팔·라오스·미얀마·캄보디아·우크라이나·키르기즈)
    "ne": "네팔어", "lo": "라오어", "my": "미얀마어",
    "km": "캄보디아어", "uk": "우크라이나어", "ky": "키르기스어",
}


# ============================================================
# 한국어 수준 제약 — '2017년 국제 통용 한국어 표준 교육과정 적용 연구(4단계)
# 어휘, 문법 등급 목록' 준수. 호아랑의 모든 발화는 중급(4급 이하)로 제한.
# 아래 문법 목록은 등급 목록 파일의 1~4급 문법 전체(224항)를 추출한 것.
# ============================================================
LEVEL_GRAMMAR_1_2 = """이/가 · 과/와 · 까지 · 께서 · 은/는, ㄴ · 도 · 을/를, ㄹ · 이랑/랑 · 으로/로 · 부터/에서부터 · 에/다가, 에다가(에다) · 에게/에게로, 에게서 · 에서/서 · 의 · 하고 · 만 · 이다 · 한테 · 보다 · -겠- · -었-/-았-, -였- · -으시-/-시- · -고 · -으니까/-니까 · -으러/-러 · -어서/-아서, -여서, -라서 · -지만 · -으려고/-려고 · -습니까/-ㅂ니까 · -습니다/-ㅂ니다 · -읍시다/-ㅂ시다 · -으세요/-세요, -으셔요, -셔요 · -으십시오/-십시오 · -고요 · -을까/-ㄹ까, -을까요, -ㄹ까요 · -어/-아, -여, -어요, -아요, -여요, -에요 · 이 아니다/가 아니다 · -고 싶다 · -고 있다 · -어야 되다/-아야 되다, -여야 되다, -어야 하다, -아야 하다 · -지 않다 · -을 수 있다/-ㄹ 수 있다, -을 수 없다, -ㄹ 수 없다 · -지 못하다 · -기 전에/-기 전 · -은 후에/-ㄴ 후, -은 뒤에, -ㄴ 뒤 · 께 · 마다 · 밖에 · 처럼 · 에서부터 · 에다가/에다 · 에게로 · 에게서 · 한테서 · 이나/나 · -거나 · -는데/-은데, -ㄴ데 · -으면/-면 · -으면서/-면서 · -게 · -다가 · -기 · -는/-은, -ㄴ · -을/-ㄹ · -음/-ㅁ · -는군/-군, -는군요, -군요 · -을게/-ㄹ게, -을게요, -ㄹ게요 · -지/-지요(-죠) · -는데요/-ㄴ데요, -은데요 · -네/-네요 · -을래/-을래요, -ㄹ래요 · -게 되다 · -기 때문에/-기 때문이다 · -기로 하다 · -는 것 같다/-ㄴ 것 같다, -은 것 같다, -ㄹ 것 같다, -을 것 같다 · -은 지/-ㄴ 지 · -는 것/-은 것, -ㄴ 것, -을 것, -ㄹ 것 · -는 동안에/-는 동안 · -은 적이 있다/-ㄴ 적이 있다, -은 적이 없다, -ㄴ 적이 없다 · -을 것/-ㄹ 것 · -을 때/-ㄹ 때 · -을까 보다/-ㄹ까 보다 · -어 보다/-아 보다, -여 보다 · -어 있다/-아 있다, -여 있다 · -어 주다/-아 주다, -여 주다 · -어도 되다/-아도 되다, -여도 되다 · -지 말다 · -을 수밖에 없다/-ㄹ 수밖에 없다"""

LEVEL_GRAMMAR_3_4 = """같이 · 이고/고 · 대로 · 으로부터 · 만큼/만치 · 보고 · 뿐 · 아/야 · 요 · 이라고/라고, 이라 · -었었-/-았었-, -였었- · -거든/거들랑 · -는다거나/-ㄴ다거나, -다거나, -라거나 · -는다고/-다고, -라고, -으라고, -자고 · -으나/-나 · -느라고/-느라 · -도록 · -어다가/-아다가, -여다가, -어다 · -어도/-아도, -여도, -라도, 이라도 · -어야/-아야, -여야, -어야만 · -어야지/-아야지, -여야지 · -었더니/-았더니, -였더니 · -자마자/-자 · -으니/-니 · -으려면/-려면 · -던- · -거든요 · -는구나/-구나 · -는다/-ㄴ다, -다 · -던데/-던데요 · -잖아/-잖아요 · -자 · -게 하다/-게 만들다, -도록 하다 · -고 나다 · -고 말다 · -고 싶어 하다 · -은 결과/-ㄴ 결과 · -은 다음에/-ㄴ 다음에 · -는 대신에/-ㄴ 대신에, -은 대신에 · -는 만큼/-ㄴ 만큼, -은 만큼, -ㄹ 만큼, -을 만큼 · -는 반면/-ㄴ 반면에, -은 반면에 · -나 보다 · -을 텐데/-ㄹ 텐데, -을 텐데요 · -기 위해/-기 위해서, -기 위한, 을 위해, 를 위해 · 만 아니면 · -으면 안 되다/-면 안 되다, -으면 되다, -면 되다 · -으면 좋겠다/-면 좋겠다 · -어 가다/-아 가다, -여 가다 · -어 가지고/-아 가지고, -여 가지고 · -어 놓다/-아 놓다, -여 놓다 · -어 두다/-아 두다, -여 두다 · -어 드리다/-아 드리다, -여 드리다 · -어야겠-/-아야겠-, -여야겠- · -어지다/-아지다, -여지다 · 에 대하여/에 대해, 에 대해서, 에 대한 · -을 테니/-ㄹ 테니, -을 테니까, -ㄹ 테니까 · -어 오다/-아 오다, -여 오다 · -기는/-긴, -기는요, -긴요 · -는 모양이다/-ㄴ 모양이다, -은 모양이다 · -는 편이다 · -는가 보다 · -는 중이다 · -으려다가/-려다가, -으려다, 려다 · -어 보이다/-아 보이다, -여 보이다 · 커녕/ㄴ커녕, 는커녕, 은커녕 · 이나마/나마 · 이며/며, 이니, 니, 하며, 하고 · 이든/든, 이든지, 든지, 이든가, 든가 · 이란/란 · 이면/면 · 이야/야 · 치고 · 까지 · 이라도/라도 · 으로서/로서 · 으로써/로써 · 마저 · -거니와 · -고도 · -고자 · -기에 · -는지/-ㄴ지, -은지, -을지 · -다시피 · -더라도 · -든지/-든, -든가 · -으므로/-므로 · -을래야/-ㄹ래야 · -고서/-고서는, -고서야 · -는다면/-ㄴ다면, -다면, -라면 · -더니 · -던데 · -듯이 · -을수록/-ㄹ수록 · -으며/-며 · -는다니/-ㄴ다니, -다니, -라니 · -더군/-더군요 · -더라 · -어라/-아라, -여라 · -게요 · -는다면서/-ㄴ다면서, -다면서, -라면서, -는다면서요, -다면서요, -라면서요 · -나/-나요 · -을걸/-ㄹ걸, -을걸요, -ㄹ걸요 · -어야지요/-아야지요, -여야지요 · -다니요/-라니요 · -을 따름이다/-ㄹ 따름이다, -을 뿐이다, -ㄹ 뿐이다 · -고 들다 · -고 보다 · -고 해서 · -는 김에/-ㄴ 김에, -은 김에 · -는 대로/-ㄴ 대로, -은 대로 · -는 사이에/-는 사이 · -는 듯/-ㄴ 듯, -은 듯, -ㄹ 듯, -을 듯 · -는 줄/-ㄴ 줄, -은 줄, -ㄹ 줄, -을 줄 · -는 탓에/-ㄴ 탓에, -은 탓에, -는 덕분에 · -나 싶다 · -는 바람에 · -는 한 · 으로 인하여/로 인하여, 으로 인해, 로 인해 · 만 같아도 · -어 대다/-아 대다, -여 대다 · -어서인지/-아서인지, -여서인지 · 에 따라/에 따르면 · 에 비하여/에 비하면 · 에 의하여/에 의하면 · -어 버리다/-아 버리다, -여 버리다 · -을 모양이다/-ㄹ 모양이다 · -을 뻔하다/-ㄹ 뻔하다 · -는대/-ㄴ대, -는대요, -대, -대요, -래, -래요, -재, -재요 · -는 통에"""

LEVEL_RULES = f"""
# ★★ 한국어 수준 제약 (국제 통용 한국어 표준 교육과정 — 중급 기준) ★★
- 너의 모든 발화는 한국어 '중급(4급 이하)' 수준에 맞춘다. 이것은 말투 규칙만큼 중요한 최우선 지침이다.
- 어휘: 국제 통용 표준 교육과정 1~4급 범위의 고빈도 일상 어휘만 사용해.
  5급 이상 수준의 저빈도 한자어·전문 용어·속담·사자성어·어려운 관용구는 쓰지 마.
  꼭 필요한 어려운 단어가 나오면 바로 뒤에 쉬운 말로 짧게 풀어줘.
- 문법: 아래 1~4급 문법 목록 안의 문형만 사용해. 목록에 없는 고급 문형(-건대, -노라면, -기 그지없다, -을진대 등)은 금지.
[사용 가능 문법 — 초급(1·2급)]
{LEVEL_GRAMMAR_1_2}
[사용 가능 문법 — 중급(3·4급)]
{LEVEL_GRAMMAR_3_4}
- 한 문장은 짧게, 한 번에 한 가지 내용만. 중급 학습자가 한 번 듣고 이해할 수 있어야 한다.
"""

# ============================================================
# 구어성(입말) 지침 — 이 챗봇의 목표는 '구어 능력' 향상.
# 근거: 정선화(2009)·김현지(2015)·김주연 외(2021)의 구어 문법 요소.
# 단, 음운 변이 표기(축약·경음화·현실음)와 의도적 끼어들기는 구현 제외.
# ============================================================
SPOKEN_RULES = """
# ★ 구어성(입말) 지침 — 문어체가 아니라 진짜 '입말'로 말해 ★
- 담화표지·간투사를 자연스럽게 섞어: "아", "어", "음", "그", "뭐", "좀", "이제", "그니까", "근데", "아 맞다", "있잖아요".
- 맞장구·평가 표지를 자주: "아 그래요?", "진짜요?", "맞아요 맞아요", "그렇죠", "오~ 좋은데요?", "헐".
- 구어 문법을 살려:
  · 조각문 — 완전한 문장 대신 필요한 성분만 ("얼마예요?" → "삼천 원이요.")
  · 생략 — 맥락상 뻔한 주어·조사는 생략 ("(저는) 밥 먹었어요", "커피 좋아해요?")
  · 반복 — 강조·공감의 반복 ("좋아요 좋아요", "네네")
  · 어순 전위 — 뒤에 덧붙이기 ("맛있어요, 거기 떡볶이.")
  · 대용어 — "그거", "거기", "그분" 같은 대명사 활용
  · 머리말·꼬리말 — "있잖아요", "~거든요", "~잖아요", "~더라고요"
- 덩어리 표현(구어 관용 표현)을 중급 수준 안에서: "글쎄요", "그러게요", "아직요", "어떡해요", "잠시만요".
- 문어체 접속어(그러나, 따라서, 및, ~하였다)와 딱딱한 설명조는 금지.
- 단, 발음 변이 표기(줄임·경음화 표기)는 쓰지 말고 표준 표기로. 학습자의 말을 일부러 끊지도 마.
"""


# ============================================================
# 상호작용 대화 능력(IDC, Interactional Dialogue Competence)
# 근거: 이남호(2027) 박사논문 제3장 3절
#   〈표 33〉 IDC의 구성 요소 — 거시 3 · 미시 5 · 기반 1 = 9요소
#   〈표 34〉 구성 요소의 교수 매체 역할 분담 — ◎ AI 담당 / △ AI+교실 / ✕ 교실 전담
#   〈표 42〉 상호작용 대화 수행의 평가 범주와 중급 평가 기준
#
# 설계의 전제(2.1 사회구성주의):
#   챗봇은 대화 상대가 아니라 '더 유능한 타인(More Knowledgeable Other)'이다.
#   따라서 각 요소를 ① 시범 보이고(모델링) ② 실현할 자리를 만들고(촉진)
#   ③ 학습자가 스스로 하게 되면 물러난다(자율) — 근접발달영역 안의 비계와 페이딩.
#
# media 값의 뜻
#   "ai"    ◎ — 학습자가 발휘할 수 있고 AI가 그 발휘를 유발·수용한다. 유발 대상.
#   "both"  △ — AI에서 대안적 형태로만 실현된다. 대안 형태만 유발하고 교실이 보완.
#   "class" ✕ — AI 대화에서 실현 불가. 유발하지 않고 총점에서도 제외(교실 도입 담당).
# ============================================================
IDC_ELEMENTS = [
    {
        "key": "stage", "layer": "macro", "media": "ai",
        "name": "기능 단계의 조직과 흐름",
        "sub": "시작·전개·마무리 단계의 조직",
        # MKO의 유발 — 이 요소가 학습자에게서 나오게 만드는 상대의 행동
        "elicit": "학습자가 단계를 건너뛰면 그 단계가 필요해지는 자리를 역할 안에서 만들어 되돌려라. "
                  "예) 값을 묻지 않고 사겠다고 하면 \"결제부터 도와드릴까요?\" 대신 \"가격은 확인하셨어요?\". "
                  "단계 이름을 입에 올리는 것은 절대 금지.",
        "model": "네가 먼저 그 단계의 발화를 한 번 보여 주고(예: 마무리라면 \"오늘 도와드려서 좋았어요\"), 학습자가 같은 자리에서 이어받게 하라.",
        "criteria": "대화 목적 달성에 필요한 기능 단계(시작-전개-마무리)를 생략 없이 실현하여 과업을 완수할 수 있다. "
                    "대화의 목적을 이루기 위한 시도를 단계에 맞게 이어 갈 수 있다(과업 완성의 정도성).",
    },
    {
        "key": "topic", "layer": "macro", "media": "ai",
        "name": "화제 관리",
        "sub": "화제의 개시·확장·전환·마무리",
        "elicit": "목적이 이루어져도 대화를 닫지 말고 새 화제로 옮길 여지를 한 번 열어 둬라. "
                  "\"그럼 이제 뭐 하실 거예요?\"처럼 열린 자리를 만들고 기다려라. "
                  "학습자가 화제를 열거나 옮기면 반드시 그 화제를 따라가라. 네가 화제를 독점하지 마라.",
        "model": "네가 관련된 화제로 한 걸음 옮겨 보이고(\"아 그러고 보니…\"), 바로 학습자에게 되돌려라.",
        "criteria": "대화의 주제를 자연스럽게 도입할 수 있다. "
                    "필요에 따라 새로운 주제로 옮기거나 본래의 주제로 돌아올 수 있다.",
    },
    {
        "key": "move", "layer": "macro", "media": "ai",
        "name": "대화이동 관리",
        "sub": "시작·역시작·수정·고수 등 화행 연쇄의 운용",
        "elicit": "학습자의 시작 대화이동에 늘 순순히 응하지 마라. 역할에 맞는 범위에서 가끔 역시작(되묻기)이나 "
                  "조건 제시를 넣어, 학습자가 후속 대화이동(재요청·수정·고수)을 배치할 자리를 만들어라. "
                  "예) \"지금은 자리가 없는데요\" → 학습자가 다시 협상하게.",
        "model": "네가 되묻기 한 번을 보여 주고, 학습자가 그에 대응하는 발화를 할 때까지 기다려라.",
        "criteria": "의사소통 목적에 적절한 화행을 선택하여 시작 대화이동을 수행할 수 있다. "
                    "상대 반응에 따라 후속 대화이동을 배치하며 대화의 흐름을 조율할 수 있다.",
    },
    {
        "key": "turn", "layer": "micro", "media": "ai",
        "name": "차례 관리",
        "sub": "차례의 요구·유지·양보 (끼어들기는 교실 담당)",
        "elicit": "네 발화는 짧게 끊고 말차례를 넘겨라. 학습자가 말을 이어 가려는 기색이면 채우지 말고 기다려라. "
                  "학습자가 짧게만 답하고 넘기면 \"그래서요?\", \"더 얘기해 주세요\"로 차례를 되돌려 주되 대신 말하지 마라. "
                  "네가 두 문장을 넘기면 실패다.\n"
                  "★차례 넘기기 — 학습자가 할 말을 다 하고도 문장을 안 맺고 흐리면(\"음… 그래서…\") "
                  "네가 이어받지 말고 한 박자 기다려 스스로 맺게 하라. 맺고 나면 그때 받아라.",
        "model": "채움말로 차례를 유지하는 법을 짧게 보여 줘라(\"음… 그러니까요…\"). 그 뒤에는 학습자 차례로 넘겨라.",
        "criteria": "말차례의 기회를 주고받으며 대화를 균형 있게 운영할 수 있다. "
                    "대화를 독점하거나 수동적인 태도를 보이지 않고 대화를 유지할 수 있다. "
                    "자기 말을 끝까지 맺고 상대에게 차례를 넘길 수 있다.",
    },
    {
        "key": "repair", "layer": "micro", "media": "ai",
        "name": "의사소통 단절 수정",
        "sub": "자기 수정·명료화 요구·명료화 응답·발화 공동 완성",
        "elicit": "학습자의 발화가 모호하거나 어긋나면 넘겨짚어 대답하지 말고 역할 안에서 되물어라 "
                  "— 학습자가 스스로 고칠 자리가 여기서 생긴다. 예) \"두 개요? 아니면 두 인분이요?\". "
                  "★단, 일부러 어렵게 말하거나 알아듣고도 못 알아들은 척하지는 마라. 그건 학습이 아니라 방해다.",
        "model": "네가 먼저 명료화 요구를 시범 보여 주고(\"죄송한데 한 번만 더 말씀해 주시겠어요?\"), "
                 "학습자가 못 알아들은 눈치일 때 같은 표현을 쓸 수 있게 하라.\n"
                 "★발화 공동 완성 — 학습자의 말이 조각으로 끊기면(\"바나… 먹어…\") 틀렸다고 하지 말고 "
                 "네가 뜻을 이어 완성해 준 뒤 학습자가 그 문장을 스스로 말하게 하라. "
                 "예) \"아, 바나나가 먹고 싶다고요? '바나나가 먹고 싶어요' 해 볼래요?\" "
                 "따라 말하면 그것으로 통과다 — 대신 말해 준 것이 아니라 함께 만든 것이다.",
        "criteria": "의사소통이 단절되었을 때 자기 교정이나 명료화 요구로 대화를 복원할 수 있다. "
                    "상대방이 자신의 발화를 이해하지 못한 경우 다른 표현을 사용해 이야기할 수 있다. "
                    "상대가 되물으면 알아듣게 다시 말할 수 있고, 상대가 이어 준 문장을 받아 스스로 완성할 수 있다.",
    },
    {
        "key": "strategy", "layer": "micro", "media": "ai",
        "name": "의사소통 전략",
        "sub": "우회 표현·모국어 전환·따라 말하기·지연/회피",
        "elicit": "학습자가 단어를 못 찾아 머뭇거려도 곧바로 답을 주지 마라. 한 박자 기다려서 "
                  "학습자가 우회 표현이나 지연 표현(\"그… 뭐지…\")을 스스로 쓰게 하라. "
                  "학습자가 우회해서 말해 내면 먼저 알아들었다고 받아 준 뒤에 정확한 표현을 알려 줘라.\n"
                  "★모국어 전환 — 우회로도 안 풀려 두 번 넘게 막히면, 답을 주지 말고 모국어로 말해 보라고 권하라. "
                  "예) \"{native}로 말해 봐도 돼요. 제가 한국어로 알려 드릴게요.\" "
                  "모국어로 말하면 그 뜻을 한국어 한 문장으로 바꿔 주고 따라 말하게 하라. "
                  "모국어를 쓰는 것은 회피가 아니라 대화를 잇는 전략이다 — 나무라지 마라.\n"
                  "★따라 말하기 — 네가 방금 쓴 표현을 학습자가 가져다 쓰면 짧게 짚어 줘라. "
                  "예) \"오, 방금 제가 쓴 말 그대로 쓰셨네요. 좋아요.\"",
        "model": "우회 표현을 한 번 시범 보여라(\"이름이 기억이 안 나는데, 매운 국물 있는 거요\"). "
                 "학습자가 쓸 만한 표현은 네 발화 안에 미리 흘려 두어, 학습자가 그것을 가져다 쓸 수 있게 하라.",
        "criteria": "모르는 표현을 우회 표현이나 대체 표현으로 보상하며 대화를 지속할 수 있다. "
                    "즉각적인 응답이 어려울 때 도움 요청이나 지연 표현으로 대화의 중단을 피할 수 있다. "
                    "막혔을 때 모국어나 상대의 표현을 빌려서라도 대화를 이어 갈 수 있다.",
    },
    {
        "key": "listen", "layer": "micro", "media": "ai",
        "name": "상호작용적 듣기",
        "sub": "맞장구·반응 발화, 이해 확인 (실시간 동시 맞장구는 교실 담당)",
        "elicit": "학습자가 반응할 만한 것을 던져 맞장구의 자리를 만들어라 — 놀랄 만한 소식, 공감할 만한 사정. "
                  "예) \"오늘 이거 마지막 하나예요!\". 학습자가 아무 반응 없이 다음 말로 넘어가면 "
                  "다음 차례에서 네가 짧게 시범을 보여라.",
        "model": "\"아 진짜요?\", \"맞아요 맞아요\", \"그렇구나\" 같은 반응 표현을 네 발화에 섞어 들려주어라.",
        "criteria": "'그럼요', '진짜요', '맞아요' 등 구어에서 자주 쓰이는 반응 표현을 사용해 상대방의 발화에 "
                    "동의하거나 이해를 표현할 수 있다. 상대방의 발화에 대한 이해 여부를 언어적으로 확인하며 들을 수 있다.",
    },
    {
        "key": "nonverbal", "layer": "micro", "media": "class",
        "name": "비언어적 행위",
        "sub": "시선·표정·제스처·자세, 고개 끄덕임",
        "elicit": "",   # ✕ — 유발하지 않는다
        "model": "",
        "criteria": "시선·표정·고개 끄덕임으로 상대의 발화에 반응할 수 있다. "
                    "대화의 시작과 종결을 비언어적 신호로 함께 표시할 수 있다. "
                    "※ 교실 도입 단계에서 다루며 챗봇 연습에서는 훈련되지 않는다. 관찰·기록하되 총점에는 산입하지 않는다.",
    },
    {
        "key": "context", "layer": "base", "media": "ai",
        "name": "맥락·정체성 인식",
        "sub": "역할·관계의 인식과 레지스터의 선택",
        "elicit": "너는 배역과 관계를 끝까지 일관되게 유지하라 — 네가 흔들리면 학습자가 맞출 기준이 사라진다. "
                  "학습자가 관계에 맞지 않는 레지스터를 쓰면(처음 보는 점원에게 반말 등) 역할 안에서 "
                  "가볍게 드러내라. 예) 살짝 당황한 기색이나 \"어… 네?\". 훈계는 하지 마라.",
        "model": "그 관계에 맞는 말투를 네 발화로 또렷이 들려주어 학습자가 맞출 기준을 갖게 하라.",
        "criteria": "참여자의 역할과 사회적 관계에 맞는 레지스터를 선택할 수 있다. "
                    "격식적 상황과 비격식적 상황을 구분하여 대화할 수 있다.",
    },
]

IDC_BY_KEY = {e["key"]: e for e in IDC_ELEMENTS}
# 유발·평가 대상 = 교실 전담(✕)을 뺀 나머지. 총점도 이 요소들로만 낸다.
IDC_TRAINABLE = [e for e in IDC_ELEMENTS if e["media"] != "class"]

# ── 오늘의 퀘스트 가운데 '세는 것'만으로는 판정할 수 없는 것들 ──
# 로그의 낱말만 봐서는 알 수 없고 대화의 흐름을 읽어야 하는 행동이다.
# 진행률 분석과 같은 호출에서 함께 판정한다(따로 부르면 비용·지연이 두 배).
# 모두 논문 3.3 IDC 요소 안에 있다.
QUEST_LLM = [
    {"id": "qRefuse",  "el": "move",     "desc": "상대의 제안·요청을 완곡하게라도 거절한 적이 있다"},
    {"id": "qAlt",     "el": "move",     "desc": "거절하거나 곤란할 때 다른 방법·대안을 스스로 제안한 적이 있다"},
    {"id": "qCond",    "el": "move",     "desc": "'~하면 ~할게요'처럼 조건을 붙여 협상한 적이 있다"},
    {"id": "qHold",    "el": "move",     "desc": "상대가 한 번 거절·난색을 보였는데도 물러서지 않고 다시 요청한 적이 있다"},
    {"id": "qCircum",  "el": "strategy", "desc": "낱말이 떠오르지 않을 때 다른 말로 돌려 설명한 적이 있다"},
    {"id": "qReturn",  "el": "topic",    "desc": "다른 화제로 옮겼다가 원래 화제로 스스로 돌아온 적이 있다"},
    {"id": "qNewTopic","el": "topic",    "desc": "과업과 별개로 새로운 화제를 스스로 꺼낸 적이 있다"},
    {"id": "qSelfFix", "el": "repair",   "desc": "말하다가 스스로 틀린 것을 알아채고 고쳐 말한 적이 있다"},
    # ── v95: 요소별 공백 메우기 ──
    # 기존 여덟은 대화이동(4)·화제(2)·전략(1)·수정(1)에 몰려 있어, 듣기·차례에는
    # LLM이 읽어야만 알 수 있는 퀘스트가 하나도 없었다. 아래 여섯으로 여덟 요소를 모두 덮는다.
    {"id": "qParaphrase", "el": "listen",   "desc": "상대의 말을 자기 말로 바꾸어 '그러니까 ~라는 말이죠?'처럼 확인한 적이 있다"},
    {"id": "qRephrase",   "el": "repair",   "desc": "상대가 알아듣지 못했을 때 같은 뜻을 다른 표현으로 바꾸어 다시 말한 적이 있다"},
    {"id": "qNative",     "el": "strategy", "desc": "막혔을 때 모국어로 말해 보고, 상대가 알려 준 한국어로 다시 말한 적이 있다"},
    {"id": "qEcho",       "el": "strategy", "desc": "상대가 방금 쓴 표현을 가져다 자기 발화에 쓴 적이 있다"},
    {"id": "qEndTurn",    "el": "turn",     "desc": "말끝을 흐리지 않고 문장을 끝까지 맺어 차례를 넘긴 적이 있다"},
    {"id": "qExpand",     "el": "topic",    "desc": "상대가 꺼낸 화제에 자기 이야기를 얹어 넓힌 적이 있다"},
]

# ── 대화 중 '교육적 개입'으로 띄울 수 있는 퀘스트 ──
# 논문 4.2.3의 비계 층위를 하나 늘린 것이다. 지금까지 챗봇은 '자리를 만들고 기다리는'
# 유발까지만 했고, 그것이 먹히지 않으면 다음 손길은 대화가 끝난 뒤의 사후 피드백뿐이었다.
# 개입은 그 사이를 메운다 — 그 자리에서, ★기능만 알려 주고 표현은 주지 않는다.
#   예) "지금이에요! 한 번 거절해 보기"
# 표현이 필요하면 학습자가 🪜 도움말을 눌러 요청한다(비계는 요청 시 · 맥락에 맞게).
# 챗봇이 형식까지 미는 자리는 두지 않는다 — 타이밍과 형식을 모두 주면 받아쓰기가 된다.
# qSelfFix는 제외한다. 자기 수정은 시켜서 하면 자기 수정이 아니다.
INTERVENABLE = {q["id"] for q in QUEST_LLM} - {"qSelfFix"}

# 개입 빈도 — 페이더(0~3)로 학습자가 조절한다. 0이면 개입하지 않는다.
INTV_MAX = {0: 0, 1: 2, 2: 4, 3: 7}      # 세션당 최대 횟수
INTV_GAP = {0: 0, 1: 150, 2: 90, 3: 50}  # 개입 사이 최소 간격(초)
IDC_SCORED_KEYS = [e["key"] for e in IDC_TRAINABLE]
# 발화 연습(한 차례 주고받기)으로 실제로 기를 수 있는 요소만.
# 'stage'(기능 단계의 조직)는 대화 전체의 흐름이라 한 문장 연습의 목표가 될 수 없다.
EXPR_IDC_KEYS = [k for k in IDC_SCORED_KEYS if k != "stage"]
_QUEST_IDS = {q["id"] for q in QUEST_LLM}

# 비계 수준 — 실현 횟수에 따라 3 → 2 → 1로 내려간다(페이딩).
IDC_LEVEL_MODEL = 3    # 모델링: 네가 시범을 보이고 학습자가 이어받게 한다
IDC_LEVEL_PROMPT = 2   # 촉진: 자리만 만들고 기다린다
IDC_LEVEL_SOLO = 1     # 자율: 개입하지 않는다
IDC_FADE_AT = {IDC_LEVEL_MODEL: 1, IDC_LEVEL_PROMPT: 3}  # 실현 횟수 임계치


def idc_focus_block(levels: dict, counts: dict, limit: int = 3, native: str = "") -> str:
    """지금 이 학습자에게 필요한 요소만 골라 유발 지시를 만든다.
    아직 안 나온 요소(모델링) → 한 번 나온 요소(촉진) 순으로 최대 limit개.
    이미 여러 번 실현된 요소는 지시에서 빼서 비계를 걷어 낸다."""
    ranked = sorted(
        (e for e in IDC_TRAINABLE if levels.get(e["key"], IDC_LEVEL_MODEL) > IDC_LEVEL_SOLO),
        key=lambda e: (counts.get(e["key"], 0), IDC_SCORED_KEYS.index(e["key"])),
    )[:limit]
    if not ranked:
        return ("\n[지금의 비계 수준] 학습자가 목표 요소들을 스스로 실현하고 있다. "
                "이제 유발을 멈추고 자연스러운 대화 상대로만 있어라. 도움은 학습자가 요청할 때만.\n")
    lines = []
    for e in ranked:
        lv = levels.get(e["key"], IDC_LEVEL_MODEL)
        # {native}는 학습자가 고른 모국어 이름으로 바꾼다 — 코드 전환을 권할 때 쓰인다
        nat = native or "학습자의 모국어"
        model_t, elicit_t = e["model"].replace("{native}", nat), e["elicit"].replace("{native}", nat)
        if lv >= IDC_LEVEL_MODEL:
            lines.append(f"- [{e['name']} · 시범] {model_t} {elicit_t}")
        else:
            lines.append(f"- [{e['name']} · 자리 만들기] {elicit_t}")
    return "\n[지금 이 학습자에게 필요한 것 — 이 셋만 신경 써라]\n" + "\n".join(lines) + "\n"


def build_mko_block(levels: dict | None = None, counts: dict | None = None, native: str = "") -> str:
    """호아랑을 '더 유능한 타인'으로 규정하는 블록.
    levels/counts가 없으면(대화 시작 시점) 모든 요소가 모델링 수준에서 출발한다."""
    levels = levels or {}
    counts = counts or {}
    return f"""

# ★★★ 너의 교육적 위치 — 더 유능한 타인(비고츠키) ★★★
너는 그냥 대화 상대가 아니다. 학습자보다 한국어 대화를 더 잘하는 '더 유능한 타인'이다.
학습자 혼자서는 아직 못 하지만 너와 함께라면 해낼 수 있는 것 — 그 자리가 네가 일할 곳이다.
네가 할 일은 대화를 잘 굴리는 게 아니라, 학습자가 다음의 상호작용을 **직접 해내게** 만드는 것이다.

[변하지 않는 원칙]
① 학습자가 할 수 있는 것을 네가 대신하지 마라. 학습자의 몫을 가져가는 순간 연습은 사라진다.
   - 학습자가 물어야 할 것을 네가 먼저 알려주지 마라.
   - 학습자가 끝내야 할 대화를 네가 끝내지 마라.
   - 학습자가 고를 것을 네가 골라 주지 마라.
② 학습자의 발화가 두 어절 이하이거나 뜻이 흐리면 **반드시 되물어라**. 넘겨짚어 대답하는 순간
   학습자는 명료화에 응답할 기회를 잃는다. ("뭐를 말씀하시는 거예요?", "○○요? 아니면 ○○요?")
③ 학습자가 말을 고르느라 침묵하면 채우지 말고 3초쯤 기다려라. 그래도 막히면 답이 아니라
   채움말을 권하라 — "'음…', '그러니까…' 하면서 천천히 생각해도 돼요."
④ 도움은 필요한 만큼만, 그리고 점점 줄여라. 학습자가 한 번 해낸 것은 다음부터 도와주지 마라.
⑤ 못 하는 것은 어려운 말로 밀어붙여서가 아니라, 그것이 필요해지는 '자리'를 만들어서 끌어내라.
⑥ 학습자가 스스로 해내면 그 순간을 짧게 짚어 줘라. 다만 수업하듯 설명하지는 마라.
   예) "오 지금 그거 좋았어요!" 한 마디면 충분하다.
⑦ 위 원칙과 배역 연기가 부딪히면 배역 안에서 푸는 길을 찾아라. 극을 깨고 선생님으로 나오지 마라.
{idc_focus_block(levels, counts, native=native)}
[하지 말 것]
- 요소 이름("맞장구", "명료화 요구", "기능 단계")을 학습자에게 말하지 마라. 대화 밖으로 나가는 순간 극이 깨진다.
- 유발한다고 일부러 어렵게 말하거나, 알아들은 척·못 알아들은 척 연기하지 마라.
- 한 턴에 여러 요소를 한꺼번에 끌어내려 하지 마라. 한 턴에 하나면 충분하다.
"""


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
    return BASE_PERSONA + LEVEL_RULES + SPOKEN_RULES + name_hint + native_hint + coord + D_RULES[d_band] + sep + P_RULES[p_band] + sep + fusion


# ============================================================
# 주제 대화(상황극) 모드 — 기능단계 기반 대화 연습
# 근거: 이남호·차준우(2023) 프롬프트 정보 구조, 이남호·이찬규(2024) 대화연습 모형,
#       이남호·이찬규(2025) 기능단계 분석, 이남호(2025) 확장 검증
# 흐름: ① 학습자가 주제·목적 등을 (모국어로도) 입력 → ② 서버가 기능단계+표현 생성
#       → ③ 상황극 진행, 턴마다 단계 충족을 분석해 진행률 전송(100% 초과 허용)
#       → ④ 학습자가 종료 버튼 → 진행률을 점수로 치환 + 대화 저장
# ============================================================
# 계획 생성·추천·단계 분석용 모델.
# ※ 2026-07 확인: gemini-2.5-flash-lite는 신규 사용자에게 404(제공 종료).
#   결제(Tier 1) 연결 후에는 gemini-2.5-flash 쿼터가 충분하므로 기본값으로 사용.
# 사용 중 모델이 404(단종)가 되면 아래 후보 목록 → API 모델 목록 순으로 자동 전환.
# Render 환경변수 ANALYSIS_MODEL로 언제든 고정 가능.
ANALYSIS_MODEL = os.environ.get("ANALYSIS_MODEL", "").strip() or "gemini-2.5-flash"
_analysis_model = {"name": ANALYSIS_MODEL}   # 현재 실사용 모델 (404 시 자동 갱신)
_MODEL_FALLBACKS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]
_tried_models = set()
_roleplay_plans = {}  # plan_id -> {"plan": dict, "style": str, "at": float}

# 마지막 생성 호출 오류 기록 — 실패 원인을 클라이언트 팝업과 /rp-diag에 그대로 노출
LAST_GEN_ERROR = {"at": "", "msg": ""}


def _note_gen_error(e) -> None:
    LAST_GEN_ERROR["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    LAST_GEN_ERROR["msg"] = (f"{type(e).__name__}: {e}" if not isinstance(e, str) else e)[:300]


def _quota_exhausted() -> bool:
    """직전 실패가 API 쿼터 소진(429)이었는지 — 이때 재시도는 쿼터만 2배로 태운다."""
    m = LAST_GEN_ERROR["msg"]
    return "429" in m or "RESOURCE_EXHAUSTED" in m


def _model_not_found() -> bool:
    """직전 실패가 '모델 없음/단종'(404 NOT_FOUND)이었는지."""
    m = LAST_GEN_ERROR["msg"]
    return "NOT_FOUND" in m or ("404" in m and "model" in m.lower())


def _fail_reason(data) -> str:
    """502 detail에 담을 사람이 읽을 수 있는 실패 원인."""
    if data is not None:
        return "모델이 형식에 맞지 않는 응답을 반환"
    if _quota_exhausted():
        return "Gemini API 사용량(쿼터) 초과 — 잠시 후 다시 시도 (429)"
    if _model_not_found():
        return "분석용 모델 사용 불가(404) — 자동 전환도 실패. /rp-diag?models=1 에서 사용 가능 모델 확인"
    return LAST_GEN_ERROR["msg"] or "원인 미기록"


async def _next_model(bad: str) -> str | None:
    """단종된 모델 대신 쓸 다음 후보. 후보가 다 막히면 API 모델 목록에서 flash 계열 탐색."""
    _tried_models.add(bad)
    for c in _MODEL_FALLBACKS:
        if c not in _tried_models:
            return c
    try:
        lst = client.aio.models.list()
        if hasattr(lst, "__await__"):
            lst = await lst
        names = []
        async for m in lst:
            n = (getattr(m, "name", "") or "").replace("models/", "")
            acts = list(getattr(m, "supported_actions", None) or [])
            if n and (not acts or "generateContent" in acts):
                names.append(n)
        flash = sorted(
            (n for n in names
             if "flash" in n and not any(x in n for x in ("live", "audio", "tts", "image", "exp", "8b", "lite"))),
            reverse=True)
        for n in flash:
            if n not in _tried_models:
                return n
    except Exception as e:
        print(f"[상황극] 모델 목록 조회 실패: {e}")
    return None
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


async def _gen_json(prompt: str, timeout_s: float = 20.0, temperature: float = 0.3):
    """일회성 생성 호출 → JSON 파싱. 실패 시 None (호출부에서 처리).
    ★ 2.5 모델은 '동적 사고(thinking)'가 기본 활성화라 복잡한 프롬프트에서
      응답 전에 수십 초씩 생각하다 타임아웃될 수 있다 → thinking_budget=0으로 즉답."""
    async def _call(model_name: str):
        try:
            cfg = types.GenerateContentConfig(
                response_mime_type="application/json", temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0))
            resp = await client.aio.models.generate_content(
                model=model_name, contents=prompt, config=cfg)
        except Exception as e1:
            if "NOT_FOUND" in str(e1) or "404" in str(e1):
                raise  # 모델 자체가 없음 — 같은 모델로 재호출해 봐야 낭비
            print(f"[상황극] thinking 끈 JSON 호출 실패 — 기본 설정 폴백: {e1}")
            try:
                cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
                resp = await client.aio.models.generate_content(
                    model=model_name, contents=prompt, config=cfg)
            except (TypeError, AttributeError):
                # 구버전 SDK 폴백 — JSON 모드 미지원이면 텍스트로 받고 관대 파싱
                resp = await client.aio.models.generate_content(model=model_name, contents=prompt)
        return _parse_json_loose(getattr(resp, "text", "") or "")

    # 모델이 단종(404)이면 후보로 갈아타며 최대 3개 모델까지 시도
    for _ in range(3):
        model_name = _analysis_model["name"]
        try:
            return await asyncio.wait_for(_call(model_name), timeout=timeout_s)
        except asyncio.TimeoutError:
            print(f"[상황극] 생성 호출 타임아웃 ({timeout_s}s)")
            _note_gen_error(f"Timeout: 모델 응답이 {timeout_s:.0f}초를 초과")
            return None
        except Exception as e:
            print(f"[상황극] 생성 호출 실패({model_name}): {e}")
            _note_gen_error(e)
            if _model_not_found():
                nxt = await _next_model(model_name)
                if nxt:
                    print(f"[상황극] 모델 자동 전환: {model_name} → {nxt}")
                    _analysis_model["name"] = nxt
                    continue
            return None
    return None


def _clean_str(v, limit: int) -> str:
    if not isinstance(v, str):
        return ""
    return re.sub(r"\s+", " ", v).strip()[:limit]


def _normalize_expr(e) -> dict | None:
    """표현 항목 정규화 — 신형 {"text","cue","follow"} / 구형 "문자열" 모두 수용.
    cue    = text 앞에 올 상대 발화 (비어 있으면 학습자가 먼저 말하는 자리)
    follow = text 뒤에 올 상대의 반응 (3항 연속체일 때만)"""
    if isinstance(e, dict):
        text = _clean_str(e.get("text"), 60)
        cue = _clean_str(e.get("cue"), 60)
    else:
        text, cue = _clean_str(e, 60), ""
    follow = _clean_str(e.get("follow"), 60) if isinstance(e, dict) else ""
    # 발화 연습은 한 차례의 주고받기를 익히는 자리다. '기능 단계'는 대화 전체의
    # 조직이라 한 문장 연습으로 기를 수 없다 — 태그로 붙으면 학습자에게 거짓말이 된다.
    idc = e.get("idc") if isinstance(e, dict) and e.get("idc") in EXPR_IDC_KEYS else ""
    if not idc:
        idc = "move"          # 기본은 대화이동 관리
    return {"text": text, "cue": cue, "follow": follow, "idc": idc} if text else None


def _validate_script(raw, n_stages: int) -> list:
    """모델 대화문 정리 — 교실 '도입'의 모델 대화 관찰 자료(3.4.2).
    한 줄이라도 어긋나면 그 줄만 버리고, 전체가 너무 짧으면 빈 목록으로 돌려
    클라이언트가 듣기 단계를 건너뛰게 한다(대화 자체는 그대로 진행)."""
    if not isinstance(raw, list):
        return []
    lines = []
    for it in raw[:16]:
        if not isinstance(it, dict):
            continue
        text = _clean_str(it.get("text"), 90)
        if not text:
            continue
        who = "user" if str(it.get("speaker", "")).lower().startswith("u") else "ai"
        st = _clamp_int(it.get("stage"), 0, max(0, n_stages - 1), 0)
        lines.append({"speaker": who, "text": text,
                      "native": _clean_str(it.get("native"), 110), "stage": st})
    # 양쪽이 최소 두 번씩은 말해야 '대화문'이라 할 수 있다
    if len(lines) < 6 or sum(1 for l in lines if l["speaker"] == "user") < 2:
        return []
    return lines


# ── 말투 섞임 검사 ──
# 한 화자가 한 대화 안에서 존댓말과 반말을 오가면 학습자가 배울 본이 되지 못한다.
# 문장 끝만 보고 판정한다(형태소 분석 없이도 종결어미로 충분히 갈린다).
# 존댓말 종결: -요 / -ㅂ니다 / -습니까 / -세요 / -십시오 / -지요 …
# 반말 종결:   -야 / -어 / -아 / -지 / -니 / -냐 / -데 / -래 / -자 / -군 / -네 …
# ※ "네", "응", "어" 처럼 그 자체가 대답인 한 마디는 판정하지 않는다.
_ONE_WORD = {"네", "예", "응", "어", "아", "음", "그래", "글쎄", "야"}


def _speech_level(text: str) -> str:
    """한 발화의 말투 — "polite" / "banmal" / "" (판정 불가).
    형태소 분석 없이 마지막 어절의 종결형만 본다. 종결어미만으로 충분히 갈린다."""
    t = (text or "").strip().rstrip("!?.…~♪ ")
    if not t:
        return ""
    # 마지막 문장만 본다("네, 그럼요. 무슨 일이에요?" → "무슨 일이에요")
    for sep in (". ", "? ", "! ", "…"):
        if sep in t:
            t = t.split(sep)[-1].strip().rstrip("!?.…~ ")
    if not t or t in _ONE_WORD:
        return ""
    for e in ("요", "니다", "니까", "세요", "십시오", "ㅂ니다"):
        if t.endswith(e):
            return "polite"
    for e in ("야", "어", "아", "지", "니", "냐", "데", "래", "자", "군", "네",
              "거든", "잖아", "구나", "든지", "든가", "니까"):
        if t.endswith(e):
            return "banmal"
    return ""


def _style_offenders(script: list, want_user: str, want_ai: str) -> list:
    """정해 둔 말투를 어긴 줄의 번호를 돌려준다.
    '섞였는가'만 보면 한쪽으로 통일된 채 설정과 어긋난 경우를 놓친다.
    화자마다 쓸 말투를 미리 정해 두고 줄마다 대조한다."""
    bad = []
    for i, l in enumerate(script or []):
        lv = _speech_level(l.get("text", ""))
        if not lv:
            continue
        want = want_user if l.get("speaker") == "user" else want_ai
        if lv != want:
            bad.append(i)
    return bad


def _link_expr_to_script(stages: list, script: list) -> None:
    """발화 연습의 cue·follow를 실제 대화문에서 끌어온다.
    학습자가 '먼저 듣기'에서 들은 흐름과 연습이 어긋나면 두 활동이 따로 논다.
    표현의 text와 가장 비슷한 학습자 줄을 찾아, 그 앞뒤 상대 발화를 cue·follow로 삼는다."""
    import difflib
    if not script:
        return
    for si, st in enumerate(stages):
        for e in st.get("expressions") or []:
            best, score = -1, 0.0
            for i, l in enumerate(script):
                if l["speaker"] != "user":
                    continue
                r = difflib.SequenceMatcher(None, e["text"], l["text"]).ratio()
                if l["stage"] == si:
                    r += 0.15          # 같은 단계면 우선
                if r > score:
                    best, score = i, r
            if best < 0 or score < 0.45:
                continue               # 대화문에 없는 표현은 그대로 둔다
            prev = script[best - 1] if best > 0 else None
            nxt = script[best + 1] if best + 1 < len(script) else None
            e["cue"] = prev["text"] if (prev and prev["speaker"] == "ai") else ""
            if e.get("follow"):
                e["follow"] = nxt["text"] if (nxt and nxt["speaker"] == "ai") else ""


async def _fix_style(plan: dict, want_user: str, want_ai: str) -> None:
    """말투를 어긴 줄만 골라 그 줄만 고쳐 쓴다.
    통째로 다시 만들면 20초가 더 들고, 다시 만든 것도 어긋날 수 있다.
    어긴 줄이 몇 줄뿐이면 그 줄만 손질하는 편이 빠르고 확실하다."""
    script = plan.get("script") or []
    bad = _style_offenders(script, want_user, want_ai)
    if not bad or len(bad) > 8:
        return
    ko = {"polite": "존댓말(해요체, '-요/-습니다'로 끝남)", "banmal": "반말(해체, '-아/-어/-야'로 끝남)"}
    lines = "\n".join(
        f"{i}\t{script[i]['text']}\t→ {ko[want_user if script[i]['speaker'] == 'user' else want_ai]}"
        for i in bad)
    prompt = f"""아래는 한국어 교재의 모델 대화문 가운데 **말투가 어긋난 줄**이다.
뜻은 그대로 두고 **말투만** 바꿔 다시 써라. 낱말을 새로 지어내지 마라.

번호\t원래 문장\t고칠 말투
{lines}

- 한 줄에 한 문장. 중급(4급 이하) 어휘·문법.
- 구어체를 유지하라. 담화표지("아", "음", "그럼")는 그대로 두어도 된다.

JSON만 출력: {{"fixed":[{{"i":번호,"text":"고친 문장"}}]}}"""
    try:
        data = await _gen_json(prompt, timeout_s=15.0)
    except Exception as e:
        print(f"[상황극] 말투 손질 실패: {e}")
        return
    if not isinstance(data, dict):
        return
    for it in (data.get("fixed") or []):
        if not isinstance(it, dict):
            continue
        i = _clamp_int(it.get("i"), 0, len(script) - 1, -1)
        t = _clean_str(it.get("text"), 90)
        if i >= 0 and t:
            script[i]["text"] = t
    left = _style_offenders(script, want_user, want_ai)
    print(f"[상황극] 말투 손질: {len(bad)}줄 중 {len(bad) - len(left)}줄 고침")
    # 대화문이 고쳐졌으니 발화 연습의 cue·follow도 다시 붙인다
    _link_expr_to_script(plan.get("stages") or [], script)


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
        exprs = [x for x in (_normalize_expr(e) for e in (s.get("expressions") or [])) if x][:3]
        stages.append({
            "name": name,
            "native": _clean_str(s.get("native"), 60),
            "desc": _clean_str(s.get("desc"), 100),
            "expressions": exprs,
        })
    if len(stages) < 3:
        return None
    script = _validate_script(data.get("script"), len(stages))
    # 발화 연습을 대화문에 붙인다 — 들은 것과 연습하는 것이 같아야 한다
    _link_expr_to_script(stages, script)
    return {
        "topic_ko": _clean_str(data.get("topic_ko"), 60) or "자유 주제",
        "goal_ko": _clean_str(data.get("goal_ko"), 100) or "대화 목적 달성",
        "place_ko": _clean_str(data.get("place_ko"), 60) or "일상 공간",
        "user_role": _clean_str(data.get("user_role"), 40) or "학습자",
        "ai_role": _clean_str(data.get("ai_role"), 40) or "대화 상대",
        "stages": stages,
        "script": script,
    }


def _clamp_int(v, lo: int, hi: int, default: int) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _validate_suggest(data) -> dict | None:
    """주제 기반 자동 추천 JSON 정리. goals는 교재형→일상형→엉뚱형 3개 보장."""
    if not isinstance(data, dict):
        return None
    goals = [_clean_str(g, 100) for g in (data.get("goals") or []) if _clean_str(g, 100)][:3]
    if len(goals) < 3:
        return None
    style = data.get("style") if data.get("style") in ("polite", "banmal") else "polite"
    return {
        "goals": goals,
        "place": _clean_str(data.get("place"), 60),
        "my_role": _clean_str(data.get("my_role"), 40),
        "ai_role": _clean_str(data.get("ai_role"), 40),
        "style": style,
        "style_reason": _clean_str(data.get("style_reason"), 60),
        # 역할 관계에 어울리는 친밀도(D)·학습자 지위(P) 추천 — 페이더 자동 설정용
        "d": _clamp_int(data.get("d"), 0, 100, 30),
        "p": _clamp_int(data.get("p"), 0, 100, 50),
    }


@app.post("/roleplay-suggest")
async def roleplay_suggest(request: Request):
    """장소나 목적 중 하나만 적으면 나머지(목적 3단계·장소·역할·말투)를 '예)'로 자동 추천.
    목적은 ①교재형(이상적) ②일상형(흔히 겪는) ③엉뚱형(뜻밖의 상황) 3단계 —
    클라이언트가 랜덤으로 하나를 보여주고 🎲 버튼으로 순환·재추첨한다."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="bad_json")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="bad_json")

    topic = _clean_str(body.get("topic"), 80)   # 구버전 호환
    place = _clean_str(body.get("place"), 60)
    goal = _clean_str(body.get("goal"), 120)
    if not (topic or place or goal):
        raise HTTPException(status_code=400, detail="input_required")

    # 추천 값은 학습자의 화면 언어(모국어)로 — 학습자가 읽고 고를 수 있어야 한다.
    # (제출 시 /roleplay-setup이 어떤 언어든 한국어로 정규화하므로 문제 없음)
    ui_lang = _clean_str(body.get("lang"), 5).lower()
    native = LANG_NAMES.get(ui_lang, "")
    lang_line = (f"모든 추천 값(goals, place, my_role, ai_role, style_reason)은 반드시 학습자의 모국어인 {native}로 작성하라. 한국어로 쓰지 마라."
                 if native else "모든 추천 값은 자연스러운 한국어로 작성하라.")

    given_lines = []
    if place:
        given_lines.append(f"- 대화 장소: {place}")
    if goal:
        given_lines.append(f"- 대화의 달성 목적: {goal}")
    if topic:
        given_lines.append(f"- 주제: {topic}")
    given = "\n".join(given_lines)

    prompt = f"""너는 한국어 교육 전문가다. 한국어 학습자가 음성 챗봇과 상황극 대화 연습을 하려고 아래 항목을 입력했다.
입력은 학습자의 모국어 등 어떤 언어로도 올 수 있다. 의미를 파악해 빈 항목들을 추천하라.

[학습자 입력]
{given}

[요구사항]
★ {lang_line}
1) goals: 이 상황에서 도전할 만한 '대화의 달성 목적' 3개를 정확히 이 순서로.
   ① 교재형: 한국어 교재에 나올 법한 가장 이상적·전형적인 목적.
   ② 일상형: 실제 생활에서 흔히 부딪히는, 약간의 변수가 있는 목적.
   ③ 엉뚱형: 같은 상황인데 뜻밖이고 재미있는 목적 (황당하지만 대화로는 성립해야 함).
   각각 짧은 명사형 구로 간결하게.
   학습자가 이미 목적을 적었다면 그 취지를 살리면서 세 단계로 변주하라.
2) place: 이 대화가 벌어질 전형적인 장소. 학습자가 적었다면 그것을 자연스럽게 다듬어라.
3) my_role: 학습자 역할 (예: "손님").
4) ai_role: 상대(챗봇) 역할 (예: "점원").
5) style: 이 관계에서 자연스러운 말투 — "polite"(존댓말) 또는 "banmal"(반말).
6) style_reason: 그 말투가 자연스러운 이유 한 구절 (15자 내외, 예: "처음 보는 점원과 손님 사이").
7) d: 두 역할의 친밀도 추천값 0~100 (0=처음 보는 사이, 50=아는 사이, 100=절친). 예: 점원↔손님=10.
8) p: 학습자의 상대적 지위 추천값 0~100 (0=학습자가 아랫사람, 50=대등, 100=학습자가 윗사람/손님). 예: 손님=75, 면접 지원자=15.

JSON만 출력: {{"goals":["","",""],"place":"","my_role":"","ai_role":"","style":"polite","style_reason":"","d":30,"p":50}}"""

    # 엉뚱형의 다양성을 위해 온도를 높게 (호출마다 다른 추천)
    data = await _gen_json(prompt, timeout_s=25.0, temperature=1.1)
    sug = _validate_suggest(data)
    if sug is None and not (data is None and _quota_exhausted()):
        # 쿼터 소진이 아닐 때만 1회 재시도 (429에서 재시도는 쿼터 낭비)
        data = await _gen_json(prompt, timeout_s=25.0, temperature=1.1)
        sug = _validate_suggest(data)
    if sug is None:
        raise HTTPException(status_code=502, detail=("suggest_failed | " + _fail_reason(data))[:250])
    print(f"[상황극] 추천 생성: 입력='{place or goal or topic}' → 목적 {sug['goals']}")
    return sug


# ══════════ 교재 사진에서 상황 읽어 오기 ══════════
# 학습자가 교실에서 배운 그 페이지를 찍어 오면, 장소·목적·역할·말투를 뽑아
# 설정 칸을 미리 채운다. 앱에서 아무 상황이나 만들면 그날 배운 내용과 따로 놀지만,
# 교재를 찍어 넣으면 교실 수업이 그대로 확장 연습으로 이어진다(설계 원칙 P9).
#
# ★ 사진은 저장하지 않는다. 교재는 저작물이므로 설정만 뽑고 그 자리에서 버린다.
#   추출 결과는 반드시 학습자가 확인·수정한 뒤에 쓴다(잘못 뽑히면 엉뚱한 연습이 된다).
MAX_PHOTO_BYTES = 8 * 1024 * 1024
_PHOTO_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@app.post("/roleplay-from-photo")
async def roleplay_from_photo(photo: UploadFile = File(...), lang: str = Form(default="ko")):
    """교재 말하기 페이지 사진 → 장소·목적·내 역할·상대 역할·말투 추출."""
    mime = (photo.content_type or "").split(";")[0].strip().lower()
    if mime not in _PHOTO_MIME:
        raise HTTPException(status_code=415, detail="unsupported_image")
    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty_image")
    if len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="image_too_large")

    ui_lang = _clean_str(lang, 5).lower()
    native = LANG_NAMES.get(ui_lang, "")
    native_line = f"- native: 위 값을 {native}로 옮긴 것 (없으면 빈 문자열)" if native else "- native: 빈 문자열"

    prompt = f"""이 사진은 한국어 교재의 말하기 활동 페이지다. 대화문·삽화·지시문을 읽고
학습자가 연습할 '상황'을 뽑아라.

뽑을 것 (모두 한국어로, 짧게)
- place: 대화가 일어나는 장소 (예: 옷 가게, 병원 접수처).
  사진에 안 보이면 대화 내용에서 가장 그럴듯한 곳을 적는다. **비워 두지 마라.**
  짐작이 어려우면 "교실"로 둔다.
- goal: 학습자가 이루려는 목적 한 문장 (예: 마음에 드는 옷을 사기)
- myRole: 학습자가 맡을 역할 (예: 손님). **분명하지 않으면 "나"로 둔다.**
- aiRole: 상대가 맡을 역할 (예: 가게 점원). **분명하지 않으면 "친구"로 둔다.**
  교재의 말하기 활동은 대부분 친구끼리의 대화이므로, 점원·의사처럼
  뚜렷한 직업 역할이 보일 때만 그것을 쓰고 그 밖에는 "친구"가 맞다.
- style: "polite"(존댓말) 또는 "banmal"(반말). 대화문의 종결어미로 판단한다.
- topic: 이 활동의 주제 (예: 물건 사기)
{native_line}

규칙
- 대화의 내용을 지어내지 마라. 다만 place·myRole·aiRole 은 위 기본값 규칙에 따라 반드시 채운다.
- goal·topic 은 사진에서 읽히지 않으면 빈 문자열로 둔다.
- 교재 문장을 그대로 베끼지 말고, 상황을 요약해서 적는다.
- 한국어 교재가 아니거나 말하기 활동이 아니면 모든 값을 빈 문자열로 둔다.

JSON만 출력:
{{"place":"","goal":"","myRole":"","aiRole":"","style":"","topic":"","native":{{"place":"","goal":"","myRole":"","aiRole":""}}}}"""

    try:
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=0))
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=_analysis_model["name"],
                contents=[types.Part.from_bytes(data=raw, mime_type=mime), prompt],
                config=cfg),
            timeout=30.0)
        data = _parse_json_loose(getattr(resp, "text", "") or "")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="photo_timeout")
    except Exception as e:
        print(f"[교재사진] 분석 실패: {e}")
        raise HTTPException(status_code=502, detail="photo_failed")
    finally:
        raw = b""          # ★ 사진은 여기서 버린다 — 어디에도 저장하지 않는다

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="photo_parse_failed")
    nat = data.get("native") if isinstance(data.get("native"), dict) else {}
    out = {
        "place": _clean_str(data.get("place"), 60),
        "goal": _clean_str(data.get("goal"), 120),
        "myRole": _clean_str(data.get("myRole"), 40),
        "aiRole": _clean_str(data.get("aiRole"), 40),
        "topic": _clean_str(data.get("topic"), 80),
        "style": data.get("style") if data.get("style") in ("polite", "banmal") else "",
        "native": {k: _clean_str(nat.get(k), 120) for k in ("place", "goal", "myRole", "aiRole")},
    }
    out["ok"] = bool(out["place"] or out["goal"])
    print(f"[교재사진] 추출 {'성공' if out['ok'] else '실패(읽을 수 없음)'} — {out['place']} / {out['goal']}")
    return out


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
    # 페이더 좌표 — 대화문과 표현의 말투를 여기에 맞춘다.
    # 지금까지 style을 받아만 놓고 프롬프트에 넘기지 않아, 모델 대화문과
    # 발화 연습이 설정한 말투를 무시하고 제멋대로 나왔다(v88에서 고침).
    d_val = _clamp_int(body.get("d"), 0, 100, 30)
    p_val = _clamp_int(body.get("p"), 0, 100, 50)
    ui_lang = _clean_str(body.get("lang"), 5).lower()
    if not topic and not goal and not place:
        raise HTTPException(status_code=400, detail="topic_goal_or_place_required")

    # ── 말투(레지스터) 지시 ──
    # 학습자가 고른 말투와 페이더(친밀도 D·지위 P)를 대화문·표현에 그대로 반영한다.
    # 한 사람이 한 대화 안에서 반말과 존댓말을 섞으면 학습자가 배울 본이 되지 못한다.
    if style == "polite":
        want_user = want_ai = "polite"
    elif style == "banmal":
        want_user = want_ai = "banmal"
    else:
        # auto — 페이더로 정한다. 반말은 '가까운 사이'에서만 나오고,
        # 지위(P)가 위아래를 갈라 비대칭(한쪽만 반말)을 만든다.
        close = d_val >= 60
        want_user = "banmal" if (close and p_val >= 45) else "polite"
        want_ai = "banmal" if (close and p_val <= 55) else "polite"
    _LV_KO = {"polite": "존댓말(해요체)", "banmal": "반말(해체)"}
    if style == "polite":
        style_line = (f"두 사람 모두 **존댓말(해요체/합쇼체)** 로 말한다. "
                      f"{ai_role or '상대'}도 반말을 쓰지 않는다.")
    elif style == "banmal":
        style_line = ("두 사람 모두 **반말(해체)** 로 말한다. "
                      "'-요'로 끝나는 존댓말을 쓰지 않는다.")
    else:
        # auto — 페이더 좌표로 관계를 읽는다. D 높으면 가깝고, P 높으면 학습자가 윗사람.
        close = "가까운 사이" if d_val >= 60 else ("서먹한 사이" if d_val <= 30 else "보통 사이")
        rank = ("학습자가 윗사람" if p_val >= 65 else
                "학습자가 아랫사람" if p_val <= 35 else "둘이 대등")
        style_line = (
            f"두 사람의 관계는 **{close}**이고 **{rank}**이다(친밀도 {d_val}, 지위 {p_val}).\n"
            f"   이 관계에 맞는 말투를 **각 화자마다 하나로 정해** 대화문과 표현 전체에 똑같이 써라.\n"
            f"   윗사람이 아랫사람에게 반말을 쓰기로 했으면 끝까지 반말이고, "
            f"아랫사람은 끝까지 존댓말이다. 중간에 바뀌면 안 된다.")
    # 모델이 헷갈리지 않게 화자별 말투를 못 박아 준다 — 이것이 검증 기준이 된다
    style_line += (f"\n   ▶ **{my_role or '학습자'}는 {_LV_KO[want_user]}만 쓴다.**"
                   f"\n   ▶ **{ai_role or '상대'}는 {_LV_KO[want_ai]}만 쓴다.**")

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
- 챗봇(호아랑) 역할: {ai_role or "(미입력 — 학습자 역할의 상대역으로 추정)"}

[★ 말투 — 이것을 어기면 전부 다시 만들어야 한다]
{style_line}
- **한 사람은 처음부터 끝까지 한 가지 말투만 쓴다.** 대화문(script)과 표현(expressions) 모두에서.
  나쁜 예) 같은 사람이 "무슨 일이야?"(반말)라고 했다가 "무슨 일이에요?"(존댓말)로 바꾸는 것.
- 학습자가 쓸 표현(expressions)의 말투는 학습자({my_role or '학습자'})의 말투를 따른다.
- cue와 follow는 상대({ai_role or '상대'})의 말이므로 상대의 말투를 따른다.

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
   - expressions: 학습자({my_role or '학습자'} 역할)가 이 단계에서 쓸 만한 자연스러운 한국어 표현 2~3개. 실제 구어체로.
     표현과 cue는 모두 국제 통용 한국어 표준 교육과정 중급(4급 이하) 어휘·문법 범위로 작성하라.
     각 표현은 객체로 만든다: {{"text":"","cue":"","follow":"","idc":""}}
       · idc — 이 표현이 주로 기르는 상호작용 요소 하나:
         move(대화이동)|topic(화제)|turn(차례)|repair(단절 수정)|strategy(전략)|listen(듣기 반응)|context(맥락·존대)
         ★ 발화 연습은 '한 차례 주고받기'를 익히는 자리다. 기본은 move(대화이동)이며,
           대화 전체의 흐름인 '기능 단계'는 여기서 기를 수 없으니 쓰지 마라.
         한 단계 안에서 요소가 겹치지 않게 안배하라 — 모두 move면 대화이동만 연습하게 된다.
       · text   — 학습자가 말할 발화 (필수)
       · cue    — text 바로 앞에 올 상대({ai_role or '상대'})의 발화.
                  **학습자가 먼저 말을 여는 자리면 빈 문자열로 둔다.**
       · follow — text 바로 뒤에 올 상대의 반응. **3항 연속체로 연습시킬 때만** 채우고,
                  두 마디로 끝나는 자리면 빈 문자열로 둔다.

     ★ 말차례 연쇄를 다양하게 짜라. 질문–응답만 반복하지 마라.
       대화이동 관리 능력은 인접쌍 하나로 길러지지 않는다.
       - 학습자 선행형(cue 빈 문자열): 인사·요청·제안을 학습자가 먼저 여는 자리.
         예) text "선생님, 안녕하세요!" / cue "" / follow "어, 안녕하세요. 잘 지냈어요?"
       - 2항형: cue → text 로 끝나는 자리.
         예) cue "어떻게 오셨어요?" / text "택배 좀 부치려고 하는데요" / follow ""
       - 3항형(제안–수락/거절–반응): 상대의 반응까지 들어야 뜻이 완성되는 자리.
         예) cue "이건 3만 원이에요" / text "좀 비싼데요, 깎아 주시면 안 될까요?"
             follow "그럼 2만 5천 원에 드릴게요"
     ★ 한 단계 안의 표현들이 모두 같은 형태가 되지 않게 하라.
       특히 대화를 여는 단계에서는 **학습자가 먼저 말하는 형태(cue 빈 문자열)를 반드시 하나 이상** 넣어라.
4) script — 위 기능단계를 처음부터 끝까지 밟아 가는 **모델 대화문** 10~14줄.
   학습자가 연습에 들어가기 전에 듣고 관찰할 자료다. 교재의 제시 대화문을 대신하되 실제 구어에 가깝게 쓴다.
   - 각 줄: speaker("user" = {my_role or '학습자'} / "ai" = {ai_role or '상대'}), text(한국어 발화), stage(해당 기능단계 번호 0부터), native.
   - stage 번호는 반드시 0부터 차례로 올라가야 하며, 위 stages의 단계를 하나도 빠뜨리지 마라.
   - 첫 줄은 {ai_role or '상대'}(speaker="ai")로 시작하고, 두 사람이 번갈아 말하게 하라. 한 사람이 두 줄 이어 말해도 되지만 세 줄 이상은 안 된다.
   - 한 줄은 한 문장 또는 짧은 두 문장. 국제 통용 표준 교육과정 중급(4급 이하) 어휘·문법으로.
   - 문어체 금지. 담화표지("아", "음", "그럼", "네네"), 맞장구, 조각문 같은 입말의 특징을 자연스럽게 담아라.
   - 위 expressions에 쓴 표현들이 이 대화문 안에 자연스럽게 들어가게 하라. 학습자가 들은 것을 그대로 연습하게 된다.
   - {native_line.replace('각 단계의 native 필드에 name의', '각 줄의 native 필드에 text의') if native else 'native 필드는 빈 문자열로 둔다.'}

JSON만 출력하라. 스키마:
{{"topic_ko":"","goal_ko":"","place_ko":"","user_role":"","ai_role":"","stages":[{{"name":"","native":"","desc":"","expressions":[{{"text":"","cue":"","follow":"","idc":""}}]}}],"script":[{{"speaker":"ai","text":"","native":"","stage":0}}]}}"""

    # 대화문까지 함께 만드느라 길어졌다 — 넉넉히 기다린다
    data = await _gen_json(prompt, timeout_s=55.0)
    plan = _validate_plan(data)
    if plan is None and not (data is None and _quota_exhausted()):
        # 쿼터 소진이 아닐 때만 1회 재시도 (429에서 재시도는 쿼터 낭비)
        data = await _gen_json(prompt, timeout_s=55.0)
        plan = _validate_plan(data)
    # 말투가 어긋난 대화문은 본보기가 못 된다. 통째로 다시 만들지 않고
    # 어긋난 줄만 골라 손질한다 — 빠르고, 나머지 줄이 흔들리지 않는다.
    if plan is not None:
        bad = _style_offenders(plan.get("script"), want_user, want_ai)
        if bad:
            print(f"[상황극] 말투 어긋남 {len(bad)}줄 — 손질 시도")
            await _fix_style(plan, want_user, want_ai)
    if plan is None:
        raise HTTPException(status_code=502, detail=("plan_generation_failed | " + _fail_reason(data))[:250])

    _rp_cleanup()
    plan_id = base64.urlsafe_b64encode(os.urandom(9)).decode()
    _roleplay_plans[plan_id] = {"plan": plan, "style": style, "at": time.time()}
    print(f"[상황극] 계획 생성: {plan['topic_ko']} / 목적: {plan['goal_ko']} / "
          f"단계 {len(plan['stages'])}개 / 대화문 {len(plan['script'])}줄"
          + ("" if plan["script"] else " (대화문 없음 — 듣기 단계 건너뜀)"))
    return {"id": plan_id, "plan": plan}


_STYLE_RULES = {
    "polite": "말투: 존댓말(해요체) 고정. 아래 페이더 규칙과 충돌하면 이 말투 지시가 우선한다.",
    "banmal": "말투: 반말(해체) 고정. 아래 페이더 규칙과 충돌하면 이 말투 지시가 우선한다.",
    "auto": "말투: 페이더 좌표(D/P)를 따른다.",
}


def build_roleplay_prompt(d: int, p: int, ui_lang: str, user_name: str,
                          plan: dict, style: str,
                          idc_levels: dict | None = None,
                          idc_counts: dict | None = None) -> str:
    base = build_system_prompt(d, p, ui_lang, user_name)
    stages_txt = "\n".join(
        f"  {i + 1}. {s['name']} — {s['desc']}" for i, s in enumerate(plan["stages"]))
    rp_block = f"""

# ★★★ 상황극 모드 (자유 대화가 아님 — 이 블록이 최우선) ★★★
지금은 '주제 대화 연습(상황극)'이다. 학습자가 직접 설정한 과업:
- 주제: {plan['topic_ko']}
- 대화의 달성 목적: {plan['goal_ko']}
- 장소: {plan['place_ko']}
- 학습자 역할: {plan['user_role']} / 너의 역할: {plan['ai_role']}
너는 호아랑인 채로 '{plan['ai_role']}' 역할을 연기한다. 역할에 몰입하되 호아랑의 온기는 유지해.
- [목소리 나이] 위 '목소리와 말투의 나이'(어린 아이 톤)는 자유 대화일 때 규칙이다.
  지금은 배역을 맡았으니 '{plan['ai_role']}'에게 어울리는 나이·말투로 말해라.
  배역이 어른이면 어른답게, 또래면 또래답게. 배역이 아이가 아닌데 아이 목소리를 흉내 내지 마라.
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
    return base + rp_block + build_mko_block(idc_levels, idc_counts,
                                              native=LANG_NAMES.get(ui_lang, ""))


# ============================================================
# 발화 연습용 Gemini TTS/STT — 기기 내장 음성 대신 실감나는 음성으로.
# TTS 모델도 단종(404) 시 후보 → API 목록 순으로 자동 전환.
# ============================================================
TTS_MODEL = os.environ.get("TTS_MODEL", "").strip() or "gemini-2.5-flash-preview-tts"

# ── 목소리 (Chirp 3 HD 프리빌트 보이스 — Live API·TTS 공용) ──────────────
# 호아랑은 '갓 쓴 아기 호랑이'라 기본은 밝은 남자아이 목소리(Puck)로 잡는다.
# 주제 대화에서는 호아랑이 배역을 맡으므로, 그 배역에 맞는 목소리로 자동 전환한다.
VOICE_TABLE = {
    "boy":     "Puck",     # Upbeat  — 밝은 남자아이 (호아랑 본래 목소리)
    "boy_hi":  "Fenrir",   # Excitable — 더 들뜬 소년
    "girl":    "Leda",     # Youthful — 앳된 목소리
    "man":     "Charon",   # Informative — 차분한 성인 남성
    "man_firm": "Orus",    # Firm — 단단한 성인 남성
    "woman":   "Kore",     # Firm — 또렷한 성인 여성
    "woman_soft": "Aoede", # Breezy — 부드러운 성인 여성
    "elder_m": "Algenib",  # Gravelly — 나이 든 남성 (할아버지 역)
    "elder_f": "Gacrux",   # Mature — 원숙한 여성 (할머니 역)
}
HOARANG_VOICE_KEY = "boy"
TTS_VOICE = os.environ.get("TTS_VOICE", "").strip() or VOICE_TABLE[HOARANG_VOICE_KEY]

# 역할 이름에서 성별·나이를 '드러나 있을 때만' 읽는다.
# 직업만으로 성별을 넘겨짚지 않기 위해(예: 간호사=여성) 명시적 호칭만 본다.
_ROLE_FEMALE = ("아주머니", "아줌마", "어머니", "엄마", "어머님", "언니", "누나", "이모", "고모",
                "여자", "여성", "소녀", "딸", "아내", "부인", "여동생", "여학생", "여선생",
                "할머니", "외할머니", "여사장", "아가씨", "며느리", "숙모")
_ROLE_MALE = ("아저씨", "아버지", "아빠", "아버님", "형", "오빠", "삼촌", "외삼촌",
              "남자", "남성", "소년", "아들", "남편", "남동생", "남학생", "남선생",
              "할아버지", "외할아버지", "남사장", "총각", "사위", "고모부")
_ROLE_ELDER = ("할머니", "할아버지", "어르신", "노인", "외할머니", "외할아버지", "연세")
_ROLE_YOUNG = ("친구", "학생", "동급생", "반 친구", "짝꿍", "또래", "후배", "아이", "어린이",
               "동생", "초등학생", "중학생", "고등학생")


def pick_voice(ai_role: str = "", override: str = "") -> str:
    """대화 상대(호아랑이 맡은 배역)에 어울리는 목소리 이름을 고른다.

    - 학습자가 홈에서 목소리를 직접 고르면(override) 그것을 최우선으로 쓴다.
    - 자유 대화처럼 배역이 없으면 호아랑 본래 목소리(남자아이).
    - 배역에 성별·나이가 드러나 있으면 반영한다.
    - 직업 이름만 있어 성별을 알 수 없으면 넘겨짚지 않고, 역할 이름을 해시해
      성인 남성/여성 중 하나를 고정 배정한다(같은 역할이면 항상 같은 목소리).
    """
    key = (override or "").strip().lower()
    if key and key != "auto":
        if key in VOICE_TABLE:
            return VOICE_TABLE[key]
        for v in VOICE_TABLE.values():       # 목소리 이름을 그대로 보낸 경우
            if key == v.lower():
                return v
    role = (ai_role or "").strip()
    if not role:
        return VOICE_TABLE[HOARANG_VOICE_KEY]

    is_elder = any(w in role for w in _ROLE_ELDER)
    is_female = any(w in role for w in _ROLE_FEMALE)
    is_male = any(w in role for w in _ROLE_MALE)
    is_young = any(w in role for w in _ROLE_YOUNG)
    # 성별이 드러나지 않으면 넘겨짚지 않고 역할명 해시로 고정 배정
    # (같은 역할이면 언제나 같은 목소리 — 수업 중 목소리가 널뛰지 않게)
    coin_female = hashlib.sha1(role.encode("utf-8")).digest()[0] % 2 == 1
    if not (is_female or is_male):
        is_female, is_male = coin_female, not coin_female

    if is_elder:
        return VOICE_TABLE["elder_f" if is_female else "elder_m"]
    if is_young:
        return VOICE_TABLE["girl" if is_female else "boy"]
    return VOICE_TABLE["woman" if is_female else "man"]


# 같은 목소리라도 '어떻게 말할지'를 지시하면 나이대가 달라진다.
# Gemini TTS는 "<지시>: <문장>" 형태의 자연어 스타일 지시를 지원한다.
# 아이 목소리로 잡힌 배역에서만 붙이고, 어른 배역에는 붙이지 않는다.
_CHILD_VOICES = {"Puck", "Leda", "Fenrir", "Sadachbia"}
TTS_CHILD_STYLE = os.environ.get("TTS_CHILD_STYLE", "").strip() or \
    "밝고 신나는 초등학생 아이 목소리로, 조금 빠르고 가볍게 말해줘"


def _tts_prompt(text: str, voice: str, style_on: bool = True) -> str:
    """TTS에 보낼 최종 프롬프트. 아이 목소리일 때만 어린 톤 지시를 앞에 붙인다."""
    if not style_on or voice not in _CHILD_VOICES:
        return text
    return f'{TTS_CHILD_STYLE}: "{text}"'


_tts_model = {"name": TTS_MODEL}
_tts_tried = set()
_tts_cache = {}  # (text, voice, style) -> pcm bytes (같은 문장 반복 재생 시 API 호출 절약)


async def _next_tts_model(bad: str) -> str | None:
    _tts_tried.add(bad)
    for c in ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts", "gemini-2.5-flash-tts"]:
        if c not in _tts_tried:
            return c
    try:
        lst = client.aio.models.list()
        if hasattr(lst, "__await__"):
            lst = await lst
        names = []
        async for m in lst:
            n = (getattr(m, "name", "") or "").replace("models/", "")
            if "tts" in n:
                names.append(n)
        for n in sorted(names, reverse=True):
            if n not in _tts_tried:
                return n
    except Exception as e:
        print(f"[TTS] 모델 목록 조회 실패: {e}")
    return None


@app.post("/tts")
async def tts_endpoint(request: Request):
    """짧은 문장 → 24kHz PCM 음성. 발화 연습·비계(스캐폴딩) 재생용."""
    from fastapi.responses import Response
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="bad_json")
    text = _clean_str((body or {}).get("text"), 200)
    if not text:
        raise HTTPException(status_code=400, detail="text_required")
    # 발화 연습에서도 대화와 같은 목소리로 들려준다 (배역·학습자 선택 반영)
    voice = pick_voice(_clean_str((body or {}).get("role"), 40),
                       _clean_str((body or {}).get("voice"), 20))
    style_on = (body or {}).get("style") != "off"
    prompt_text = _tts_prompt(text, voice, style_on)
    ck = (text, voice, style_on)
    if ck in _tts_cache:
        return Response(content=_tts_cache[ck], media_type="audio/pcm")

    last_err = ""
    for _ in range(3):
        model_name = _tts_model["name"]
        try:
            cfg = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))))
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(model=model_name, contents=prompt_text, config=cfg),
                timeout=25.0)
            data = b""
            for cand in (getattr(resp, "candidates", None) or []):
                content = getattr(cand, "content", None)
                for part in (getattr(content, "parts", None) or []):
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and inline.data:
                        data += inline.data
            if not data:
                raise RuntimeError("no_audio_in_response")
            if len(_tts_cache) > 300:
                _tts_cache.clear()
            _tts_cache[ck] = data
            return Response(content=data, media_type="audio/pcm")
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"[:200]
            print(f"[TTS] 생성 실패({model_name}): {e}")
            if "NOT_FOUND" in str(e) or "404" in str(e):
                nxt = await _next_tts_model(model_name)
                if nxt:
                    print(f"[TTS] 모델 자동 전환: {model_name} → {nxt}")
                    _tts_model["name"] = nxt
                    continue
            break
    raise HTTPException(status_code=502, detail=("tts_failed | " + last_err)[:250])


@app.post("/stt")
async def stt_endpoint(audio: UploadFile = File(...), hint: str = Form(default="")):
    """발화 연습 녹음 → 한국어 전사.
    hint = 학습자가 말하려던 목표 문장. 외국인 억양·서툰 발음은 일반 전사가 잘 안 되므로
    목표 문장을 참조 문맥으로 줘서 '그렇게 들리면 그렇게' 적게 한다 (관대한 인식)."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_audio")
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio_too_large")
    mime = (audio.content_type or "audio/webm").split(";")[0].strip() or "audio/webm"
    # ★ 목표 문장은 일부러 모델에 주지 않는다.
    #   목표를 알려주면 발음이 엉망이어도 그 문장을 그대로 받아 적어(베껴서) '완벽해요'가 떴다.
    #   채점은 클라이언트가 '들린 대로의 전사'와 목표를 비교해서 한다.
    prompt = (
        "다음 오디오는 한국어를 배우는 외국인 학습자의 짧은 발화다. 발음 평가에 쓸 전사이므로 "
        "들리는 소리를 있는 그대로 한글로 적어라.\n"
        "- 문법·조사·맞춤법을 고치지 마라. 어색해도 들린 대로 적는다.\n"
        "- 잘못 발음한 음절은 잘못 발음한 대로 적어라 (예: '얼마예요'로 들리지 않으면 '올마에요'처럼 들린 대로).\n"
        "- 말이 중간에 끊겼으면 끊긴 데까지만 적어라. 알아서 완성하지 마라.\n"
        "- 아무 말도 안 들리거나 잡음뿐이면 빈 문자열을 출력하라.\n"
        "전사 텍스트만 출력하고 다른 말은 하지 마라.")
    try:
        cfg = types.GenerateContentConfig(temperature=0.0)
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=_analysis_model["name"],
                contents=[types.Part.from_bytes(data=data, mime_type=mime), prompt],
                config=cfg),
            timeout=25.0)
        text = re.sub(r"\s+", " ", (getattr(resp, "text", "") or "")).strip()[:200]
        return {"text": text}
    except Exception as e:
        print(f"[STT] 인식 실패: {e}")
        raise HTTPException(status_code=502, detail=(f"stt_failed | {type(e).__name__}: {e}")[:250])


@app.get("/voice-lab", response_class=HTMLResponse)
async def voice_lab():
    """교사용 목소리 비교 페이지(학생 화면에는 링크가 없다).
    후보 목소리를 같은 문장으로 나란히 들어보고 기본 목소리를 정하는 데 쓴다."""
    cands = [
        ("Puck", "Upbeat", "밝고 들뜬 남성 — 현재 호아랑 기본"),
        ("Fenrir", "Excitable", "더 들뜨고 활기찬 남성"),
        ("Sadachbia", "Lively", "생기 있는 남성"),
        ("Achird", "Friendly", "친근한 남성"),
        ("Zubenelgenubi", "Casual", "편하게 말하는 남성"),
        ("Leda", "Youthful", "가장 앳된 목소리(여성 계열)"),
        ("Charon", "Informative", "차분한 성인 남성"),
        ("Orus", "Firm", "단단한 성인 남성"),
        ("Kore", "Firm", "또렷한 성인 여성 — v28까지의 기본"),
        ("Aoede", "Breezy", "부드러운 성인 여성"),
        ("Algenib", "Gravelly", "나이 든 남성"),
        ("Gacrux", "Mature", "원숙한 여성"),
    ]
    rows = "".join(
        f'<tr><td><b>{n}</b><div class="d">{d} · {k}</div></td>'
        f'<td><button onclick="play(this,\'{n}\',1)">🔊 어린 톤</button></td>'
        f'<td><button onclick="play(this,\'{n}\',0)">🔊 지시 없이</button></td></tr>'
        for n, d, k in cands)
    return HTMLResponse(f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>목소리 비교 — 호아랑 {APP_VERSION}</title>
<style>
 body{{font-family:-apple-system,"Malgun Gothic",sans-serif;background:#F3F1EB;color:#394063;
      margin:0;padding:24px 16px 60px}}
 .w{{max-width:640px;margin:0 auto}} h1{{font-size:20px;margin:0 0 6px}}
 p.s{{color:#8790A6;font-size:13px;margin:0 0 18px;line-height:1.6}}
 textarea{{width:100%;height:64px;border:1.5px solid #DADEEA;border-radius:12px;padding:10px;
      font-family:inherit;font-size:14px;margin-bottom:14px}}
 table{{width:100%;border-collapse:collapse;background:#fff;border-radius:16px;overflow:hidden;
      box-shadow:0 10px 34px -12px rgba(57,64,99,.28)}}
 td{{padding:10px 12px;border-bottom:1px solid #EDEBE4;vertical-align:middle}}
 .d{{font-size:11px;color:#8790A6;margin-top:2px}}
 button{{border:1.5px solid #DCE3E7;background:#fff;border-radius:10px;padding:8px 10px;
      font-size:13px;cursor:pointer;white-space:nowrap;font-family:inherit;color:#394063}}
 button:hover{{border-color:#5A7285}} button:disabled{{opacity:.45;cursor:default}}
 .note{{margin-top:18px;font-size:12px;color:#8790A6;line-height:1.7}}
</style></head><body><div class="w">
<h1>🎙️ 목소리 비교 <span style="font-size:12px;color:#8790A6">{APP_VERSION}</span></h1>
<p class="s">같은 문장을 목소리별로 들어보고 호아랑 기본 목소리를 정하세요.
'어린 톤'은 TTS에 <b>어린 아이처럼 말해달라는 지시</b>를 붙인 것이고, '지시 없이'는 목소리 원본입니다.<br>
지시가 <b>말소리로 새어 나오면</b>(안내문을 그대로 읽으면) 알려주세요 — 그 기능을 끄겠습니다.</p>
<textarea id="t">안녕! 나는 호아랑이야. 오늘 뭐 하고 놀까? 같이 한국어로 이야기하자!</textarea>
<table>{rows}</table>
<p class="note">이 페이지는 학생 화면 어디에도 링크되어 있지 않습니다(주소를 알아야 들어옴).<br>
현재 기본: <b>{VOICE_TABLE[HOARANG_VOICE_KEY]}</b> · 어린 톤 지시: <b>{TTS_CHILD_STYLE}</b></p>
</div><script>
let ctx, last;
async function play(btn, voice, style) {{
  const text = document.getElementById("t").value.trim();
  if (!text) return;
  btn.disabled = true; const old = btn.textContent; btn.textContent = "⏳";
  try {{
    const r = await fetch("/tts", {{ method:"POST", headers:{{"Content-Type":"application/json"}},
      body: JSON.stringify({{ text: text, voice: voice, style: style ? "on" : "off" }}) }});
    if (!r.ok) throw new Error("HTTP " + r.status);
    const buf = await r.arrayBuffer();
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (last) {{ try {{ last.stop(); }} catch(e) {{}} }}
    const usable = buf.byteLength - (buf.byteLength % 2);
    const i16 = new Int16Array(buf, 0, usable/2);
    const b = ctx.createBuffer(1, i16.length, 24000), ch = b.getChannelData(0);
    for (let i=0;i<i16.length;i++) ch[i] = i16[i]/32768;
    const src = ctx.createBufferSource(); src.buffer = b; src.connect(ctx.destination); src.start();
    last = src;
  }} catch(e) {{ alert("재생 실패: " + e.message); }}
  finally {{ btn.disabled = false; btn.textContent = old; }}
}}
</script></body></html>""")


# ============================================================
# 알림(웹 푸시) — 하루 세 번 호아랑이 부른다
#   설정: Render 환경변수에 VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT
#   키가 없으면 기능 전체가 조용히 꺼진다(앱 동작에는 영향 없음).
# ============================================================
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "").strip() or "mailto:namho1210@naver.com"
PUSH_HOURS = [10, 14, 20]        # 한국시간 기준 발송 시각
KST = datetime.timezone(datetime.timedelta(hours=9))
_PUSH_FILE = "push_subs.json"
_push_subs = {}                  # endpoint -> {sub, lang, name, at}
_push_sent = set()               # 오늘 이미 보낸 (날짜, 시각) — 중복 발송 방지
_push_lock = asyncio.Lock()

# 시간대별 문구 (아침·점심·저녁) — {name}은 학습자 이름으로 치환
PUSH_MSG = {
    "ko": [("좋은 아침이에요!", "{name}, 오늘 한국어 한마디 해볼까요?"),
           ("잠깐 쉬어 갈까요?", "{name}, 호아랑이랑 5분만 이야기해요"),
           ("오늘 하루 어땠어요?", "{name}, 호아랑이 기다리고 있어요")],
    "en": [("Good morning!", "{name}, ready for a little Korean today?"),
           ("Time for a break?", "{name}, just 5 minutes with Hoarang"),
           ("How was your day?", "{name}, Hoarang is waiting for you")],
    "zh": [("早上好！", "{name}，今天来说一句韩语吧？"), ("休息一下？", "{name}，和Hoarang聊5分钟"),
           ("今天过得怎么样？", "{name}，Hoarang在等你哦")],
    "ja": [("おはよう！", "{name}、今日も韓国語ひとこと言ってみる？"), ("ひと休みしよう？", "{name}、ホアランと5分だけ"),
           ("今日はどうだった？", "{name}、ホアランが待ってるよ")],
    "vi": [("Chào buổi sáng!", "{name}, hôm nay nói một câu tiếng Hàn nhé?"),
           ("Nghỉ một chút nhé?", "{name}, 5 phút với Hoarang thôi"),
           ("Hôm nay của bạn thế nào?", "{name}, Hoarang đang đợi bạn")],
    "th": [("อรุณสวัสดิ์!", "{name} วันนี้พูดภาษาเกาหลีสักประโยคไหม?"),
           ("พักสักครู่ไหม?", "{name} คุยกับ Hoarang แค่ 5 นาที"),
           ("วันนี้เป็นยังไงบ้าง?", "{name} Hoarang รออยู่นะ")],
    "id": [("Selamat pagi!", "{name}, coba satu kalimat bahasa Korea hari ini?"),
           ("Istirahat sebentar?", "{name}, 5 menit saja dengan Hoarang"),
           ("Bagaimana harimu?", "{name}, Hoarang menunggumu")],
    "mn": [("Өглөөний мэнд!", "{name}, өнөөдөр солонгосоор нэг өгүүлбэр хэлэх үү?"),
           ("Жаахан амарцгаая?", "{name}, Hoarang-тай ердөө 5 минут"),
           ("Өнөөдөр ямар байсан бэ?", "{name}, Hoarang чамайг хүлээж байна")],
    "uz": [("Xayrli tong!", "{name}, bugun bitta koreyscha gap aytamizmi?"),
           ("Biroz dam olamizmi?", "{name}, Hoarang bilan atigi 5 daqiqa"),
           ("Kuningiz qanday o'tdi?", "{name}, Hoarang sizni kutmoqda")],
    "ru": [("Доброе утро!", "{name}, скажем сегодня фразу по-корейски?"),
           ("Сделаем паузу?", "{name}, всего 5 минут с Hoarang"),
           ("Как прошёл день?", "{name}, Hoarang тебя ждёт")],
    "es": [("¡Buenos días!", "{name}, ¿una frase en coreano hoy?"),
           ("¿Un descanso?", "{name}, solo 5 minutos con Hoarang"),
           ("¿Qué tal el día?", "{name}, Hoarang te está esperando")],
    "fr": [("Bonjour !", "{name}, une phrase en coréen aujourd'hui ?"),
           ("Une petite pause ?", "{name}, juste 5 minutes avec Hoarang"),
           ("Ta journée s'est bien passée ?", "{name}, Hoarang t'attend")],
}


def _push_ready() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def _push_load():
    global _push_subs
    try:
        with open(_PUSH_FILE, encoding="utf-8") as f:
            _push_subs = json.load(f)
        print(f"[알림] 저장된 구독 {len(_push_subs)}개 불러옴")
    except Exception:
        _push_subs = {}


def _push_save():
    try:
        with open(_PUSH_FILE, "w", encoding="utf-8") as f:
            json.dump(_push_subs, f)
    except Exception as e:
        print(f"[알림] 구독 저장 실패(무시): {e}")


def _push_send_one(entry: dict, slot: int) -> bool:
    """한 사람에게 보낸다. 구독이 죽었으면 False를 돌려 정리하게 한다."""
    from pywebpush import webpush, WebPushException
    lang = entry.get("lang") or "ko"
    msgs = PUSH_MSG.get(lang) or PUSH_MSG["ko"]
    title, body = msgs[slot % len(msgs)]
    name = (entry.get("name") or "").strip()
    body = body.replace("{name}, ", f"{name}, ") if name else body.replace("{name}, ", "").replace("{name}", "")
    payload = json.dumps({"title": title, "body": body, "url": "/"})
    try:
        webpush(subscription_info=entry["sub"], data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT})
        return True
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", 0)
        if code in (404, 410):      # 구독이 사라짐 — 목록에서 뺀다
            return False
        print(f"[알림] 발송 실패(계속 유지): {str(e)[:120]}")
        return True
    except Exception as e:
        print(f"[알림] 발송 오류: {str(e)[:120]}")
        return True


async def _push_broadcast(slot: int) -> int:
    if not _push_ready() or not _push_subs:
        return 0
    dead, sent = [], 0
    for ep, entry in list(_push_subs.items()):
        ok = await asyncio.to_thread(_push_send_one, entry, slot)
        if ok:
            sent += 1
        else:
            dead.append(ep)
    if dead:
        async with _push_lock:
            for ep in dead:
                _push_subs.pop(ep, None)
            _push_save()
    print(f"[알림] {len(PUSH_HOURS) and PUSH_HOURS[slot]}시 발송 — 성공 {sent} · 정리 {len(dead)}")
    return sent


async def _push_scheduler():
    """1분마다 시계를 보고, 한국시간으로 정해진 시각이 되면 한 번만 보낸다."""
    if not _push_ready():
        print("[알림] VAPID 키가 없어 알림 기능은 꺼짐")
        return
    print(f"[알림] 스케줄러 시작 — 매일 {', '.join(str(h) + '시' for h in PUSH_HOURS)} (한국시간)")
    while True:
        try:
            now = datetime.datetime.now(KST)
            if now.hour in PUSH_HOURS and now.minute < 5:
                key = (now.strftime("%Y-%m-%d"), now.hour)
                if key not in _push_sent:
                    _push_sent.add(key)
                    if len(_push_sent) > 40:
                        _push_sent.clear()
                        _push_sent.add(key)
                    await _push_broadcast(PUSH_HOURS.index(now.hour))
        except Exception as e:
            print(f"[알림] 스케줄러 오류(계속 진행): {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _on_startup():
    _push_load()
    asyncio.create_task(_push_scheduler())


@app.get("/push/key")
async def push_key():
    """브라우저가 구독할 때 필요한 공개키. 키가 없으면 enabled=false."""
    return {"enabled": _push_ready(), "key": VAPID_PUBLIC_KEY, "hours": PUSH_HOURS}


@app.post("/push/subscribe")
async def push_subscribe(request: Request):
    if not _push_ready():
        return {"ok": False, "reason": "disabled"}
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="bad_json")
    sub = (body or {}).get("sub")
    if not isinstance(sub, dict) or not sub.get("endpoint"):
        raise HTTPException(status_code=400, detail="bad_subscription")
    async with _push_lock:
        _push_subs[sub["endpoint"]] = {
            "sub": sub,
            "lang": _clean_str((body or {}).get("lang"), 5).lower() or "ko",
            "name": _clean_str((body or {}).get("name"), 20),
            "at": int(time.time()),
        }
        _push_save()
    return {"ok": True, "count": len(_push_subs)}


@app.post("/push/unsubscribe")
async def push_unsubscribe(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="bad_json")
    ep = (body or {}).get("endpoint") or ""
    async with _push_lock:
        removed = _push_subs.pop(ep, None) is not None
        if removed:
            _push_save()
    return {"ok": True, "removed": removed}


@app.get("/push/send")
async def push_send_now(key: str = "", slot: int = 2):
    """교사용 수동 발송 — /push/send?key=ADMIN_KEY (수업 시작 알림 등)."""
    admin = os.environ.get("ADMIN_KEY", "").strip()
    if not admin or key != admin:
        raise HTTPException(status_code=403, detail="forbidden")
    sent = await _push_broadcast(max(0, min(2, slot)))
    return {"ok": True, "sent": sent, "subscribers": len(_push_subs)}


# ══════════ APK 배포 (안드로이드) ══════════
# 안드로이드는 PWA 설치가 '크롬 바로가기'로 떨어지는 일이 잦아, 진짜 앱 파일을 직접 나눠 준다.
# PWABuilder로 만든 hoarang.apk 를 static/ 에 넣으면 아래 주소로 받을 수 있다.
APK_PATH = Path("static/hoarang.apk")


@app.get("/app-info")
async def app_info():
    """관문 화면이 'APK를 줄 수 있는 상태인가'를 확인하는 곳."""
    ok = APK_PATH.exists()
    if not ok:
        return {"apk": "", "size": 0, "mb": "", "sha256": "", "version": APP_VERSION}
    n = APK_PATH.stat().st_size
    # 파일이 도중에 잘렸는지 확인할 수 있도록 지문도 함께 준다(설치 실패 진단용)
    h = hashlib.sha256()
    with open(APK_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {
        "apk": "/download/hoarang.apk",
        "size": n,
        "mb": f"{n / 1048576:.1f}MB",
        "sha256": h.hexdigest(),
        "version": APP_VERSION,
    }


@app.get("/download/hoarang.apk")
@app.head("/download/hoarang.apk")   # 일부 다운로드 관리자가 HEAD로 먼저 물어본다
async def download_apk():
    """APK 내려받기. 안드로이드가 '설치'로 이어 가도록 MIME 타입을 정확히 준다."""
    if not APK_PATH.exists():
        raise HTTPException(status_code=404, detail="APK not uploaded yet")
    return FileResponse(
        APK_PATH,
        media_type="application/vnd.android.package-archive",
        filename="hoarang.apk",
    )


@app.get("/.well-known/assetlinks.json")
async def assetlinks():
    """Digital Asset Links — APK(TWA)가 이 사이트의 '정식 앱'임을 증명한다.

    이게 맞아야 앱 위에 주소창이 뜨지 않는다.
    PWABuilder가 준 assetlinks.json 을 static/ 에 그대로 넣거나,
    지문(SHA-256)만 환경변수 TWA_FINGERPRINT 에 넣어도 된다.
    """
    f = Path("static/assetlinks.json")
    if f.exists():
        return FileResponse(f, media_type="application/json")
    fp = os.getenv("TWA_FINGERPRINT", "").strip()
    pkg = os.getenv("TWA_PACKAGE", "com.hoarang.app").strip()
    if not fp:
        raise HTTPException(status_code=404, detail="assetlinks not configured")
    return [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": pkg,
            "sha256_cert_fingerprints": [x.strip() for x in fp.split(",") if x.strip()],
        },
    }]


@app.get("/home-loops")
async def home_loops():
    """홈 배경으로 쓸 루프 영상 목록.

    static/ 안의 `home_loop*.mp4`를 그대로 훑어서 돌려준다.
    새 영상을 만들면 파일만 넣으면 되고 코드는 고칠 필요가 없다.
    같은 이름의 .jpg가 있으면 포스터(흐린 배경막)로 함께 쓴다.
    """
    out = []
    try:
        d = Path("static")
        for p in sorted(d.glob("home_loop*.mp4")):
            jpg = p.with_suffix(".jpg")
            out.append({
                "mp4": f"/static/{p.name}",
                "jpg": f"/static/{jpg.name}" if jpg.exists() else "",
            })
    except Exception:
        pass
    if not out:
        out = [{"mp4": "/static/home_loop.mp4", "jpg": "/static/home_loop.jpg"}]
    return {"loops": out}


@app.get("/version")
async def version_check():
    """서버 코드와 화면 파일의 버전이 서로 맞는지 한눈에 확인한다.

    깃헙에 main.py만 올라가고 templates/index.html이 빠지면 겉보기엔 배포가 된 것 같은데
    화면은 옛날 것이 돈다. 그 사고를 다시 겪지 않으려고 만든 자리다.
    배포 후 이 주소를 열어 match 가 true 인지만 보면 된다.
    """
    tpl = ""
    try:
        t = Path(f"templates/{_BASE_TEMPLATE}").read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'APP_VERSION = "(v\d+)', t)
        tpl = m.group(1) if m else ""
    except Exception:
        pass
    return {
        "server": APP_VERSION,          # main.py
        "screen": tpl,                  # 실제로 쓰는 화면 파일의 버전
        "template": TEMPLATE_NAME,      # 어느 파일을 읽었는지
        "base": _BASE_TEMPLATE,         # 원본 파일 이름
        "patched": TEMPLATE_NAME == "_runtime.html",   # true = 화면 파일이 낡아 응급 패치 중
        "match": (tpl == APP_VERSION),  # ★ 이게 false 면 화면 파일이 안 올라간 것
        "date": APP_DATE,
        "sessions": _active_sessions,
        "max_sessions": MAX_CONCURRENT_SESSIONS,
    }


@app.get("/healthz")
async def healthz():
    """서버가 깨어 있는지만 확인하는 가장 가벼운 응답.
    무료 플랜은 15분쯤 쓰지 않으면 잠들고, 깨어나는 데 수십 초가 걸린다.
    클라이언트가 앱을 켤 때·대화 준비 단계에서 미리 이걸 찔러 깨워 둔다."""
    return {"ok": True, "app": APP_VERSION, "sessions": _active_sessions}


@app.get("/conn-diag", response_class=HTMLResponse)
async def conn_diag():
    """연결 진단 — '서버에 연결 중…'에서 멈출 때 어디서 막히는지 단계별로 재 본다.
    학생 화면에는 링크가 없다. 문제가 나는 그 기기에서 이 주소를 열면 된다."""
    return HTMLResponse(f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>연결 진단 — 호아랑 {APP_VERSION}</title>
<style>
 body{{font-family:-apple-system,"Malgun Gothic",sans-serif;background:#F4F0E6;color:#2E3338;margin:0;padding:22px 16px 60px}}
 .w{{max-width:620px;margin:0 auto}} h1{{font-size:19px;margin:0 0 6px}}
 p.s{{color:#726A5C;font-size:13px;margin:0 0 16px;line-height:1.6}}
 button{{border:none;border-radius:12px;background:#4A7C74;color:#fff;font-weight:800;font-size:14px;
   padding:12px 18px;cursor:pointer;font-family:inherit}}
 table{{width:100%;border-collapse:collapse;background:#FFFDF8;border-radius:14px;overflow:hidden;margin-top:16px}}
 td{{padding:10px 12px;border-bottom:1px solid #EDE8DC;font-size:13px;vertical-align:top}}
 td:first-child{{width:42%;font-weight:800;color:#2A4A55}}
 .ok{{color:#2E5B3E;font-weight:800}} .bad{{color:#B5573F;font-weight:800}} .wait{{color:#8A8175}}
 pre{{background:#FFFDF8;border-radius:12px;padding:12px;font-size:11.5px;overflow:auto;line-height:1.6}}
</style></head><body><div class="w">
<h1>🔌 연결 진단 <span style="font-size:12px;color:#726A5C">{APP_VERSION}</span></h1>
<p class="s">'서버에 연결 중…'에서 멈추는 그 기기·그 네트워크에서 이 페이지를 열고 아래 버튼을 눌러 주세요.
 어느 단계에서 몇 초가 걸리는지, 무엇이 막히는지 그대로 보여 줍니다.</p>
<button onclick="run()">진단 시작</button>
<table id="t"></table>
<pre id="log"></pre>
</div><script>
const rows = [
  ["서버 응답(/healthz)", "서버가 깨어 있는지 · 지금 대화 중인 세션 수"],
  ["웹소켓 핸드셰이크", "대화용 연결이 열리는 데 걸린 시간"],
  ["첫 서버 메시지", "연결 후 서버가 실제로 말을 거는지"],
  ["마이크 권한", "브라우저가 마이크를 내주는지"],
];
function draw(i, val, cls) {{
  const t = document.getElementById("t");
  if (!t.rows.length) rows.forEach(r => {{
    const tr = t.insertRow(); tr.insertCell().textContent = r[0];
    const c = tr.insertCell(); c.innerHTML = '<span class="wait">대기</span><div style="font-size:11px;color:#8A8175;margin-top:2px">' + r[1] + '</div>';
  }});
  const c = t.rows[i].cells[1];
  c.innerHTML = '<span class="' + cls + '">' + val + '</span><div style="font-size:11px;color:#8A8175;margin-top:2px">' + rows[i][1] + '</div>';
}}
function log(m) {{ document.getElementById("log").textContent += m + "\\n"; }}
async function run() {{
  document.getElementById("t").innerHTML = ""; document.getElementById("log").textContent = "";
  rows.forEach((_, i) => draw(i, "대기", "wait"));
  // ① /healthz
  let t0 = performance.now();
  try {{
    const r = await fetch("/healthz?t=" + Date.now(), {{ cache: "no-store" }});
    const j = await r.json();
    const ms = Math.round(performance.now() - t0);
    draw(0, ms + "ms · 세션 " + j.sessions + "개", ms < 1500 ? "ok" : "bad");
    log("healthz " + ms + "ms " + JSON.stringify(j));
    if (ms > 3000) log("→ 서버가 잠들어 있었거나 매우 느립니다.");
  }} catch (e) {{ draw(0, "실패", "bad"); log("healthz 실패: " + e); return; }}
  // ② 웹소켓
  t0 = performance.now();
  const proto = location.protocol === "https:" ? "wss://" : "ws://";
  const ws = new WebSocket(proto + location.host + "/ws/live?d=50&p=50&lang=ko&name=%EC%A7%84%EB%8B%A8");
  let opened = false, gotMsg = false;
  const guard = setTimeout(() => {{
    if (!opened) {{ draw(1, "25초 안에 못 붙음", "bad");
      log("→ 핸드셰이크가 응답하지 않습니다. 서버 재시작 중이거나 네트워크(방화벽·프록시)가 웹소켓을 막는지 확인하세요."); }}
    try {{ ws.close(); }} catch (e) {{}}
  }}, 25000);
  ws.onopen = () => {{ opened = true; clearTimeout(guard);
    const ms = Math.round(performance.now() - t0);
    draw(1, ms + "ms 연결됨", ms < 3000 ? "ok" : "bad"); log("웹소켓 연결 " + ms + "ms");
    setTimeout(() => {{ if (!gotMsg) {{ draw(2, "10초간 응답 없음", "bad");
      log("→ 연결은 됐는데 서버가 조용합니다. Gemini 연결·API 키·쿼터를 확인하세요."); }}
      try {{ ws.close(); }} catch (e) {{}} }}, 10000);
  }};
  ws.onmessage = (ev) => {{ if (gotMsg) return; gotMsg = true;
    const ms = Math.round(performance.now() - t0);
    draw(2, ms + "ms 만에 첫 메시지", "ok");
    log("첫 메시지: " + String(ev.data).slice(0, 160));
    try {{ ws.close(); }} catch (e) {{}} }};
  ws.onclose = (ev) => {{ clearTimeout(guard); log("소켓 닫힘 code=" + ev.code + " reason=" + (ev.reason || "-"));
    if (!opened) draw(1, "닫힘 code " + ev.code, "bad"); }};
  ws.onerror = () => log("소켓 오류 발생");
  // ③ 마이크
  try {{
    const st = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    draw(3, "허용됨", "ok"); st.getTracks().forEach(t => t.stop());
  }} catch (e) {{ draw(3, "거부/실패: " + e.name, "bad");
    log("→ 마이크가 없으면 연결돼도 대화가 되지 않습니다."); }}
}}
</script></body></html>""")


@app.get("/rp-diag")
async def rp_diag(test: int = 0, models: int = 0):
    """상황극 생성 경로 진단 — /rp-diag?test=1 은 실제 모델 호출 1회로 성공 여부·
    소요 시간·오류 원인을, ?models=1 은 이 API 키로 쓸 수 있는 모델 목록을 보여준다."""
    import sys
    try:
        import google.genai as _gg
        sdk_ver = getattr(_gg, "__version__", "?")
    except Exception:
        sdk_ver = "?"
    info = {
        "app": APP_VERSION,
        "python": sys.version.split()[0],
        "google_genai": sdk_ver,
        "analysis_model": _analysis_model["name"],
        "api_key_set": bool(os.environ.get("GEMINI_API_KEY")),
        "last_gen_error": dict(LAST_GEN_ERROR),
    }
    if models:
        try:
            lst = client.aio.models.list()
            if hasattr(lst, "__await__"):
                lst = await lst
            names = []
            async for m in lst:
                n = (getattr(m, "name", "") or "").replace("models/", "")
                acts = list(getattr(m, "supported_actions", None) or [])
                if n and (not acts or "generateContent" in acts):
                    names.append(n)
            info["available_models"] = sorted(names)[:80]
        except Exception as e:
            info["available_models_error"] = repr(e)[:200]
    if test:
        t0 = time.time()
        data = await _gen_json('JSON만 출력하라: {"pong": true}', timeout_s=20.0)
        info["test_seconds"] = round(time.time() - t0, 1)
        info["test_ok"] = isinstance(data, dict) and bool(data.get("pong"))
        info["test_result"] = data
        info["last_gen_error"] = dict(LAST_GEN_ERROR)
    return info


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    resp = templates.TemplateResponse(request=request, name=TEMPLATE_NAME)
    # 브라우저가 옛 index.html을 캐시해서 "고쳤는데 그대로"가 되는 것 방지
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-App-Version"] = f"{APP_VERSION} ({APP_DATE})"
    return resp


# 서비스 워커는 루트 경로에서 서빙해야 전체 사이트를 제어(scope '/')할 수 있음
@app.get("/sw.js")
async def get_service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")


# ── 대화 중 주기 저장: 세션 ID(sid)별로 파일 이름·Drive 파일 ID를 기억해
#    같은 파일을 계속 갱신한다 → 앱을 강제 종료해도 마지막 저장분까지 보존 ──
_session_uploads = {}  # sid -> {"base": str, "at": float, "ids": {filename: gdrive_id}}


def _session_uploads_cleanup():
    now = time.time()
    for k in [k for k, v in _session_uploads.items() if now - v["at"] > 6 * 3600]:
        _session_uploads.pop(k, None)


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
    sid: str = Form(default=""),
):
    """대화 녹음(믹스 1파일) + 대화기록(txt) + 대화 정보(json) 저장.
    - 대화 중 60초마다 클라이언트가 같은 sid로 진행분을 보내면 같은 파일을 갱신
      (앱 강제 종료에도 마지막 저장분까지 보존)
    - 종료 시 최종본으로 마무리, 탭을 닫으면 sendBeacon으로 txt+json이라도 전송"""
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
    # 같은 세션(sid)의 반복 저장은 같은 파일 이름을 재사용 → 갱신
    safe_sid = re.sub(r"[^0-9A-Za-z_-]", "", sid)[:24]
    entry = _session_uploads.get(safe_sid) if safe_sid else None
    if entry:
        base = entry["base"]
        entry["at"] = time.time()
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"호아랑대화_{ts}" + (f"_{safe_name}" if safe_name else "") + f"_D{d}_P{p}"
        if safe_sid:
            _session_uploads_cleanup()
            entry = {"base": base, "at": time.time(), "ids": {}}
            _session_uploads[safe_sid] = entry
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
                known_id = entry["ids"].get(filename) if entry else None
                if known_id:
                    # 진행 중 저장 갱신 — 새 파일을 만들지 않고 내용만 교체
                    file_id = await asyncio.to_thread(_gdrive_update_sync, known_id, data, mime)
                else:
                    file_id = await asyncio.to_thread(_gdrive_upload_sync, filename, data, mime)
                    if entry is not None:
                        entry["ids"][filename] = file_id
                saved.append({"name": filename, "id": file_id})
            print(f"[녹음] Google Drive 저장 완료{' (갱신)' if entry and safe_sid else ''}: {[s['name'] for s in saved]}")
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
    # 학습자가 홈에서 고른 목소리 (빈 값·auto면 배역에 맞춰 자동 선택)
    voice_pref = websocket.query_params.get("voice", "").strip().lower()[:20]
    # 비계 넛지의 세기 — 홈의 페이더로 학습자가 정한다 (0 끔 / 1 적게 / 2 보통 / 3 많이).
    # 학습자가 상한을 정하고, 그 아래에서는 실현 여부에 따른 자동 페이딩이 그대로 돈다.
    try:
        scaf_level = max(0, min(3, int(float(websocket.query_params.get("scaf", 2)))))
    except (TypeError, ValueError):
        scaf_level = 2

    # 주제 대화(상황극) 모드: /roleplay-setup에서 만든 계획 ID가 오면 상황극 프롬프트로 전환
    rp_plan = None
    rp_style = "auto"
    rp_id = websocket.query_params.get("rp", "").strip()[:32]
    # 기기가 보관해 온 IDC 실현 누적 횟수 — "stage:2,repair:1" 꼴.
    # 근접발달영역은 세션을 넘어 이동한다: 어제 자율 수준까지 간 요소를
    # 오늘 다시 모델링부터 시작하면 비계가 아니라 방해다.
    prev_counts = {}
    try:
        for pair in websocket.query_params.get("idc", "").split(","):
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            k = k.strip()
            if k in IDC_SCORED_KEYS:
                prev_counts[k] = min(max(int(v), 0), 99)
    except (ValueError, TypeError):
        prev_counts = {}
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

    # ── IDC 비계 상태 (더 유능한 타인의 페이딩) ──
    # counts: 요소별 실현 누적 횟수 / levels: 3 모델링 → 2 촉진 → 1 자율
    def _level_from(nc: int) -> int:
        if nc >= IDC_FADE_AT[IDC_LEVEL_PROMPT]:
            return IDC_LEVEL_SOLO
        if nc >= IDC_FADE_AT[IDC_LEVEL_MODEL]:
            return IDC_LEVEL_PROMPT
        return IDC_LEVEL_MODEL
    idc_state = {
        "counts": {k: prev_counts.get(k, 0) for k in IDC_SCORED_KEYS},
        "levels": {k: _level_from(prev_counts.get(k, 0)) for k in IDC_SCORED_KEYS},
        "self": 0,            # 학습자가 스스로 매긴 별점(1~5, 0=안 매김)
        "review": "",         # 총평 전문 (스트리밍으로 다 받은 뒤 보관)
        "last_focus": "",     # 직전에 주입한 유발 지시의 대상 (같으면 다시 안 보냄)
        "final": None,        # 종료 시 산출한 9요소 프로파일
        # ── 교육적 개입 상태 (v95) ──
        "prompted": {k: 0 for k in IDC_SCORED_KEYS},  # 개입을 받고 실현한 횟수
        "intv_turn": {},      # 요소 key -> 개입한 시점의 학습자 턴 수 (실현하면 지운다)
        "intv_ids": set(),    # 이미 개입한 퀘스트 id (세션당 한 번)
        "intv_at": 0.0,       # 마지막 개입 시각
        "intv_n": 0,          # 개입 누적 횟수
    }
    # 라이브 세션 핸들 보관 — 분석 태스크가 대화 중에 비계 지시를 주입할 때 쓴다
    live = {"session": None}

    if rp_plan:
        system_prompt = build_roleplay_prompt(d, p, ui_lang, user_name, rp_plan, rp_style,
                                              idc_state["levels"], idc_state["counts"])
        print(f"[서버] 상황극 세션 — 주제={rp_plan['topic_ko']}, D={d}, P={p}, 말투={rp_style}, 이름={user_name or '(없음)'}")
    else:
        # 자유 대화에도 MKO 블록을 붙인다 — IDC는 상황극 전용 능력이 아니다.
        # 오히려 과업이 없는 자유 대화에서 화제·차례 관리가 순수하게 드러난다.
        system_prompt = build_system_prompt(d, p, ui_lang, user_name) \
            + build_mko_block(idc_state["levels"], idc_state["counts"],
                              native=LANG_NAMES.get(ui_lang, ""))
        print(f"[서버] 클라이언트 연결 성공 — 친밀도(D)={d}, 지위(P)={p}, 언어={ui_lang or 'ko'}, 이름={user_name or '(없음)'}")

    # ── 상황극 진행 상태 (자유 대화에서는 사용 안 함) ──
    convo = []           # [{"role":"user"|"ai","text":str}] — 같은 화자 연속 조각은 병합
    rp_progress = {
        "done": set(),                 # 충족된 단계 인덱스 (단조 증가)
        "quests": set(),               # 학습자가 해낸 퀘스트 id (누적)
        "abc": "",                     # 대화 유형 판정 A/B/C (이남호·이찬규 2025)
        "chains": {"시작": 0, "역시작": 0, "수정": 0, "고수": 0},   # 대화이동 연쇄 (학습자)
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
            "quests": sorted(rp_progress["quests"]),   # 오늘의 퀘스트 중 해낸 것
        }

    def _idc_absorb(keys) -> None:
        """분석이 돌려준 '학습자가 실현한 요소'를 누적하고 비계 수준을 한 칸씩 내린다(페이딩).
        한 번 해낸 요소는 시범을 거두고, 세 번 해낸 요소는 유발 자체를 멈춘다."""
        if not isinstance(keys, list):
            return
        turn_now = _user_turns()
        for k in keys:
            if not isinstance(k, str) or k not in idc_state["counts"]:
                continue
            idc_state["counts"][k] += 1
            # 개입을 받고 두 차례 안에 나온 실현은 '지시받은 것'으로 따로 센다.
            # 시켜서 한 거절과 스스로 한 거절이 같은 무게로 쌓이면 페이딩이 잘못 내려가고,
            # 제5장에서 이 로그가 무엇을 재는 자료인지 말할 수 없게 된다.
            t0 = idc_state["intv_turn"].get(k)
            if t0 is not None and turn_now - t0 <= 2:
                idc_state["prompted"][k] += 1
            idc_state["intv_turn"].pop(k, None)
            n = idc_state["counts"][k]
            lv = idc_state["levels"][k]
            if lv == IDC_LEVEL_MODEL and n >= IDC_FADE_AT[IDC_LEVEL_MODEL]:
                idc_state["levels"][k] = IDC_LEVEL_PROMPT
            elif lv == IDC_LEVEL_PROMPT and n >= IDC_FADE_AT[IDC_LEVEL_PROMPT]:
                idc_state["levels"][k] = IDC_LEVEL_SOLO

    async def send_idc_nudge():
        """근접발달영역 갱신 — 지금 학습자에게 필요한 요소만 골라 라이브 세션에 조용히 얹는다.
        end_of_turn=False라서 이 지시만으로는 호아랑이 말하지 않는다.
        학습자가 다음에 말할 때 그 맥락과 함께 읽힌다. 대상이 그대로면 보내지 않는다."""
        sess = live["session"]
        if sess is None:          # 자유 대화에도 비계 갱신을 보낸다
            return
        block = idc_focus_block(idc_state["levels"], idc_state["counts"],
                                native=LANG_NAMES.get(ui_lang, ""))
        sig = "|".join(f"{k}{idc_state['levels'][k]}" for k in IDC_SCORED_KEYS)
        if sig == idc_state["last_focus"]:
            return
        idc_state["last_focus"] = sig
        try:
            await sess.send(
                input=("[교사 지시 — 소리 내어 읽지 말 것. 이 내용을 학습자에게 언급하지도 말 것. "
                       "지금부터의 네 발화 방침만 갱신한다]" + block),
                end_of_turn=False,
            )
            solo = [k for k in IDC_SCORED_KEYS if idc_state["levels"][k] == IDC_LEVEL_SOLO]
            print(f"[IDC] 비계 갱신 — 자율 도달 {len(solo)}/{len(IDC_SCORED_KEYS)} {solo}")
        except Exception as e:
            # 주입에 실패해도 대화는 그대로 굴러가야 한다 (초기 시스템 프롬프트가 남아 있음)
            print(f"[IDC] 비계 주입 실패(무시): {e}")

    async def send_teach_intervention(qid: str) -> None:
        """교육적 개입 — 호아랑이 잠깐 극 밖으로 나와 '지금이 그 자리'라고 알린다.

        호아랑은 배역이 아니라 배역을 맡은 배우이므로(build_roleplay_prompt),
        무대 옆으로 비켜서는 것은 극을 깨지 않는다. 다만 그 비켜섬이 분명해야 하므로
        배역의 발화가 아니라 화면 층(빼꼼)으로 보낸다.

        ★ 기능만 알리고 표현은 주지 않는다. 한 퀘스트에 한 번뿐이다.
        형식이 필요하면 학습자가 🪜 도움말을 눌러 요청한다 — 그편이 맥락에 맞고,
        비계를 가져가는 주체가 학습자가 된다.
        """
        if scaf_level <= 0 or qid not in INTERVENABLE:
            return
        q = next((x for x in QUEST_LLM if x["id"] == qid), None)
        if q is None:
            return
        el = q["el"]
        # ① 이미 자율에 도달한 요소는 건드리지 않는다 — 페이딩을 스스로 되돌리는 셈이다
        if idc_state["levels"].get(el, IDC_LEVEL_MODEL) <= IDC_LEVEL_SOLO:
            return
        # ② 퀘스트 하나에 세션당 한 번
        if qid in idc_state["intv_ids"]:
            return
        # ③ 총량과 간격 — 자주 나오면 학습자가 개입을 좇게 되어 주도성을 해친다(v72~74의 판단)
        now = time.time()
        if idc_state["intv_n"] >= INTV_MAX.get(scaf_level, 0):
            return
        if now - idc_state["intv_at"] < INTV_GAP.get(scaf_level, 0):
            return
        idc_state["intv_ids"].add(qid)
        idc_state["intv_turn"][el] = _user_turns()
        idc_state["intv_at"] = now
        idc_state["intv_n"] += 1
        try:
            await websocket.send_text(json.dumps({
                "type": "intervene", "qid": qid, "el": el}))
            print(f"[개입] {qid}({el}) — 누적 {idc_state['intv_n']}회")
        except Exception as e:
            print(f"[개입] 전송 실패(무시): {e}")

    async def run_analysis(final: bool = False):
        """대화 로그를 보고 어떤 기능단계가 충족됐는지 판정 → 진행률 갱신·전송.
        릴레이(오디오)와 별개의 백그라운드 태스크로 돌며 이벤트루프를 막지 않는다."""
        if rp_progress["running"]:
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
            if rp_plan:
                transcript = "\n".join(
                    f"{'학습자(' + rp_plan['user_role'] + ')' if m['role'] == 'user' else '상대(' + rp_plan['ai_role'] + ')'}: {m['text'].strip()}"
                    for m in convo[-60:] if m["text"].strip())
                stages_txt = "\n".join(
                    f"{i}. {s['name']}: {s['desc']}" for i, s in enumerate(rp_plan["stages"]))
                task_line = f"과업 — 주제: {rp_plan['topic_ko']} / 달성 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']}"
            else:
                transcript = "\n".join(
                    f"{'학습자' if m['role'] == 'user' else '상대'}: {m['text'].strip()}"
                    for m in convo[-60:] if m["text"].strip())
                stages_txt = "(자유 대화 — 기능단계 없음. done은 빈 배열로 두라)"
                task_line = "과업 — 자유 주제 대화"
            idc_txt = "\n".join(
                f"- {e['key']}: {e['name']} — {e['sub']}" for e in IDC_TRAINABLE)
            quest_txt = "\n".join(f"- {q['id']}: {q['desc']}" for q in QUEST_LLM)
            intv_txt = "\n".join(
                f"- {q['id']}: {q['desc'].replace(' 적이 있다', '')}"
                for q in QUEST_LLM if q["id"] in INTERVENABLE)
            prompt = f"""다음은 한국어 학습자의 대화 기록이다.
{task_line}

[기능단계 목록]
{stages_txt}

[대화 기록]
{transcript}

[상호작용 대화 능력 요소]
{idc_txt}

다섯 가지를 판정하라.
(1) done — 위 대화에서 이미 실현(충족)된 기능단계의 번호를 모두.
    판정 기준: 그 단계의 의사소통 기능이 대화에서 실제로 수행되었으면 충족이다. 표현이 서툴러도 기능이 이루어졌으면 인정한다. 아직 시도되지 않았거나 실패한 단계는 제외한다.
(2) idc — 위 요소 가운데 **학습자가** 실제로 수행한 것의 key를 모두.
    ★상대(챗봇)가 한 것은 세지 마라. 학습자의 발화에서 확인되는 것만 고른다.
    표현이 서툴러도 그 기능을 해냈으면 인정한다. 해당 없으면 빈 배열.
(3) quest — 아래 목록 가운데 **학습자가** 실제로 한 것의 id를 모두. 없으면 빈 배열.
{quest_txt}
(4) abc — 지금까지의 대화가 어느 유형인지 (이남호·이찬규 2025의 기능단계 유형론).
    ★기능단계가 없는 자유 대화라면 빈 문자열("")로 두라. 이 유형론은 과업 대화에만 적용된다.
    "A" 단순형: 목적을 향해 곧장 가는 직선적 전개.
    "B" 반복형: 같은 기능 단계(질문-응답 등)가 맴돌며 반복됨.
    "C" 확장형: 목적 달성 후에도 재개·부가 화제로 대화가 확장됨.
(6) intervene — 지금 대화의 흐름에서 학습자가 **바로 다음 차례에** 자연스럽게 해 볼 수 있는 것 하나의 id.
    아래 목록에서만 고른다. 자리가 자연스럽지 않으면 빈 문자열("")로 두라. 억지로 고르지 마라.
    ★ (3)에서 학습자가 이미 해냈다고 적은 것은 고르지 마라.
{intv_txt}

(5) chains — **학습자가** 수행한 대화이동 연쇄의 횟수.
    시작(먼저 화제·요청을 엶) / 역시작(상대의 시작에 질문으로 되받음) /
    수정(자기 발화를 고쳐 다시 말함) / 고수(거절·난색에도 재요청).

JSON만 출력: {{"done":[번호,...],"idc":["key",...],"quest":["id",...],"abc":"A|B|C","chains":{{"시작":0,"역시작":0,"수정":0,"고수":0}},"intervene":""}}"""
            data = await _gen_json(prompt, timeout_s=15.0)
            pending_intv = ""
            if isinstance(data, dict):
                for i in data.get("done") or []:
                    try:
                        idx = int(i)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= idx < rp_progress["total"]:
                        rp_progress["done"].add(idx)
                _idc_absorb(data.get("idc"))
                # (4) 대화 유형 — 마지막 판정을 유지 (대화가 진행되며 A→C로 옮겨 갈 수 있다)
                # A/B/C는 기능단계의 유형론이다. 단계가 없는 자유 대화에 매기면
                # 재려는 것과 다른 것을 재게 된다 — 과업(상황극)에서만 판정한다.
                if rp_plan and data.get("abc") in ("A", "B", "C"):
                    rp_progress["abc"] = data["abc"]
                # (5) 대화이동 연쇄 — 최대값 유지 (판정 흔들림에 뒤로 가지 않게)
                ch = data.get("chains")
                if isinstance(ch, dict):
                    for k in ("시작", "역시작", "수정", "고수"):
                        try:
                            v = int(ch.get(k, 0))
                        except (TypeError, ValueError):
                            continue
                        rp_progress["chains"][k] = max(rp_progress["chains"][k], min(v, 30))
                # 퀘스트는 한 번 해내면 계속 인정한다(누적)
                for q in data.get("quest") or []:
                    if isinstance(q, str) and q in _QUEST_IDS:
                        rp_progress["quests"].add(q)
                # (6) 지금 개입할 만한 자리 — 실제 발동은 아래에서 조건을 따져 결정한다
                nq = data.get("intervene")
                if isinstance(nq, str) and nq in INTERVENABLE and nq not in rp_progress["quests"]:
                    pending_intv = nq
            turns = _user_turns()
            # 완료 판정: 모든 단계 충족 OR 마지막(마무리) 단계에 도달.
            # 중간 기능단계 하나를 건너뛰었어도 마무리 단계까지 갔으면 과업은 끝난 것으로 본다
            # (예: 12345 중 4를 건너뛰고 마무리(5) 도달 → 100% 완료 처리).
            last_idx = rp_progress["total"] - 1
            task_complete = rp_progress["total"] and (
                len(rp_progress["done"]) == rp_progress["total"]
                or last_idx in rp_progress["done"]
            )
            if task_complete:
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
            if not final:
                await send_idc_nudge()   # 비계를 학습자의 현재 수준에 맞춰 다시 조인다
                if pending_intv:
                    await send_teach_intervention(pending_intv)
        except Exception as e:
            print(f"[상황극] 단계 분석 실패: {e}")
        finally:
            rp_progress["running"] = False

    hint_state = {"running": False}

    async def send_hints():
        """🪜 도움말: 지금 대화 맥락에서 학습자의 '다음 턴'에 쓸 발화 2개 제안.

        v95부터 자유 대화에서도 쓴다. 두 모드의 축이 다르므로 무엇을 근거로 삼는지도 다르다.
          · 주제 대화 — 아직 못 밟은 기능 단계와 그 단계에서 연습한 표현이 축이다.
          · 자유 대화 — 과업이 없으므로 최근 흐름과 '지금 학습자에게 필요한 요소'가 축이다.
        교육적 개입이 기능만 알리는 데 반해, 이것은 형식을 준다. 다만 학습자가 눌러야 나온다.
        """
        if hint_state["running"]:
            return
        hint_state["running"] = True
        try:
            transcript = "\n".join(
                f"{'학습자' if m['role'] == 'user' else '상대'}: {m['text'].strip()}"
                for m in convo[-12:] if m["text"].strip()) or "(아직 대화 없음)"
            if rp_plan:
                unmet = [i for i in range(len(rp_plan["stages"])) if i not in rp_progress["done"]]
                idx = unmet[0] if unmet else len(rp_plan["stages"]) - 1
                st = rp_plan["stages"][idx]
                practiced = " / ".join(
                    (e.get("text", "") if isinstance(e, dict) else str(e))
                    for e in (st.get("expressions") or []))
                title = st["name"]
                fallback = [(e.get("text", "") if isinstance(e, dict) else str(e))
                            for e in (st.get("expressions") or [])][:2]
                head = (f"한국어 학습자가 음성 상황극 중이다. 잠시 막혀서 도움을 요청했다.\n"
                        f"- 학습자 역할: {rp_plan['user_role']} / 상대(챗봇) 역할: {rp_plan['ai_role']}\n"
                        f"- 과업 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']}\n"
                        f"- 지금 수행할 기능단계: {st['name']} — {st['desc']}\n"
                        f"- 연습했던 표현: {practiced or '(없음)'}")
                extra = "- 가능하면 연습했던 표현과 같거나 유사하게 하라."
            else:
                # 자유 대화 — 과업도 단계도 없다. 지금 학습자에게 가장 필요한 요소를 축으로 삼는다.
                need = sorted(
                    (e for e in IDC_TRAINABLE
                     if idc_state["levels"].get(e["key"], IDC_LEVEL_MODEL) > IDC_LEVEL_SOLO),
                    key=lambda e: idc_state["counts"].get(e["key"], 0))[:2]
                focus = " / ".join(f"{e['name']}({e['sub']})" for e in need) or "자연스러운 대화 잇기"
                title = need[0]["name"] if need else ""
                fallback = []
                head = ("한국어 학습자가 챗봇과 자유 대화 중이다. 잠시 막혀서 도움을 요청했다.\n"
                        f"- 지금 이 학습자에게 필요한 상호작용: {focus}")
                extra = ("- 위 상호작용이 자연스럽게 실현되는 발화면 더 좋다. "
                         "다만 억지로 끼워 맞추지 말고, 흐름에 맞는 말을 우선하라.")
            prompt = f"""{head}

[최근 대화]
{transcript}

학습자가 '지금 자기 차례에' 말하면 자연스러운 한국어 발화를 정확히 2개 제안하라.
- 상대의 마지막 말에 대한 대답으로 자연스러워야 한다.
{extra}
- 국제 통용 표준 교육과정 중급(4급 이하) 어휘·문법, 짧은 구어체로.
JSON만 출력: {{"hints":["",""]}}"""
            data = await _gen_json(prompt, timeout_s=12.0, temperature=0.7)
            hints = []
            if isinstance(data, dict):
                hints = [_clean_str(h, 80) for h in (data.get("hints") or []) if _clean_str(h, 80)][:2]
            if not hints:
                hints = fallback   # 주제 대화는 연습 표현으로, 자유 대화는 빈 목록으로
            await websocket.send_text(json.dumps({
                "type": "hint", "stage": title, "items": [h for h in hints if h]}))
        except Exception as e:
            print(f"[도움말] 생성 실패: {e}")
        finally:
            hint_state["running"] = False

    async def run_idc_profile() -> dict:
        """종료 시 1회 — 대화 전체를 〈표 42〉의 중급 평가 기준으로 재어 9요소 프로파일을 만든다.
        등급 상(2)·중(1)·하(0), 총점은 교실 전담 요소(비언어적 행위)를 빼고 100점으로 환산."""
        blank = {"items": [], "total": 0}
        if not convo:
            return blank
        transcript = "\n".join(
            f"{'학습자' if m['role'] == 'user' else '상대'}: {m['text'].strip()}"
            for m in convo[-80:] if m["text"].strip())
        rubric = "\n".join(
            f"[{e['key']}] {e['name']}\n  기준: {e['criteria']}" for e in IDC_TRAINABLE)
        prompt = f"""너는 한국어 말하기 평가 전문가다. 아래는 중급 한국어 학습자가 챗봇과 수행한 역할극 대화다.
{f"과업 — 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']} / 학습자 역할: {rp_plan['user_role']}" if rp_plan else "과업 — 자유 주제 대화 (기능 단계 범주는 대화를 열고 이어가고 맺는 능력으로 재라)"}

[대화 기록]
{transcript}

[평가 범주와 중급 평가 기준]
{rubric}

각 범주를 학습자의 수행만 보고 상·중·하로 판정하라.
- "hi"(상): 기준의 두 가지를 모두 안정적으로 해냈다.
- "mid"(중): 한 가지를 해냈거나, 시도했으나 불완전하다.
- "lo"(하): 시도가 없거나 기능이 이루어지지 않았다.
판정 원칙: 표현의 정확성이 아니라 **상호작용 기능의 수행 여부**로 재라. 문법이 틀려도 기능을 해냈으면 인정한다.
기회 자체가 없었던 범주는 "mid"로 두고 why에 그 사실을 적어라.
why는 학습자가 읽을 한 문장(30자 이내). 실제 발화를 근거로 칭찬하거나 다음에 해 볼 것을 말하라.
★ 읽는 사람은 한국어를 배우는 중급 학습자다. **다음 말은 절대 쓰지 마라** —
  화행, 레지스터, 담화, 대화이동, 기능 단계, 의사소통 전략, 명료화, 구인, 발화 순서, 연속체.
  대신 학습자가 바로 아는 말로 풀어 써라.
  예) "적절한 화행을 시작하지 못했습니다" → "먼저 말을 걸어 보면 좋겠어요"
      "레지스터를 선택하지 못했습니다"     → "상대에 맞는 높임말을 써 보세요"
      "기능 단계가 나타나지 않았습니다"     → "인사하고 끝인사까지 해 보세요"
  '~하지 못했습니다'보다 '~해 보세요'처럼 다음에 할 일로 적어라. 반드시 한국어로.
JSON만 출력: {{"items":[{{"key":"","grade":"hi|mid|lo","why":""}}]}}"""
        data = None
        try:
            data = await _gen_json(prompt, timeout_s=18.0)
        except Exception as e:
            # 여기서 되돌아가면 화면의 '상호작용 대화 능력' 칸이 통째로 빈다.
            # 판정을 못 받아도 아래에서 실시간 누적 횟수로 채워 내려보낸다.
            print(f"[IDC] 프로파일 생성 실패 — 누적 횟수로 대체: {e}")
        graded = {}
        if isinstance(data, dict):
            for it in (data.get("items") or []):
                if not isinstance(it, dict):
                    continue
                k = _clean_str(it.get("key"), 20)
                g = it.get("grade") if it.get("grade") in ("hi", "mid", "lo") else None
                if k in idc_state["counts"] and g:
                    graded[k] = {"grade": g, "why": _clean_str(it.get("why"), 60)}
        # 판정이 빠진 요소는 실시간 누적 횟수로 메운다 (LLM 실패 시에도 화면이 비지 않게)
        items, pts = [], 0
        for e in IDC_ELEMENTS:
            k = e["key"]
            if e["media"] == "class":
                # 비언어적 행위(✕)는 교실이 담당한다 → 화면에도 넣지 않는다.
                # 회색 줄로라도 두면 학습자가 '못 한 항목'으로 읽는다.
                continue
            if k in graded:
                grade, why = graded[k]["grade"], graded[k]["why"]
            else:
                n = idc_state["counts"].get(k, 0)
                grade, why = ("hi" if n >= 3 else "mid" if n >= 1 else "lo"), ""
            pts += {"hi": 2, "mid": 1, "lo": 0}[grade]
            items.append({"key": k, "name": e["name"], "layer": e["layer"],
                          "grade": grade, "why": why, "scored": True})
        total = round(100 * pts / (2 * len(IDC_SCORED_KEYS))) if IDC_SCORED_KEYS else 0
        print(f"[IDC] 프로파일 — 총점 {total}점 / " +
              " ".join(f"{i['key']}:{i['grade']}" for i in items if i["scored"]))
        return {"items": items, "total": total}

    async def run_review(send_piece=None) -> str:
        """총평 — 등급표 말고 사람이 쓴 것 같은 줄글로.
        요소별 상·중·하는 '무엇이 부족한가'는 알려 주지만 '어떻게 말했는가'는 못 담는다.
        실제 발화를 짚어 칭찬하고 고칠 곳을 알려 주는 선생님의 말이 따로 있어야 한다."""
        if not convo:
            return ""
        # 총평은 흐름만 보면 되므로 40턴이면 넉넉하다.
        # 80턴을 넣으면 입력이 두 배가 되어 첫 글자가 그만큼 늦게 나온다.
        transcript = "\n".join(
            f"{'학습자' if m['role'] == 'user' else '상대'}: {m['text'].strip()}"
            for m in convo[-40:] if m["text"].strip())
        # 요소별 등급을 기다리지 않는다 — 기다리면 총평이 늦어 화면에 못 붙는다.
        # 대신 대화 중 실시간으로 쌓인 실현 횟수를 참고로 준다.
        graded = "\n".join(
            f"- {e['name']}: {idc_state['counts'].get(e['key'], 0)}회"
            for e in IDC_TRAINABLE)
        task_line = (f"과업 — 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']} / "
                     f"학습자 역할: {rp_plan['user_role']}") if rp_plan else "자유 주제 대화"
        prompt = f"""너는 따뜻하고 꼼꼼한 한국어 선생님이다. 방금 대화 연습을 마친 중급 학습자에게
말로 해 주듯 총평을 써라.

{task_line}

[대화 기록]
{transcript}

[대화 중 관찰된 요소별 실현 횟수 — 참고만 하라]
{graded}

[쓰는 법]
- 200~320자. 줄글 두세 문단. 목록·번호·표를 쓰지 마라.
- **학습자가 실제로 한 말을 따옴표로 한두 개 인용하라.** 인용 없는 칭찬은 빈말이다.
- 순서: ① 이번 대화에서 잘한 것(구체적으로) → ② 다음에 이렇게 해 보자 한 가지
  → ③ 짧은 격려. ②는 하나만 골라라. 여러 개를 주면 아무것도 남지 않는다.
- 틀린 문장을 고쳐 줄 때는 "○○보다 △△가 더 자연스러워요"처럼 대안을 함께 줘라.
- 반드시 한국어. 중급(4급 이하) 어휘·문법. '-해요'체로 다정하게.
- ★ 다음 말은 절대 쓰지 마라 — 화행, 레지스터, 담화, 대화이동, 기능 단계,
  의사소통 전략, 명료화, 구인, 발화 순서, 연속체. 학습자가 바로 아는 말로 풀어 써라.
- 못한 것을 늘어놓지 마라. 학습자가 다시 해 보고 싶어지게 쓰는 것이 목적이다.

총평 글만 출력하라. 제목도 인사말도 붙이지 마라."""
        # ★ 다 쓴 뒤에 한꺼번에 주지 않고 쓰는 대로 흘려보낸다.
        #   학습자는 첫 글자를 1~2초 안에 보게 되고, 기다린다는 느낌 자체가 없어진다.
        buf = []
        try:
            stream = await asyncio.wait_for(
                client.aio.models.generate_content_stream(
                    model=_analysis_model["name"], contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.7)),
                timeout=12.0)
            async for chunk in stream:
                piece = getattr(chunk, "text", "") or ""
                if not piece:
                    continue
                buf.append(piece)
                if send_piece:
                    try:
                        await send_piece(piece)
                    except Exception:
                        return ""      # 학습자 쪽이 이미 닫혔다 — 더 만들 이유가 없다
            return re.sub(r"\n{3,}", "\n\n", "".join(buf).strip())[:900]
        except Exception as e:
            print(f"[총평] 생성 실패: {e}")
            return "".join(buf).strip()[:900]

    async def send_final_score():
        """종료 버튼 → 마지막 분석을 마치고 퍼센트를 점수로, IDC 프로파일을 함께 전송."""
        # ★ 총평을 맨 먼저 띄운다.
        #   예전에는 ①대기 ②최종 분석 ③프로파일 을 다 마친 뒤에야 총평을 시작해서
        #   첫 글자가 나오기까지 10~25초가 걸렸다. 총평은 프로파일 결과를 쓰지 않으므로
        #   기다릴 이유가 없다 — 여기서 바로 시작해 아래 작업과 나란히 돌린다.
        async def _piece(text: str):
            await websocket.send_text(json.dumps({"type": "review_chunk", "text": text}))

        async def _review_job():
            try:
                text = await run_review(send_piece=_piece)
            except Exception as e:
                print(f"[총평] 실패: {e}")
                text = ""
            idc_state["review"] = text
            try:
                await websocket.send_text(json.dumps({"type": "review_done", "text": text}))
                print(f"[총평] 완료 {len(text)}자")
            except Exception as e:
                print(f"[총평] 마무리 전송 실패(이미 닫힘): {e}")

        review_task = asyncio.create_task(_review_job())

        idc = {"items": [], "total": 0}
        for _ in range(40):  # 진행 중 분석이 있으면 최대 8초 대기
            if not rp_progress["running"]:
                break
            await asyncio.sleep(0.2)
        await run_analysis(final=True)          # 자유 대화도 idc·퀘스트·유형을 최종 판정
        # ★ 총평을 기다리지 않는다.
        #   학습자를 "점수 계산 중..."에 붙잡아 두면 "왜 안 넘어가지?" 하게 된다.
        #   요소 프로파일까지만 받아 결과를 먼저 띄우고, 총평은 다 되는 대로 따로 보낸다.
        idc = await run_idc_profile()
        idc_state["final"] = idc
        review = ""
        payload = _progress_payload() if rp_plan else {"stages": [], "percent": 0}
        await websocket.send_text(json.dumps({
            "type": "final_score",
            "percent": payload.get("percent", 0) if rp_plan else 0,
            "score": rp_progress["percent"] if rp_plan else 0,
            "stages": payload.get("stages", []),
            "idc": idc["items"],
            "idcTotal": idc["total"],
            "abc": rp_progress["abc"],                      # 대화 유형 A/B/C
            "chains": rp_progress["chains"],                # 대화이동 연쇄 횟수
            "review": review,                              # 총평은 뒤이어 따로 온다(type:"review")
            "idcCounts": dict(idc_state["counts"]),         # 기기 저장용 — 다음 세션 페이딩에 쓴다
            "idcPrompted": dict(idc_state["prompted"]),     # 그중 개입을 받고 해낸 것
            "interventions": idc_state["intv_n"],           # 이번 대화의 교육적 개입 횟수
            "scaf": scaf_level,                             # 학습자가 정한 비계 세기
            "quests": sorted(rp_progress["quests"]),
        }))
        print(f"[상황극] 최종 점수 전송: 진행률 {rp_progress['percent']}점 / IDC {idc['total']}점")

        # 총평은 위에서 이미 돌고 있다 — 여기서는 아무것도 하지 않는다.
        # (조각이 오는 대로 review_chunk 로 나가고, 끝나면 review_done 이 나간다)
        _ = review_task

    # ── 목소리: 호아랑은 갓 쓴 아기 호랑이라 기본은 남자아이 목소리.
    #    주제 대화에서 배역(점원·선생님·아주머니 등)을 맡으면 그에 맞는 목소리로 자동 전환.
    #    학습자가 홈에서 직접 고른 값(voice)이 있으면 그게 최우선. ──
    voice_name = pick_voice(rp_plan.get("ai_role", "") if rp_plan else "", voice_pref)
    print(f"[서버] 목소리 = {voice_name} (배역={rp_plan.get('ai_role','-') if rp_plan else '자유대화'}, 선택={voice_pref or 'auto'})")

    config_kwargs = dict(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=system_prompt)]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))),
    )
    # ── 발화 감지: 수동 모드 (push-to-talk) ──
    # 진단 결과(업로드 0KB·응답 1.4s인데도 STT가 30~60초 지연) → 오디오는 잘 도착하는데
    # Gemini의 '자동 발화감지(VAD)'가 "말 끝났다"를 늦게 판단하는 게 병목이었다.
    # 그래서 자동감지를 끄고(disabled=True), 클라이언트가 버튼으로 발화 시작/끝을
    # activity_start / activity_end 신호로 '명시적으로' 보낸다. → 텍스트 버튼처럼 즉시 확정.
    try:
        config_kwargs["realtime_input_config"] = types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
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
            live["session"] = gemini_session   # 분석 태스크가 비계 지시를 얹을 수 있게

            if rp_plan:
                first_msg = (f"(상황극 시작 — 학습자가 아직 말이 없다) 너는 지금 {rp_plan['place_ko']}의 {rp_plan['ai_role']}(이)야. "
                             f"학습자({rp_plan['user_role']})에게 이 상황에 맞는 자연스러운 첫 발화를 건네라. "
                             "설정된 말투와 페이더에 맞게, 1~2문장으로 짧게.")
            else:
                first_msg = "(대화 시작 — 학습자가 아직 말이 없다) 지금 설정된 친밀도·지위 페이더에 맞는 말투로 첫인사를 건네고, 가벼운 질문 하나로 대화를 열어줘."

            # ── 말걸기 연습: 학습자가 먼저 입을 열 기회를 준다 ──
            # 접속 후 잠시 기다렸다가(기본 4초, FIRST_SPEAK_WAIT_S로 조절)
            # 학습자 발화가 없을 때만 호아랑이 먼저 말을 건다.
            user_spoke = {"flag": False}
            first_wait = float(os.environ.get("FIRST_SPEAK_WAIT_S", "4"))

            async def greet_if_silent():
                try:
                    await asyncio.sleep(first_wait)
                    if not user_spoke["flag"]:
                        await gemini_session.send(input=first_msg, end_of_turn=True)
                except Exception:
                    pass

            greeter_task = asyncio.create_task(greet_if_silent())

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
                            elif event.get("type") == "activity_start":
                                # push-to-talk: 버튼을 누른 순간 — "발화 시작" 명시
                                user_spoke["flag"] = True  # 학습자가 먼저 말함 → 자동 첫인사 취소
                                await gemini_session.send_realtime_input(activity_start=types.ActivityStart())
                            elif event.get("type") == "activity_end":
                                # push-to-talk: 버튼을 뗀 순간 — "발화 끝" 명시 → 턴 즉시 확정
                                await gemini_session.send_realtime_input(activity_end=types.ActivityEnd())
                            elif event.get("type") == "end_session":
                                # 종료 버튼: 최종 분석 → 점수 치환 → 클라이언트가 받고 연결을 닫는다
                                await send_final_score()
                            elif event.get("type") == "self_rating":
                                # 학습자가 스스로 매긴 별점(1~5). 점수에는 넣지 않는다.
                                # 자기 평가와 실제 수행의 차이가 5장의 자료가 된다.
                                v = _clamp_int(event.get("value"), 0, 5, 0)
                                if v:
                                    idc_state["self"] = v
                                    print(f"[자기평가] 별 {v}/5")
                            elif event.get("type") == "hint_request":
                                # 🪜 비계 요청 — 백그라운드 생성 (오디오 릴레이를 막지 않음)
                                asyncio.create_task(send_hints())
                            elif event.get("type") == "text" and event.get("text"):
                                # 빠른 요청 버튼 등 텍스트 턴 주입 (대화 맥락 유지)
                                user_spoke["flag"] = True
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
            greeter_task.cancel()

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

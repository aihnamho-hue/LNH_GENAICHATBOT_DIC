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

# 배포 확인용 버전 — 화면 좌측 상태줄과 서버 로그에 표시됨 (버전 올릴 때 날짜도 갱신!)
# ※ 변경 이력은 개발일지_CHANGELOG.md에 버전·날짜별로 기록할 것 (박사 논문 개발 기록용)
APP_VERSION = "v20"
APP_DATE = "2026-07-15"

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


# ============================================================
# 한국어 수준 제약 — '2017년 국제 통용 한국어 표준 교육과정 적용 연구(4단계)
# 어휘, 문법 등급 목록' 준수. 마사마사의 모든 발화는 중급(4급 이하)로 제한.
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
    """표현 항목 정규화 — 신형 {"text","cue"} / 구형 "문자열" 모두 수용.
    cue = 그 표현을 자연스럽게 이끌어내는 상대방 발화 (발화 연습의 말차례 교환용)."""
    if isinstance(e, dict):
        text = _clean_str(e.get("text"), 60)
        cue = _clean_str(e.get("cue"), 60)
    else:
        text, cue = _clean_str(e, 60), ""
    return {"text": text, "cue": cue} if text else None


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
    return {
        "topic_ko": _clean_str(data.get("topic_ko"), 60) or "자유 주제",
        "goal_ko": _clean_str(data.get("goal_ko"), 100) or "대화 목적 달성",
        "place_ko": _clean_str(data.get("place_ko"), 60) or "일상 공간",
        "user_role": _clean_str(data.get("user_role"), 40) or "학습자",
        "ai_role": _clean_str(data.get("ai_role"), 40) or "대화 상대",
        "stages": stages,
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
    """장소나 목적 중 하나만 적으면 나머지(목적 3단계·장소·역할·화계)를 '예)'로 자동 추천.
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
5) style: 이 관계에서 자연스러운 화계 — "polite"(존댓말) 또는 "banmal"(반말).
6) style_reason: 그 화계가 자연스러운 이유 한 구절 (15자 내외, 예: "처음 보는 점원과 손님 사이").
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
    if not topic and not goal and not place:
        raise HTTPException(status_code=400, detail="topic_goal_or_place_required")

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
   - expressions: 학습자({my_role or '학습자'} 역할)가 이 단계에서 쓸 만한 자연스러운 한국어 표현 2~3개. 실제 구어체로.
     표현과 cue는 모두 국제 통용 한국어 표준 교육과정 중급(4급 이하) 어휘·문법 범위로 작성하라.
     각 표현은 객체로: text = 학습자 발화, cue = 그 발화가 자연스러운 대답이 되는 상대방({ai_role or '상대'}) 발화.
     예) cue "어떻게 오셨어요?" → text "택배 좀 부치려고 하는데요".
     cue는 발화 연습(말차례 교환)에 쓰인다. text가 대화를 먼저 여는 발화면 cue는 빈 문자열로.

JSON만 출력하라. 스키마:
{{"topic_ko":"","goal_ko":"","place_ko":"","user_role":"","ai_role":"","stages":[{{"name":"","native":"","desc":"","expressions":[{{"text":"","cue":""}}]}}]}}"""

    data = await _gen_json(prompt, timeout_s=40.0)
    plan = _validate_plan(data)
    if plan is None and not (data is None and _quota_exhausted()):
        # 쿼터 소진이 아닐 때만 1회 재시도 (429에서 재시도는 쿼터 낭비)
        data = await _gen_json(prompt, timeout_s=40.0)
        plan = _validate_plan(data)
    if plan is None:
        raise HTTPException(status_code=502, detail=("plan_generation_failed | " + _fail_reason(data))[:250])

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


# ============================================================
# 발화 연습용 Gemini TTS/STT — 기기 내장 음성 대신 실감나는 음성으로.
# TTS 모델도 단종(404) 시 후보 → API 목록 순으로 자동 전환.
# ============================================================
TTS_MODEL = os.environ.get("TTS_MODEL", "").strip() or "gemini-2.5-flash-preview-tts"
TTS_VOICE = os.environ.get("TTS_VOICE", "").strip() or "Kore"
_tts_model = {"name": TTS_MODEL}
_tts_tried = set()
_tts_cache = {}  # text -> pcm bytes (같은 문장 반복 재생 시 API 호출 절약)


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
    if text in _tts_cache:
        return Response(content=_tts_cache[text], media_type="audio/pcm")

    last_err = ""
    for _ in range(3):
        model_name = _tts_model["name"]
        try:
            cfg = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=TTS_VOICE))))
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(model=model_name, contents=text, config=cfg),
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
            _tts_cache[text] = data
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
    hint = _clean_str(hint, 120)
    if hint:
        prompt = (
            "다음 오디오는 한국어를 배우는 외국인 학습자의 짧은 발화다. 억양이 어색하고 발음이 부정확할 수 있다.\n"
            f"학습자는 지금 이 문장을 말하는 연습을 하고 있다: \"{hint}\"\n"
            "오디오를 듣고 들리는 대로 한국어로 전사하라.\n"
            "- 발음이 목표 문장과 대체로 비슷하게 들리면, 목표 문장 표기를 따라 적어라 (학습자 발음에 관대하게).\n"
            "- 학습자가 명백히 다른 말을 했으면 들리는 대로 적어라. 목표 문장을 그대로 베끼지 마라.\n"
            "- 아무 말도 안 들리면 빈 문자열을 출력하라.\n"
            "전사 텍스트만 출력하고 다른 말은 하지 마라.")
    else:
        prompt = ("다음 오디오는 한국어를 배우는 외국인 학습자의 짧은 발화다. 들리는 대로 한국어로 전사하라. "
                  "발음이 서툴러도 가장 그럴듯한 한국어 문장으로 적어라. 전사 텍스트만 출력하고 다른 말은 하지 마라.")
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
    resp = templates.TemplateResponse(request=request, name="index.html")
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
        base = f"마사마사대화_{ts}" + (f"_{safe_name}" if safe_name else "") + f"_D{d}_P{p}"
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

    hint_state = {"running": False}

    async def send_hints():
        """🪜 비계(스캐폴딩): 지금 대화 맥락에서 학습자의 '다음 턴'에 쓸 발화 2개 제안.
        연습했던 표현과 같거나 유사하게 유도하고, 실패 시 연습 표현으로 폴백."""
        if rp_plan is None or hint_state["running"]:
            return
        hint_state["running"] = True
        try:
            unmet = [i for i in range(len(rp_plan["stages"])) if i not in rp_progress["done"]]
            idx = unmet[0] if unmet else len(rp_plan["stages"]) - 1
            st = rp_plan["stages"][idx]
            practiced = " / ".join(
                (e.get("text", "") if isinstance(e, dict) else str(e))
                for e in (st.get("expressions") or []))
            transcript = "\n".join(
                f"{'학습자' if m['role'] == 'user' else '상대'}: {m['text'].strip()}"
                for m in convo[-12:] if m["text"].strip()) or "(아직 대화 없음)"
            prompt = f"""한국어 학습자가 음성 상황극 중이다. 잠시 막혀서 도움을 요청했다.
- 학습자 역할: {rp_plan['user_role']} / 상대(챗봇) 역할: {rp_plan['ai_role']}
- 과업 목적: {rp_plan['goal_ko']} / 장소: {rp_plan['place_ko']}
- 지금 수행할 기능단계: {st['name']} — {st['desc']}
- 연습했던 표현: {practiced or '(없음)'}

[최근 대화]
{transcript}

학습자가 '지금 자기 차례에' 말하면 자연스러운 한국어 발화를 정확히 2개 제안하라.
- 상대의 마지막 말에 대한 대답으로 자연스러워야 한다.
- 가능하면 연습했던 표현과 같거나 유사하게 하라.
- 국제 통용 표준 교육과정 중급(4급 이하) 어휘·문법, 짧은 구어체로.
JSON만 출력: {{"hints":["",""]}}"""
            data = await _gen_json(prompt, timeout_s=12.0, temperature=0.7)
            hints = []
            if isinstance(data, dict):
                hints = [_clean_str(h, 80) for h in (data.get("hints") or []) if _clean_str(h, 80)][:2]
            if not hints:
                # 생성 실패 → 이 단계의 연습 표현으로 폴백
                hints = [(e.get("text", "") if isinstance(e, dict) else str(e))
                         for e in (st.get("expressions") or [])][:2]
            await websocket.send_text(json.dumps({
                "type": "hint", "stage": st["name"], "items": [h for h in hints if h]}))
        except Exception as e:
            print(f"[상황극] 비계 생성 실패: {e}")
        finally:
            hint_state["running"] = False

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

            if rp_plan:
                first_msg = (f"(상황극 시작 — 학습자가 아직 말이 없다) 너는 지금 {rp_plan['place_ko']}의 {rp_plan['ai_role']}(이)야. "
                             f"학습자({rp_plan['user_role']})에게 이 상황에 맞는 자연스러운 첫 발화를 건네라. "
                             "설정된 화계와 페이더에 맞게, 1~2문장으로 짧게.")
            else:
                first_msg = "(대화 시작 — 학습자가 아직 말이 없다) 지금 설정된 친밀도·지위 페이더에 맞는 말투로 첫인사를 건네고, 가벼운 질문 하나로 대화를 열어줘."

            # ── 말걸기 연습: 학습자가 먼저 입을 열 기회를 준다 ──
            # 접속 후 잠시 기다렸다가(기본 4초, FIRST_SPEAK_WAIT_S로 조절)
            # 학습자 발화가 없을 때만 마사마사가 먼저 말을 건다.
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

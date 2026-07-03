import os
import asyncio
import json
import base64
import struct
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from google import genai
from google.genai import types

# 로컬 실행 시 .env 파일에서 환경변수를 읽어온다. (배포 환경에서는 호스팅
# 플랫폼이 환경변수를 직접 주입하므로 .env 파일이 없어도 문제 없음)
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 햄스터 이미지 등 정적 파일 서빙
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일 또는 호스팅 환경변수를 확인하세요.")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# ============================================================
# 공개 배포 시 비용 남용 방지 장치
# - ACCESS_CODE: 설정하면 이 코드를 아는 사람만 접속 가능 (미설정 시 누구나 접속)
# - MAX_CONCURRENT_SESSIONS: 동시 접속 가능한 대화 세션 수 제한
# ============================================================
ACCESS_CODE = os.environ.get("ACCESS_CODE", "").strip()
MAX_CONCURRENT_SESSIONS = int(os.environ.get("MAX_CONCURRENT_SESSIONS", "5"))
_active_sessions = 0
_session_lock = asyncio.Lock()

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

# 한국어 선생님 역할 (몰래 수행 — 절대 티내지 마)
- 사용자는 한국어 학습자야. 문법 오류는 직접 지적하지 말고, 자연스러운 표현으로 슬쩍 되받아줘 (Recast).
  예) 사용자: "어제 친구 만났어서 좋았어" -> 너: "아 어제 친구 만나서 좋았구나! 뭐 했는데?"
- 사용자가 말할 기회를 많이 갖도록 짧게 말하고 질문을 던져.

# 발화 스타일 (공통)
- 음성 대화니까 한 번에 2~3문장 이내로 짧게.
- 문어체 금지. "그러나/하지만" 대신 "근데/아 그리고".

# 발화 속도와 학습자 배려 (중요)
- 기본은 자연스럽고 편안한 속도로 말해.
- 학습자가 "천천히 말해 주세요", "조금만 천천히", "빨라요" 라고 하면 → 속도를 확 늦추고 또박또박, 한 어절씩 끊어서 발음해. 이게 한국어 연습의 중요한 전략이니 흔쾌히 응해줘.
- "방금 뭐라고 했어요?", "다시 한 번만", "네?" 하면 → 짜증 없이 같은 말을 더 천천히, 또는 더 쉬운 표현으로 바꿔서 다시 말해줘 (rephrase).
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


def _band(v: int) -> str:
    if v <= 33:
        return "low"
    if v <= 66:
        return "mid"
    return "high"


def build_system_prompt(d: int, p: int) -> str:
    d_band, p_band = _band(d), _band(p)
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
    return BASE_PERSONA + coord + D_RULES[d_band] + sep + P_RULES[p_band] + sep + fusion


def calculate_rms_level(pcm_bytes: bytes) -> float:
    if not pcm_bytes:
        return 0.0
    sample_count = len(pcm_bytes) // 2
    if sample_count == 0:
        return 0.0
    samples = struct.unpack(f"<{sample_count}h", pcm_bytes[: sample_count * 2])
    rms = (sum(s * s for s in samples) / sample_count) ** 0.5
    return round(min(1.0, (rms / 32768.0) * 4.0), 3)


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# 서비스 워커는 루트 경로에서 서빙해야 전체 사이트를 제어(scope '/')할 수 있음
@app.get("/sw.js")
async def get_service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    global _active_sessions
    await websocket.accept()

    # 접속 코드 검증 (ACCESS_CODE가 설정된 경우에만)
    if ACCESS_CODE:
        supplied_code = websocket.query_params.get("code", "")
        if supplied_code != ACCESS_CODE:
            await websocket.send_text(json.dumps({
                "type": "error",
                "code": "bad_access_code",
                "message": "접속 코드가 올바르지 않습니다.",
            }))
            await websocket.close()
            print("[서버] 접속 거부 — 잘못된 접속 코드")
            return

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

    system_prompt = build_system_prompt(d, p)
    print(f"[서버] 클라이언트 연결 성공 — 친밀도(D)={d}, 지위(P)={p}")

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=system_prompt)]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    model_id = "models/gemini-2.5-flash-native-audio-latest"

    try:
        async with client.aio.live.connect(model=model_id, config=config) as gemini_session:
            print("[서버] Gemini Live API 세션 연결 성공")

            await gemini_session.send(
                input="(대화 시작) 지금 설정된 친밀도·지위 페이더에 맞는 말투로 첫인사를 건네고, 가벼운 질문 하나로 대화를 열어줘.",
                end_of_turn=True
            )

            async def client_to_gemini():
                try:
                    while True:
                        data = await websocket.receive_text()
                        event = json.loads(data)
                        if event.get("type") == "audio" and "data" in event:
                            audio_bytes = base64.b64decode(event["data"])
                            await gemini_session.send_realtime_input(
                                audio=types.Blob(
                                    data=audio_bytes,
                                    mime_type="audio/pcm;rate=16000"
                                )
                            )
                        elif event.get("type") == "text" and event.get("text"):
                            # 빠른 요청 버튼 등 텍스트 턴 주입 (대화 맥락 유지)
                            await gemini_session.send(input=event["text"], end_of_turn=True)
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
                                    audio_bytes = part.inline_data.data
                                    await websocket.send_text(json.dumps({
                                        "type": "audio",
                                        "data": base64.b64encode(audio_bytes).decode("utf-8"),
                                        "volume": calculate_rms_level(audio_bytes),
                                    }))
                        if sc.input_transcription and sc.input_transcription.text:
                            await websocket.send_text(json.dumps({
                                "type": "user_text",
                                "text": sc.input_transcription.text,
                            }))
                        if sc.output_transcription and sc.output_transcription.text:
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

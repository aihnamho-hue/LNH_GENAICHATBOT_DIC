# -*- coding: utf-8 -*-
"""v107 통합 점검 — 코드 모양이 아니라 **실제로 돌려 보고** 확인한다.

정규식으로 '이렇게 생겼나'를 재는 검사는 조사·말투·판정 같은 것을 못 잡는다.
서버를 띄우지 않고 함수만 떼어 실행해, 학습자가 겪을 결과를 직접 만들어 본다."""
import re, io, sys, hashlib, base64, struct, asyncio, os, time

# ★ 세션마다 바뀌는 절대경로를 박아 두면 다음 판에서 반드시 깨진다.
#   인자로 받고, 없으면 이 파일이 있는 폴더를 본다.
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()
HT = io.open(f"{ROOT}/app.html", encoding="utf-8").read()

fail = []
def ok(sec, msg, cond, extra=""):
    print(("  ✅ " if cond else "  ❌ ") + msg + (("   " + str(extra)) if not cond and extra else ""))
    if not cond:
        fail.append(f"{sec} · {msg}")

def grab(pat, flags=re.S | re.M):
    m = re.search(pat, PY, flags)
    assert m, f"못 찾음: {pat[:40]}"
    return m.group(0)

def grab1(pat):          # 한 줄짜리 — re.S 를 주면 '.' 가 줄을 넘어가 통째로 집는다
    return grab(pat, re.M)

# ═══════════════════════════════════════════════════════════
print("\n════════ ③ 목소리 배정 (v107 새로 고침) ════════")
ns = {"re": re, "hashlib": hashlib, "os": os}
exec(grab(r'^VOICE_TABLE = \{[\s\S]*?\n\}'), ns)
exec(grab1(r'^HOARANG_VOICE_KEY = .*$'), ns)
for n in ("_ROLE_FEMALE", "_ROLE_MALE", "_ROLE_ELDER", "_ROLE_ADULT", "_ROLE_YOUNG"):
    exec(grab(rf'^{n} = \([\s\S]*?\)\n'), ns)
exec(grab(r'^def pick_voice\([\s\S]*?(?=^\S|\Z)'), ns)
pv = ns["pick_voice"]
KIND = {"Puck": "남아", "Fenrir": "남아", "Leda": "여아", "Charon": "성인남",
        "Orus": "성인남", "Kore": "성인여", "Aoede": "성인여",
        "Algenib": "노년남", "Gacrux": "노년여"}
CASES = [
    ("여자친구의 남자친구", "남"), ("남자친구의 여자친구", "여"),
    ("여자친구 부모님", "성인"), ("남자친구 부모님", "성인"),
    ("여자친구 아버지", "성인남"), ("여자친구 어머니", "성인여"),
    ("여자친구 할아버지", "노년남"), ("여자친구 할머니", "노년여"),
    ("친구", "아"), ("반 친구", "아"), ("같은 반 여학생", "여아"),
    ("옷 가게 점원", "성인"), ("병원 접수처 직원", "성인"), ("면접관", "성인"),
    ("선생님", "성인"), ("사장님", "성인"), ("시장 상인", "성인"),
    ("아저씨", "성인남"), ("아주머니", "성인여"), ("할머니", "노년여"),
]
for role, want in CASES:
    v = pv(role); k = KIND.get(v, v)
    ok("목소리", f"{role:18} → {k}", want in k, k)
# 같은 역할이면 늘 같은 목소리여야 한다 (수업 중 널뛰지 않게)
ok("목소리", "같은 역할이면 언제나 같은 목소리",
   all(pv("옷 가게 점원") == pv("옷 가게 점원") for _ in range(5)))
ok("목소리", "배역이 없으면 호아랑 본래 목소리", pv("") == ns["VOICE_TABLE"]["boy"])
ok("목소리", "학습자가 고른 목소리가 최우선", pv("할머니", "boy") == ns["VOICE_TABLE"]["boy"])

# ═══════════════════════════════════════════════════════════
print("\n════════ ④ 화자 뒤바뀜 잡기 (v107 신설) ════════")
ns2 = {}
exec(grab(r'^_DEFERENTIAL = \([\s\S]*?\)\n'), ns2)
exec(grab(r'^def _deference_offenders\([\s\S]*?(?=^\S|\Z)'), ns2)
dof = ns2["_deference_offenders"]
sc = [{"speaker": "ai", "text": "아니, 지금 여기서 뭐 하는 거예요?"},
      {"speaker": "user", "text": "죄송합니다. 제가… 그게…"},
      {"speaker": "ai", "text": "네, 명심하겠습니다."},
      {"speaker": "user", "text": "다시는 이런 일이 없도록 하겠습니다."},
      {"speaker": "ai", "text": "앞으로 조심하겠습니다."},
      {"speaker": "ai", "text": "앞으로는 그러지 마세요."}]
ok("화자", "윗사람(반말 쪽)의 아랫사람 말을 잡는다", dof(sc, "polite", "banmal") == [2, 4],
   dof(sc, "polite", "banmal"))
ok("화자", "아랫사람의 말은 안 건드린다", 1 not in dof(sc, "polite", "banmal"))
ok("화자", "제대로 된 윗사람 말은 안 잡는다", 5 not in dof(sc, "polite", "banmal"))
ok("화자", "대등한 사이면 판단하지 않는다", dof(sc, "polite", "polite") == [])
ok("화자", "학습자가 윗사람인 경우도 잡는다",
   dof([{"speaker": "user", "text": "네, 명심하겠습니다."}], "banmal", "polite") == [0])

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑤ 발화 연습 자리 고르기 ════════")
ns3 = {}
exec(grab(r'^def _balance_expr_positions\([\s\S]*?(?=^\S|\Z)'), ns3)
bal = ns3["_balance_expr_positions"]
def pos(e):
    return "시작" if not e.get("cue") else ("3항" if e.get("follow") else "반응")
st = {"expressions": [{"text": "네, 안녕하세요", "cue": "어서 오세요", "follow": ""},
                      {"text": "저 파란 옷 좀 보여 주세요", "cue": "뭐 찾으세요?", "follow": ""},
                      {"text": "좀 비싼데 깎아 주세요", "cue": "3만 원이에요", "follow": ""}]}
bal([st]); got = [pos(e) for e in st["expressions"]]
ok("연습", "전부 '반응'이면 편다", "시작" in got and got.count("반응") < 3, got)
st2 = {"expressions": [{"text": "저기요", "cue": "", "follow": ""},
                       {"text": "좀 비싼데요", "cue": "3만 원이에요", "follow": ""},
                       {"text": "세 개 주세요", "cue": "깎아 드릴게요", "follow": "여기요"}]}
before = [pos(e) for e in st2["expressions"]]; bal([st2])
ok("연습", "이미 고르면 안 건드린다", before == [pos(e) for e in st2["expressions"]])
st3 = {"expressions": [{"text": "안녕하세요", "cue": "어서 오세요", "follow": ""},
                       {"text": "감사합니다", "cue": "여기요", "follow": ""}]}
bal([st3])
ok("연습", "둘뿐이면 3항은 안 만든다", "3항" not in [pos(e) for e in st3["expressions"]])

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑥ 비계가 대화를 끊지 않는가 ════════")
ns4 = {"re": re}
exec(grab(r'^_DEAD_END = re\.compile\([\s\S]*?\)\n'), ns4)
exec(grab(r'^def _is_dead_end\([\s\S]*?(?=^\S|\Z)'), ns4)
dead = ns4["_is_dead_end"]
for s in ["아니, 없어.", "음, 없어.", "네.", "몰라요.", "괜찮아요.", "그렇구나.", "응.", "없어요."]:
    ok("비계", f"닫는 말을 거른다: {s}", dead(s))
for s in ["아, 그럼 이번엔 내가 하나 물어봐도 돼?", "지금은 잘 모르겠어. 너는 뭐가 재밌어?",
          "네, 좋아요. 그런데 시간은 언제가 괜찮으세요?", "좀 비싼데요, 깎아 주시면 안 될까요?",
          "네, 그럼 세 개 주세요.", "이거 얼마예요?", "다른 색도 있어요?"]:
    ok("비계", f"이어 가는 말은 살린다: {s[:22]}", not dead(s))

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑦ 소리 — 문법 표기·쉼표·WAV ════════")
ns5 = {"re": re, "CLOUD_TTS_COMMA_PAUSE": True}
exec(grab(r'^_GRAMMAR_MARK = re\.compile\([\s\S]*?\)\n'), ns5)
exec(grab(r'^def _tts_breathe\([\s\S]*?(?=^\S|\Z)'), ns5)
exec(grab(r'^def _tts_grammar\([\s\S]*?(?=^\S|\Z)'), ns5)
gr, br = ns5["_tts_grammar"], ns5["_tts_breathe"]
for src, want in [("-(으)려고 하다", "려고 하다"), ("-(으)ㄴ/는다고 하다", "는다고 하다"),
                  ("-아/어요", "어요"), ("-(으)면", "면"), ("-기 때문에", "기 때문에"),
                  ("안녕하세요", "안녕하세요")]:
    ok("소리", f"문법 표기 {src} → {want}", gr(src) == want, gr(src))
ok("소리", "숫자 쉼표는 안 건드린다", "1,000원" in br("1,000원입니다"), br("1,000원입니다"))
ok("소리", "쉼표 뒤에 숨을 넣는다", br("아, 그래요?") == "아, … 그래요?", br("아, 그래요?"))
ok("소리", "쉼표 없으면 그대로", br("안녕하세요.") == "안녕하세요.")
ns6 = {}
exec(grab(r'^def _pcm_from_wav\([\s\S]*?(?=^\S|\Z)'), ns6)
wav_f = ns6["_pcm_from_wav"]
p = bytes(range(256)) * 8
def mkwav(payload, extra=False):
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, 24000, 48000, 2, 16)
    mid = struct.pack("<4sI", b"LIST", 6) + b"INFOxx" if extra else b""
    data = struct.pack("<4sI", b"data", len(payload)) + payload
    body = b"WAVE" + fmt + mid + data
    return struct.pack("<4sI", b"RIFF", len(body)) + body
ok("소리", "WAV 알맹이를 정확히 꺼낸다", wav_f(mkwav(p)) == p)
ok("소리", "청크가 껴 있어도 꺼낸다", wav_f(mkwav(p, True)) == p)
ok("소리", "이미 PCM이면 그대로", wav_f(p) == p)
ok("소리", "빈 바이트도 안 터진다", wav_f(b"") == b"")
def _rate(name):
    m = re.search(name + r'\s*=\s*float\(.*?or\s*"([\d.]+)"', PY)
    return float(m.group(1)) if m else None
rate, crate = _rate("CLOUD_TTS_RATE"), _rate("CLOUD_TTS_CHILD_RATE")
ok("소리", f"말 빠르기 0.9 ({rate} / {crate})", rate == 0.9 and crate == 0.9)

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑧ 넛지 — 밴드·목록·맥락 ════════")
G = eval(re.search(r'INTV_TURN_GAP = (\{[^}]*\})', PY).group(1))
F = eval(re.search(r'INTV_FORCE_GAP = (\{[^}]*\})', PY).group(1))
M = eval(re.search(r'INTV_MAX\s*= (\{[^}]*\})', PY).group(1))
W = int(re.search(r'INTV_WARMUP = (\d+)', PY).group(1))
A = set(eval(re.search(r'INTV_ANYTIME = (\[[^\]]*\])', PY).group(1)))
ok("넛지", "바닥 간격 > 최소 간격 (안 그러면 바닥이 막힌다)",
   all(F[l] > G[l] for l in (1, 2, 3)), f"{F} vs {G}")
ok("넛지", "페이더가 올라갈수록 자주", G[1] > G[2] > G[3] and F[1] > F[2] > F[3])
ok("넛지", "페이더가 올라갈수록 많이", M[1] < M[2] < M[3])
ctx_need = {"qParaphrase", "qEmpathy", "qContinuer", "qFiller"}
ok("넛지", "맥락 필요한 것은 '아무 때나'에서 뺐다", not (A & ctx_need), A & ctx_need)
import random
def sim(lv, turns, hit):
    n, last = 0, W; random.seed(11)
    for t in range(1, turns + 1):
        if t < W or n >= M[lv]: continue
        picked = random.random() < hit
        overdue = F[lv] > 0 and (t - (last if n else W)) >= F[lv]
        if not picked and not overdue: continue
        if n and t - last < G[lv]: continue
        n += 1; last = t
    return n
print("     19차례 대화에서 나오는 횟수")
for lv in (1, 2, 3):
    print(f"       페이더 {lv}: 최소 {sim(lv,19,0)}회 · 보통 {sim(lv,19,.3)}회 · 많이 {sim(lv,19,.7)}회 (상한 {M[lv]})")
ok("넛지", "「적게」도 최소 2회는 나온다", sim(1, 19, 0) >= 2, sim(1, 19, 0))
ok("넛지", "「많이」는 최소 6회 이상", sim(3, 19, 0) >= 6, sim(3, 19, 0))

# ── 넛지 이름을 실제로 만들어 본다 ──
FORM = {}
for k, a, b, c in re.findall(r'(q\w+):\s*\["([^"]*)",\s*"([^"]*)",\s*"([^"]*)"\]',
                             re.search(r'const QUEST_FORM = \{([\s\S]*?)\n    \};', HT).group(1)):
    FORM[k] = [a, b, c]
wrap = re.search(r'\bqWrap:"((?:[^"\\]|\\.)*)"', HT).group(1)
ok("넛지", "문형이 넉넉하다(14개 이상)", len(FORM) >= 14, len(FORM))
ok("넛지", "감싸는 말이 '보기'로 읽힌다", "처럼" in wrap, wrap)
bad_render = []
for k, tiers in FORM.items():
    for t, form in enumerate(tiers):
        line = wrap.replace("%s", form)
        if "%" in line or not form.strip():
            bad_render.append(f"{k}/{t}")
ok("넛지", "42가지(14×3)가 모두 문장이 된다", not bad_render, bad_render[:3])
solo = [k for k, v in FORM.items() if all("·" not in x for x in v)]
ok("넛지", "보기가 하나뿐인 것은 4개 이하 (대본이 되지 않게)", len(solo) <= 4, solo)

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑨ 서버↔화면 짝 맞추기 ════════")
srv = {m.group(1): m.group(2) for m in re.finditer(r'\{"id":\s*"(\w+)",\s*"el":\s*"(\w+)"', PY)}
cli = {m.group(1): m.group(2) for m in re.finditer(r'id:"(\w+)",\s*el:"[^"]*",\s*ek:"(\w+)"[^}]*llm:1', HT)}
ok("짝", f"퀘스트 {len(srv)}개가 서버·화면에 모두", set(srv) == set(cli), set(srv) ^ set(cli))
ok("짝", "요소 배정이 일치", not [k for k in srv if srv[k] != cli.get(k)],
   [k for k in srv if srv[k] != cli.get(k)])
need_name = sorted(set(srv) - set(FORM))
miss = {q: HT.count(q + ':"') for q in need_name if HT.count(q + ':"') != 18}
ok("짝", f"문형 없는 {len(need_name)}개는 18개 언어에 이름이 있다", not miss, miss)
ok("짝", "문형이 모두 서버에 있다", set(FORM) <= set(srv), set(FORM) - set(srv))
for key, want in (("qWrap", 18), ("quitConfirm", 18), ("rpBriefGuide", 18),
                  ("prStepReply", 18), ("prReplyHint", 18)):
    n = HT.count(key + ':"')
    ok("짝", f"{key} {n}개 언어", n >= want, n)

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑩ 학습자에게 안 보여야 할 말 ════════")
BAN = ["대화이동", "역시작", "명료화", "레지스터", "담화", "화행", "연속체", "비계",
       "스캐폴딩", "화계", "의사소통 전략", "상호작용적 듣기", "기능 단계"]
shown = [v for _, v in re.findall(r'\b(q[A-Z]\w*):"((?:[^"\\]|\\.)*)"', HT) if re.search(r'[가-힣]', v)]
for tiers in FORM.values():
    shown += tiers
for w in BAN:
    hit = next((s for s in shown if w in s), "")
    ok("용어", f"'{w}' 안 나옴", not hit, hit[:40])

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑪ 이번에 고친 것들이 살아 있는가 ════════")
CHK = [
    ("자유 대화도 분석·넛지가 돈다", "if rp_plan is not None:\n                                # 단계" not in PY),
    ("맥락으로 넛지 자리를 좁힌다", "def _fit_intervention" in PY and "_fit_intervention()" in PY),
    ("총평을 점수와 무관하게 담는다", "let reviewBuf" in HT),
    ("총평 조각을 안 버린다", 'if (rpFinal) rpFinal.review = (rpFinal.review || "") +' not in HT),
    ("소켓 죽으면 즉시 접는다", HT.count("revGiveUp();") >= 2),
    ("마무리 영상 한 번만 재생", "v.loop = false;" in HT),
    ("총평 오면 영상 종료", "outroDone();" in HT),
    ("도와주기 페이더 대화 중 잠금", HT.count("scafSlider.disabled") == 2),
    ("나갈 때 확인(대화·결과)", "function hasUnfinished" in HT and "quitConfirm" in HT),
    ("연습은 ①→② 를 마치고 넘어간다", 'if (prPhase === "repeat" && e) {' in HT),
    ("연속체 전체 듣기", "function prSeqPlay" in HT),
    ("빈 cue 를 도로 안 채운다", 'if e.get("cue"):' in PY),
    ("감정 — 화남 포함", "★★ 감정" in PY and "화남" in PY),
    ("감정 — 실력엔 화 안 냄", "한국어 실력**을 두고는 절대 화내지" in PY),
    ("대화문에도 감정 지시", "배역의 감정을 담아라" in PY),
    ("대화문에 지위 지시", "윗사람과 아랫사람의 말은 바뀌지 않는다" in PY),
    ("교정 전에 '정말 틀렸나' 묻기", "이게 정말 틀렸나?" in PY),
    ("총평 진단 노출", '"review": {' in PY and "_review_dx" in PY),
    ("영상 파일 유무 노출", '"outro": {' in PY),
    ("/reviewtest 있음", "async def review_test" in PY),
    ("말투 계산이 한 곳", HT.count("function speechOf(d, p)") == 1
                            and "const avg = (+distSlider.value + +powerSlider.value) / 2" not in HT),
    ("말투는 두 축을 따로 본다", "SPEECH_CLOSE" in HT and "partnerSpeechOf" in HT),
    ("결과창 스크롤 표시", "function markScrollable" in HT),
]
for msg, cond in CHK:
    ok("잔존", msg, cond)


# ═══════════════════════════════════════════════════════════
print("\n════════ ⑬ 자유 대화 경로 (v107에서 켠 곳) ════════")
# rp_plan 이 None 인데 대괄호로 바로 꺼내는 코드가 있으면 분석이 통째로 죽고,
# 그 아래 넛지까지 건너뛴다 (실제로 그랬다).
_lines = PY.split("\n")
def _guarded(idx):
    ind = len(_lines[idx]) - len(_lines[idx].lstrip())
    for j in range(idx, max(-1, idx - 80), -1):
        l = _lines[j]
        if not l.strip(): continue
        k = len(l) - len(l.lstrip())
        if k < ind:
            ind = k
            if "if rp_plan" in l: return True
            if l.strip().startswith("else:"):
                for m in range(j - 1, max(-1, j - 40), -1):
                    lm = _lines[m]
                    if lm.strip() and (len(lm) - len(lm.lstrip())) == k:
                        return "rp_plan" in lm
    return False
_bad = []
for _i, _l in enumerate(_lines):
    _t = _l.strip()
    if _t.startswith(("#", "★", "·", "*", '"""')) or "`" in _t: continue   # 주석·설명문은 코드가 아니다
    if re.search(r'rp_plan\[[^\]]+\]', _l):
        if "if rp_plan else" in _l or re.search(r'rp_plan\[[^\]]+\][^\n]*if rp_plan', _l): continue
        if not _guarded(_i): _bad.append(_i + 1)
ok("자유대화", "rp_plan 을 무방비로 꺼내는 코드 없음", not _bad, _bad)
ok("자유대화", "진행률 payload 가 계획 없어도 안전", "rp_plan[\"stages\"] if rp_plan else []" in PY)
ok("자유대화", "넛지 고르기 함수들이 rp_plan 을 안 본다",
   all("rp_plan" not in grab(rf'^    (?:async )?def {f}\(.*?(?=^    (?:async )?def |\Z)')
       for f in ("_fit_intervention", "_intv_overdue", "pick_anytime_intervention",
                 "send_teach_intervention")))

print("\n════════ ⑭ 맥락 판정을 실제로 돌려 본다 ════════")
_src = re.search(r'    def _stage_phase\(\).*?(?=\n    def _intv_overdue)', PY, re.S).group(0)
_src = "\n".join(l[4:] if l.startswith("    ") else l for l in _src.split("\n"))
_QL = [{"id": m.group(1), "el": m.group(2)}
       for m in re.finditer(r'\{"id":\s*"(\w+)",\s*"el":\s*"(\w+)"', PY)]
exec(re.search(r"^PHASE_BAN = \{[\s\S]*?^\}", PY, re.M).group(0), globals())
exec(re.search(r"^INTV_EXCLUDE = \{[\s\S]*?^\}", PY, re.M).group(0), globals())
def _fit(last_ai, turns, done=(), stages=0, stages_done=0, percent=0):
    """stages=0 이면 자유 대화. stages>0 이면 주제 대화이고 stages_done 만큼 밟았다."""
    convo = []
    for t in turns[:-1]:
        convo += [{"role": "ai", "text": "네."}, {"role": "user", "text": t}]
    convo += [{"role": "ai", "text": last_ai}]
    if turns: convo.append({"role": "user", "text": turns[-1]})
    exec(__import__("re").search(r"INTV_ANYTIME\s*=\s*[\s\S]*?\n(?=[A-Z_]+\s*=|\n)", PY).group(0), globals())
    _ns = {"re": __import__("re"), "scaf_level": 2, "INTV_ANYTIME": INTV_ANYTIME, "convo": convo, "QUEST_LLM": _QL,
           "PHASE_BAN": PHASE_BAN, "INTV_EXCLUDE": INTV_EXCLUDE, "_user_turns": lambda: len(turns),
           "rp_plan": ({"stages": [{}] * stages} if stages else None),
           "idc_state": {"intv_ids": set(done), "levels": {}},
           "rp_progress": {"quests": set(), "total": stages,
                           "done": set(range(stages_done)), "percent": percent},
           "IDC_LEVEL_MODEL": 3, "IDC_LEVEL_SOLO": 1}
    exec(_src, _ns); return _ns["_fit_intervention"]()
for label, ai, turns, want in [
    ("물어봤는데 짧게만 답한다", "주말에 뭐 했어요?", ["네", "그냥요"], ("qKeepTurn", "qExpand")),
    # ★ 이 대사는 '길기만 한 말'이 아니라 **지난 일 이야기**다(-었어요 + 묻지 않음).
    #   그러면 「천천히 말해 주세요」가 아니라 「그래서요?」·공감이 맞다.
    #   v118까지 기대값이 길이만 보고 있었다 — 검사가 틀렸던 것이다.
    ("지난 일을 길게 이야기했다", "저는 어제 친구랑 영화를 봤는데요, 그 영화가 정말 재미있었어요. 특히 마지막 장면이 인상 깊었어요.", ["아 그래요"], ("qContinuer", "qEmpathy", "qEcho")),
    # 이야기가 아니라 **설명**이 길게 쏟아진 자리 — 여기가 「천천히」의 자리다
    ("설명이 한꺼번에 길게 왔다", "환불 규정은 구입일로부터 칠 일 이내이고 영수증과 포장이 그대로 있어야 하며 온라인 주문은 절차가 조금 다릅니다", ["아 네"], ("qAskSlow", "qParaphrase", "qAskAgain", "qCheckUnd", "qAskEasy")),
    ("물어봤고 길게 답했다", "주말에 뭐 했어요?", ["저는 친구를 만나서 같이 밥을 먹고 영화를 봤어요"], ("qEndTurn", "qExpand")),
    ("상대가 말을 맺었다", "저는 곶감을 제일 좋아해요.", ["아 네 저도요 저는 떡볶이도 좋아해요"], ("qExpand", "qNewTopic", "qEndTurn")),
    ("대화가 아직 없다", "", [], ("qInitiate",)),   # 먼저 말을 걸 자리다
]:
    g = _fit(ai, turns)
    ok("맥락", f"{label:22} → {g or '(없음)'}", g in want, g)

print("\n──── ⑤ 청하는 말과 묻는 말을 가르는가 (v119) ────")
# 「예약은 하셨을까요?」는 **지난 일을 묻는 말**이다. 청하는 말로 잘못 읽으면
# 인사만 나눈 자리에서 「그럼 ~는 어떻겠습니까?」(대안 제시)가 튀어나온다.
_neg = {"qAlt", "qCond", "qRefuse", "qCounter"}
for label, ai in [("예약은 하셨을까요?", "예약은 하셨을까요?"),
                  ("진료 보러 오셨어요?", "진료 보러 오셨어요?"),
                  ("점심 드셨어요?", "점심 드셨어요?")]:
    g = _fit(ai, ["네 왔어요"], stages=5, stages_done=2)
    ok("청하는 말", f"{label:18} → 협상 안 열림 ({g})", g not in _neg, g)
for label, ai in [("신분증 좀 주시겠어요?", "신분증 좀 주시겠어요?"),
                  ("2시로 예약해 드릴까요?", "2시로 예약해 드릴까요?")]:
    g = _fit(ai, ["음…"], stages=5, stages_done=2)
    ok("청하는 말", f"{label:18} → 협상 열림 ({g})", g in _neg, g)

print("\n──── ⑥ 대화의 자리를 아는가 (v119) ────")
# 마무리 단계에서 새 화제를 꺼내라고 하면 대화가 되돌아간다
_close = [_fit("네, 그럼 안녕히 가세요.", ["네 감사합니다"], stages=5, stages_done=4, percent=100),
          _fit("더 궁금한 점 있으세요?", ["아니요 없어요"], stages=5, stages_done=5, percent=120),
          _fit("정문으로 나가시면 돼요.", ["네 알겠습니다"], stages=4, stages_done=4, percent=100)]
ok("자리", f"마무리에서 화제를 새로 벌이지 않는다 {_close}",
   not (set(_close) & PHASE_BAN["close"]), _close)
# 시작 단계에서 협상·화제 접기는 아직 열리지 않았다
_open = [_fit("안녕하세요, 어떻게 오셨어요?", ["안녕하십니까"], stages=5, stages_done=0),
         _fit("네, 무엇을 도와드릴까요?", ["저기요"], stages=5, stages_done=0)]
ok("자리", f"시작에서 협상·화제 접기가 안 나온다 {_open}",
   not (set(_open) & PHASE_BAN["open"]), _open)
ok("자리", "전개에서는 막지 않는다", PHASE_BAN["mid"] == set())
ok("자리", "자유 대화는 단계가 없으니 막지 않는다",
   _fit("이거 좀 도와주세요.", ["음…"]) in {"qAlt", "qCond", "qRefuse", "qCounter"},
   _fit("이거 좀 도와주세요.", ["음…"]))

_g1 = _fit("주말에 뭐 했어요?", ["네", "그냥요"])
_g2 = _fit("주말에 뭐 했어요?", ["네", "그냥요"], done=(_g1,))
ok("맥락", "이미 띄운 것은 다시 안 고른다", _g2 and _g2 != _g1, f"{_g1} → {_g2}")


# ═══════════════════════════════════════════════════════════
print("\n════════ ⑯ 화계 — 서버와 화면이 같은 눈금인가 (v119) ════════")
# 학습자가 화면에서 「~습니다/습니까?로」를 읽는데 호아랑·대화문·도움말이
# 해요체로 나오면, 보는 말과 듣는 말이 어긋난다(v118까지 그랬다).
# 두 벌의 식이 **한 칸도** 달라서는 안 된다. 50칸을 전부 대조한다.
_sv = {"SPEECH_CLOSE": 60, "SPEECH_FAR": 35}
for _f in ("_speech_of", "_partner_speech_of"):
    exec(re.search(r"def " + _f + r"\(.*?\n(?=\n\n)", PY, re.S).group(0), _sv)
def _jsrun(fn, d, p):
    """화면 쪽 함수를 그대로 읽어 돌린다 — 두 줄짜리 조건식이라 옮길 수 있다."""
    body = re.search(r"function " + fn + r"\(d, p\) \{(.*?)\n    \}", HT, re.S).group(1)
    out = None
    for ln in body.split("\n"):
        ln = ln.split("//")[0].strip()
        m = re.match(r"if \(d (>=|<=) (SPEECH_CLOSE|SPEECH_FAR)\)\s*return (.+);", ln)
        if m:
            lim = 60 if m.group(2) == "SPEECH_CLOSE" else 35
            if (d >= lim if m.group(1) == ">=" else d <= lim):
                mm = re.match(r"p (>=|<=) (\d+) \? (\d) : (\d)", m.group(3))
                hit = (p >= int(mm.group(2))) if mm.group(1) == ">=" else (p <= int(mm.group(2)))
                return int(mm.group(3)) if hit else int(mm.group(4))
        m2 = re.match(r"return (\d);", ln)
        if m2: out = int(m2.group(1))
    return out
_TIER = ["formal", "polite", "banmal"]
_diff = []
for d in (0, 25, 50, 75, 100):
    for p in (0, 25, 50, 75, 100):
        for pyf, jsf in (("_speech_of", "speechOf"), ("_partner_speech_of", "partnerSpeechOf")):
            a, b = _sv[pyf](d, p), _TIER[_jsrun(jsf, d, p)]
            if a != b: _diff.append(f"D{d}P{p} {jsf}: 서버 {a} / 화면 {b}")
ok("화계", "서버와 화면이 50칸 모두 같다", not _diff, _diff[:4])
ok("화계", "합쇼체·해요체·해체 세 단계가 다 나온다",
   {_sv["_speech_of"](d, p) for d in range(0, 101, 5) for p in range(0, 101, 5)}
   == {"formal", "polite", "banmal"})
ok("화계", "도움말 프롬프트에 화계가 들어간다", "화계 — 반드시 지켜라" in PY)
ok("화계", "상황극 프롬프트에 화계가 들어간다", "rp_speech_line" in PY)
ok("화계", "자유 대화 프롬프트에 화계가 들어간다", "화계 — 아래 어떤 규칙보다 먼저다" in PY)
ok("화계", "화면 안내가 어미 형태다(~습니다/습니까?)", "~습니다/습니까?" in HT)
ok("화계", "「존댓말로 아주 공손하게」는 사라졌다", "존댓말로 아주 공손하게" not in HT)
ok("화계", "합쇼체를 따로 판정한다", '"formal"' in PY and "습니까" in PY)

print("\n════════ ⑱ 넛지는 이름만 · 형식은 도움말이 (v120) ════════")
# ★ 미리 만들어 둔 제시 문형은 지금 대화가 무슨 이야기인지 모른다.
#   다섯 중 셋이 어긋났다 — 「시간을 끌어 보세요」 자리에 의견 교환 문형이 나왔다.
#   이제 넛지는 **무엇을 할 자리인지**만 알리고, 형식은 도움말이 맥락을 보고 만든다.
ok("넛지", "말풍선이 제시 문형을 쓰지 않는다",
   "function questLabel(qid) { return t(qid); }" in HT)
ok("넛지", "제시 문형은 지우지 않았다(학습 화면·대응표가 쓴다)", "function questForm(qid)" in HT)
ok("넛지", "말풍선에 「지금이에요.」가 있다", "NZ_NOW" in HT and "지금이에요." in HT)
ok("넛지", "「지금이에요.」가 18개 언어에 다 있다",
   len(re.search(r"const NZ_NOW = \{(.*?)\};", HT, re.S).group(1).split(":")) - 1 == 18,
   len(re.search(r"const NZ_NOW = \{(.*?)\};", HT, re.S).group(1).split(":")) - 1)
ok("넛지", "「도와줘」 단추가 같이 움직인다", "scfNudge(true)" in HT and "nudge-live" in HT)
ok("넛지", "도움말이 오면 가라앉는다", "scfNudge(false)" in HT)
ok("넛지", "서버가 방금 알린 것을 기억한다", 'idc_state["hint_focus"] = {"qid": qid' in PY)
ok("넛지", "도움말 **두 제안 모두** 그것을 이어받는다",
   "두 제안 모두 이것을 담아라" in PY and "focus_line" in PY)
ok("넛지", "세 차례가 지나면 흘려보낸다", '_user_turns() - _fc.get("turn", 0) <= 3' in PY)
ok("넛지", "한 번 쓰면 비운다", 'idc_state["hint_focus"] = None' in PY)
ok("넛지", "맥락에서 안 되면 지시를 접으라고 못 박는다", "이 지시를 접어라" in PY)

# ★ v121 — 도와주기 페이더가 **도움말에도** 걸린다.
#   0 끔이면 요소를 얹지 않고, 2 이상이면 넛지가 없어도 골라 얹는다.
ok("페이더", "0(끔)에서는 도움말에 요소를 얹지 않는다", "if scaf_level >= 1:" in PY)
ok("페이더", "2 이상이면 넛지 없이도 요소를 고른다",
   "elif scaf_level >= 2:" in PY and "_qid = _fit_intervention()" in PY)
ok("페이더", "요소를 실었으면 로그로 남긴다", "[도움말] 요소 싣기" in PY)

print("\n──── 도움말이 잘리지 않는가 (v121) ────")
_ht = {}
exec(re.search(r"def _hint_trim\(.*?\n(?=\n\n)", PY, re.S).group(0), _ht)
_trim = _ht["_hint_trim"]
_long = "오오, 그거 유명한 게임이잖아! 나중에 나도 좀 가르쳐줘! 나는 '용맹한 친구들'이라는 만화책 보는데, 진짜 재밌어! 막 어려운 상황 속에서도 서로 도와주고 그러거든!"
_got = _trim(_long)
ok("도움말", f"긴 제안을 문장 끝에서 자른다 ({len(_got)}자)",
   len(_got) <= 112 and _got.rstrip()[-1] in "?!.…", _got[-24:])
ok("도움말", "짧은 것은 건드리지 않는다", _trim("오, 그거 유명하잖아! 나도 좀 가르쳐줘.") == "오, 그거 유명하잖아! 나도 좀 가르쳐줘.")
ok("도움말", "끝을 못 찾으면 말줄임표를 붙인다", _trim("가" * 200).endswith("…"))
ok("도움말", "길이를 못 박는다", "발화 세 개를 넘기지 마라" in PY)

print("\n──── 개입에서 뺀 항목 (v121) ────")
exec(re.search(r"^INTV_EXCLUDE = \{[\s\S]*?^\}", PY, re.M).group(0), globals())
for _q, _why in (("qTakeTurn", "끼어들기 — 상대가 말하는 도중에 눌러야 성립"),
                 ("qCircum", "돌려 말하기 — 무엇을 모르는지 서버가 알 수 없다"),
                 ("qSelfFix", "자기 수정 — 시켜서 하는 일이 아니다"),
                 ("qAskFast", "빨리 — 말이 느린지는 글로 못 잰다")):
    ok("제외", f"{_q} 는 권하지 않는다 ({_why})", _q in INTV_EXCLUDE)
ok("제외", "고르기에서도 걸러 낸다", "if qid in INTV_EXCLUDE:" in PY)
ok("제외", "퀘스트 자체는 살아 있다(점수에는 들어간다)",
   all(f'"{q}"' in PY for q in ("qTakeTurn", "qCircum")) and "INTERVENABLE = {q[\"id\"] for q in QUEST_LLM} - INTV_EXCLUDE" in PY)
_ex = [_fit(a, m, stages=5, stages_done=2) for a, m in
       (("네?", ["음 그거"]), ("뭐라고요?", ["그"]), ("응 그래.", ["어"]), ("그렇구나.", ["응"]))]
ok("제외", f"뺀 항목이 실제로 안 나온다 {_ex}", not (set(_ex) & INTV_EXCLUDE), _ex)

print("\n──── 말풍선이 태그를 뱉지 않는가 (v121) ────")
# ★ hamPeekHtml 은 이름과 달리 textContent 를 쓴다. 태그를 넘기면 글자 그대로 뜬다.
#   (다른 곳의 '<span class= 는 innerHTML 로 쓰이므로 정상이다)
_shown = re.sub(r"/\*[\s\S]*?\*/", "", HT)          # 주석은 화면에 안 나온다
ok("말풍선", "넛지가 태그를 문자열로 넘기지 않는다", "nz-now" not in _shown)
ok("말풍선", "꾸밈은 네 번째 인자로 준다",
   'hamPeekHtml(title, items, ms, cls)' in HT and 'hamPeekHtml(NZ_NOW[uiLang] || NZ_NOW.en, label, 5600, "nz")' in HT)
ok("말풍선", "두 줄 모양이 CSS 에 있다", ".ham-peek.nz .hp-bubble .qz-items" in HT)

print("\n════════ ⑳ 넛지와 도움말이 한 순간에 (v122) ════════")
# ★ 저자의 정리 — 「요소가 실현될 수 있는 차례가 오면, 그것이 실현된 표현 두 개가
#   생성됨과 동시에 넛지가 나온다. 페이더가 높으면 그 순간이 자주 온다.」
#   v121까지는 학습자가 눌러야 그때부터 만들었다. 그래서 기다려야 했고,
#   9초 안에 못 만들면 「추천 표현이 없어요」가 떴다.
ok("동시", "넛지를 띄우면서 도움말도 만든다", "asyncio.create_task(send_hints(prefetch=True))" in PY)
ok("동시", "만든 것을 재워 둔다", 'hint_cache = {"items"' in PY and "hint_cache.update(" in PY)
ok("동시", "누르면 재워 둔 것을 바로 보낸다", "재워 둔 것 바로 보냄" in PY)
ok("동시", "재워 둔 것은 같은 차례 안에서만 쓴다",
   '_user_turns() - _c["turn"] <= 1' in PY and 'time.time() - _c["at"] < 180' in PY)
ok("동시", "차례가 지났으면 새로 만든다", '_user_turns() - _c["turn"] <= 1' in PY)

ok("도움말", "요소별 구체 보기를 준다", "FOCUS_EG = {" in PY)
_eg = {}
exec(re.search(r"^FOCUS_EG = \{[\s\S]*?^\}", PY, re.M).group(0), _eg)
_need = {"qAskEasy", "qEmpathy", "qNative", "qAskSlow", "qAskAgain", "qContinuer"}
ok("도움말", "저자가 짚은 것들에 보기가 있다", _need <= set(_eg["FOCUS_EG"]),
   sorted(_need - set(_eg["FOCUS_EG"])))
ok("도움말", "모국어 항목은 학습자 언어 이름을 끼운다", "{n}" in _eg["FOCUS_EG"]["qNative"])
ok("도움말", "권할 수 있는 것에 거의 다 보기가 있다",
   len(set(_eg["FOCUS_EG"]) - INTV_EXCLUDE) >= 20, len(_eg["FOCUS_EG"]))
ok("도움말", "한 제안은 발화 셋을 넘기지 않는다", "발화 세 개를 넘기지 마라" in PY)
ok("도움말", "요소는 그 세 발화 안에 있어야 한다", "그것이 이 세 발화 안에" in PY)
ok("도움말", "요소 지시가 맨 앞에 온다", 'prompt = f"""{focus_line}{head}' in PY)
ok("도움말", "빈손이면 화면이 미리 쓴 문형으로 메운다",
   "scfLastQid" in HT and "questForm(scfLastQid)" in HT)
ok("도움말", "서버가 qid 를 함께 보낸다", '"qid": (_q or {}).get("id", "")' in PY)

print("\n════════ ㉒ 점수·태도·목소리 (v125) ════════")
# ★ 다섯 단계 중 셋만 밟고도 100점이 나왔다. 마지막 단계에 닿았다는 것만으로
#   과업 달성으로 쳤기 때문이다. 기능단계는 **거쳐야 하는 자리**이므로 건너뛴 것은 못 한 것이다.
ok("점수", "모든 단계를 밟아야 과업 달성이다",
   'len(rp_progress["done"]) == rp_progress["total"]' in PY
   and "or last_idx in rp_progress[\"done\"]" not in PY)
ok("점수", "그 전에는 밟은 만큼만 준다", "pct = round(100 * len(rp_progress[\"done\"]) / rp_progress[\"total\"])" in PY)
ok("결과", "상호작용 대화 능력 글씨를 키웠다",
   ".idc-name { font-size: 15.5px" in HT and ".idc-why { font-size: 13px" in HT)

ok("태도", "배역이 학습자의 목적을 막지 않는다", "달성 목적은 학습자의 것" in PY and "끝내 거절해서 목적을 무산시키지 마라" in PY)
ok("태도", "배역 밖에서 훈계하지 않는다", "훈계하지 마라" in PY)
ok("태도", "데이트·부탁·항의 같은 일상은 막지 않는다",
   "데이트·약속 신청, 연락처 묻기, 고백" in PY and "「그건 좀…」이라고 하면 연습이 안 된다" in PY)
ok("태도", "배역을 어린아이로 넘겨짚지 않는다",
   "배역은 학습자가 달리 정하지 않았으면 **성인**이다" in PY and "어린아이로 짐작하지 마라" in PY)
ok("태도", "막는 것은 실제로 사람이 다치는 일뿐", "실제로 사람이 다치는 일" in PY)
ok("페이지", "/voicepick 이 Render 넣는 법까지 알려 준다",
   "Add Environment Variable" in PY and "copyName" in PY)

print("\n──── 목소리 ────")
ok("목소리", "학습자가 적은 배역을 그대로 보관한다", '"ai_role_raw"' in PY and 'plan["ai_role_raw"] = ai_role' in PY)
ok("목소리", "목소리를 고를 때 그 원문도 본다", "def pick_voice(ai_role: str = \"\", override: str = \"\", raw_role: str = \"\")" in PY)
ok("목소리", "계획이 성별을 지우지 않게 못 박는다", "성별과 나이를 지우지 마라" in PY)
ok("목소리", "「여알바」류를 알아본다", '"여알바"' in PY and '"남알바"' in PY)
_pv = {"re": re, "hashlib": __import__("hashlib")}
for _n in ("_ROLE_FEMALE", "_ROLE_MALE", "_ROLE_ELDER", "_ROLE_ADULT", "_ROLE_YOUNG",
           "VOICE_TABLE", "HOARANG_VOICE_KEY"):
    _m = re.search(r"^" + _n + r" = .*?\n(?=[A-Z_#\n])", PY, re.S | re.M)
    if _m: exec(_m.group(0), _pv)
exec(re.search(r"def pick_voice\(.*?\n(?=\n\n)", PY, re.S).group(0), _pv)
_f = _pv["pick_voice"]
ok("목소리", "「여알바」→ 여성 (모델이 「아르바이트생」으로 다듬어도)",
   _f("아르바이트생", "", "여알바") == _pv["VOICE_TABLE"]["woman"], _f("아르바이트생", "", "여알바"))
ok("목소리", "「할아버지 손님」→ 어르신 남성",
   _f("할아버지 손님", "", "할아버지 손님") == _pv["VOICE_TABLE"]["elder_m"])
ok("목소리", "학습자가 고른 것이 배역을 이긴다",
   _f("여자 아르바이트생", "boy", "여알바") == _pv["VOICE_TABLE"]["boy"])

ok("고르기", "성별을 먼저, 나이를 그다음", "VOICE_SEX" in HT and "VOICE_AGE" in HT and "VOICE_MAP" in HT)
ok("고르기", "자동·남성·여성 셋", HT.count('key: "auto", emoji') == 1 and '{ key: "m",' in HT and '{ key: "f",' in HT)
ok("고르기", "아이·성인·어르신 셋", all(f'key: "{k}"' in HT for k in ("young", "adult", "elder")))
ok("고르기", "여섯 짝이 서버 열쇠와 맞는다",
   all(v in PY for v in ("boy", "girl", "man", "woman", "elder_m", "elder_f")))
ok("고르기", "자동이면 나이를 묻지 않는다", 'if (sex === "auto") return;' in HT)
ok("페이지", "/voicepick 으로 귀로 듣고 고른다", '@app.get("/voicepick")' in PY and "TTS_VOICE" in PY)

print("\n════════ ㉓ 상호작용 대화 능력 학습 화면 (v128) ════════")
# ★ 하향식(Top-down) — 학습자는 이미 대화를 할 줄 안다. 없는 것은 한국어로 하는 방법이다.
#   그래서 **설명이 맨 뒤**에 온다. 순서가 뒤집히면 이 화면은 뜻이 없다.
ok("학습", "서버 학습표는 여덟 (비언어만 제외)",
   len(re.findall(r'"key": "\w+"', re.search(r"^IDC_LESSON = \[[\s\S]*?^\]", PY, re.M).group(0))) == 8)
# ★ v131 — 화면에는 **아홉을 모두** 보인다. 못 배우는 둘을 감추면 「없는 것」이 되어
#   학습자가 상호작용 대화 능력의 전체 모습을 알 수 없다(〈표 34〉 매체 배분이 화면에 드러난다).
ok("학습", "화면에는 아홉을 모두 보인다",
   'key: "stage"' in HT and 'key: "nonverbal"' in HT
   and HT.count('where: "here"') == 8 and HT.count('where: "class"') == 1)
ok("학습", "교실에서 배우는 것(몸짓)은 눌리지 않는다", "else b.disabled = true;" in HT)
ok("학습", "★ 이모지를 쓰지 않는다 (그림으로)",
   'emoji: "' not in HT.split("const IDC_LES = [")[1].split("];")[0]
   and '"#ic-idc-" + e.key' in HT)
ok("학습", "홈 카드가 주제·자유 대화와 같은 꼴", ".home-card.hc-idc" in HT
   and "linear-gradient(135deg, #22356B" in HT and "ic-ladder" in HT)
ok("학습", "홈 카드 문구 표가 쓰는 곳보다 앞에 있다",
   HT.index("const HOME_IDC = {") < HT.index('hcIdcTitleEl").textContent'))
ok("학습", "홈 카드 이름은 「한국어 대화 상호작용 능력」", "한국어 대화 상호작용 능력" in HT)
ok("학습", "쉬운 이름과 학술어가 따로 있다", '"easy":' in PY and '"acad":' in PY)
ok("학습", "⓪ 들어가기가 있다 (배경지식 활성화)", "place" in PY and "idl-warm" in HT)
ok("학습", "뜻풀이는 재워 둔다 — 정의는 고정, 사례는 변화", "_idc_desc_cache" in PY)
ok("학습", "뜻풀이에 학술어를 못 쓰게 막는다", "화계, 상호작용" in PY)
ok("학습", "표시할 줄은 학습자 발화여야 한다",
   'if mark < 0 or script[mark]["speaker"] != "user"' in PY)
# ★ v129 — 두 갈래에서 **세 갈래**로. 둘이면 아무렇게나 눌러도 절반이 맞아,
# 「첫 시도에 맞혔는가」가 알아차림의 지표가 되지 못한다(기저율 50% → 33%).
ok("학습", "선택지가 셋이다", '"wrong1"' in PY and '"wrong2"' in PY)
ok("학습", "정답 자리를 섞는다", "cand[i], cand[j] = cand[j], cand[i]" in PY)
ok("학습", "④ 형태 — 문형이 화계를 따른다", "QUEST_BY_EL" in HT and "f[tier] || f[1]" in HT)
ok("학습", "⑤ 사용 — 방금 들은 대화에서 이어진다",
   '@app.post("/idc-drill")' in PY and "새 상황을 만들지 마라" in PY)
ok("학습", "발화 연습과 같은 길(/stt)·같은 잣대(simScore)",
   'fd.append("hint", dr.text)' in HT and "simScore(said, dr.text)" in HT)
# ★ v130 — 대화문 재생을 주제 대화 「들어보기」와 같은 방식으로 바꿨다.
#   한 목소리로 이어 붙이고 간격을 220ms 로 고정했더니 누가 말하는지도 모르고 겹쳤다.
ok("학습", "대화문 재생이 들어보기와 같다 (역할 목소리·글자 수 기다림·미리 받기)",
   'lines[i].speaker === "user" ? scMyVoice()' in HT
   and "900 + lines[i].text.length * 165" in HT and "ttsPrefetch" in HT)
ok("학습", "이전 단추를 감추지 않는다", "prev.style.visibility" not in HT
   and "prev.disabled = (idl.step === 0)" in HT)
ok("학습", "★ 대화문을 학습자의 지난 대화에서 끌어온다",
   "function idcMineLines" in HT and "mine: idcMineLines(60)" in HT
   and "실제로 나눈 대화** — 여기서 끌어와라" in PY)
ok("학습", "학습자가 쓴 말을 그대로 살린다", "말은 되도록 그대로 살려라" in PY)
ok("학습", "★ 주제 대화 기록만 쓴다", 'loadHistory().filter(h => h && h.mode === "rp")' in HT)
ok("학습", "기록이 있으면 반드시 거기서 (없을 때만 새로)",
   "반드시 거기에서 골라라" in PY and "기록이 **아예 없을 때뿐**" in PY)
ok("학습", "기록을 줬는데 새로 지으면 /version 에 보인다",
   '_idc_dx["mine_miss"] += 1' in PY and '"miss": _idc_dx["mine_miss"]' in PY)
ok("학습", "어디서 왔는지 알려 준다", 'd.from === "mine"' in HT and "fromMine" in HT)
ok("학습", "학습 대화문이 챗봇의 구어체 규칙을 물려받는다", "{SPOKEN_RULES}" in PY)
ok("학습", "오답은 그럴듯한 오해여야 한다", "모르는 사람이 실제로 하는 오해" in PY)
ok("학습", "★ 불은 추측이 끝난 뒤에 켠다", "idlScript(true)" in HT and "idlScript(false)" in HT)
ok("학습", "맞혀야 넘어간다", "next.disabled = (idl.picked !== q.ans)" in HT)

print("\n──── 학습 기록 (논문 자료) ────")
ok("기록", "서버에 남긴다", '@app.post("/idc-learn")' in PY)
ok("기록", "기기 딱지는 익명이다", 'localStorage.getItem("devId")' in HT and "이름·연락처는 받지 않는다" in PY)
ok("기록", "첫 시도 정답 여부를 센다", '"tries"' in PY and "첫판정답률" in PY)
ok("기록", "★ 드라이브로 백업한다 (Render 디스크는 판마다 지워진다)",
   "_idc_flush" in PY and "_gdrive_upload_sync" in PY)
ok("기록", "올리기 실패하면 도로 넣어 둔다", "_idc_log[:0] = part" in PY)
ok("기록", "연구자용 표와 CSV", '@app.get("/idc-stats")' in PY and "idc_learn.csv" in PY)
ok("기록", "/version 에서 상태가 보인다", '"idc": {' in PY)

print("\n════════ ㉑ 없는 이름이 있는가 (v124) ════════")
# ★★ v122에서 send_hints 안에 `native` 를 썼는데 그 스코프에는 그런 이름이 없었다.
#   그 자리는 예외를 삼키는 try 안이라, **두 판 내내 도움말이 한 번도 안 만들어졌는데도**
#   아무도 몰랐다. ast.parse 도 node --check 도 이걸 못 잡는다.
#   symtable 은 스코프를 실제로 계산한다 — 함수 안에서 쓰였는데 지역도, 감싸는 함수의
#   지역도, 모듈 전역도, 내장도 아니면 **실행하는 순간 NameError** 다.
import symtable, builtins
_top = symtable.symtable(PY, "main.py", "exec")
_mod = set(_top.get_identifiers())
_bad = []
def _walk(tab, path):
    if tab.get_type() == "function":
        for sym in tab.get_symbols():
            n = sym.get_name()
            if (sym.is_assigned() or sym.is_parameter() or sym.is_imported()
                    or not sym.is_referenced() or sym.is_free() or sym.is_local()):
                continue
            if n in _mod or hasattr(builtins, n):
                continue
            _bad.append(f"{' → '.join(path)}({tab.get_lineno()}줄) → {n}")
    for ch in tab.get_children():
        _walk(ch, path + [ch.get_name()])
_walk(_top, ["(모듈)"])
ok("이름", "실행하면 NameError 가 날 이름이 없다", not _bad, _bad[:5])
ok("이름", "도움말 실패를 조용히 삼키지 않는다", "_hint_dx[\"fail\"] += 1" in PY)
ok("이름", "/version 에서 도움말 상태가 보인다", '"hint": {' in PY and '"empty": _hint_dx["empty"]' in PY)
ok("이름", "핸들러에 native 가 있다", 'native = LANG_NAMES.get(ui_lang, "")\n    # ★★ v124' in PY
   or 'ui_lang = websocket.query_params.get("lang", "").strip().lower()[:5]\n' in PY and PY.count('native = LANG_NAMES.get(ui_lang, "")') >= 2)

print("\n──── 도움말은 눌렀을 때 이미 있어야 한다 (v123) ────")
# ★ 눌렀을 때부터 만들기 시작하면 언제나 늦다. 넛지는 벌써 사라졌는데
#   표현이 그제야 뜨면 아무 뜻이 없다 — 저자가 짚은 그대로다.
ok("미리", "학습자의 차례가 올 때마다 미리 만든다",
   'if not hint_state["running"]:\n                                asyncio.create_task(send_hints(prefetch=True))' in PY)
ok("미리", "만든 것을 곧바로 밀어 보낸다", '"ready": bool(prefetch)' in PY)
ok("미리", "미리 만드는 길은 넉넉히 기다린다", "timeout_s=(22.0 if prefetch else 9.0)" in PY)
ok("미리", "겹쳐 돌지 않는다", PY.count('if not hint_state["running"]') >= 2)
ok("미리", "화면이 미리 온 것을 들고 있는다", "scfReady = { items:" in HT)
ok("미리", "누르면 왕복 없이 곧바로 편다",
   "if (scfReady && (scfReady.items || []).length)" in HT and "return requestScaffoldSlow();" in HT)
ok("미리", "내 차례가 시작되면 지난 것을 버린다", "scfReady = null;     // 내 차례가 시작됐다" in HT)
ok("미리", "펴 둔 채였으면 새것으로 갈아 끼운다", "펴 둔 채였으면 바로 갈아 끼운다" in HT)
ok("미리", "빈 qid 가 밑천을 덮지 않는다", 'if (msg.qid) scfLastQid = msg.qid;' in HT)
ok("미리", "넛지의 qid 도 밑천이 된다", "빈손일 때 이 문형으로 메운다" in HT)

print("\n──── 홈 배경음·페이더 초기값 (v122) ────")
_bgm = re.search(r"const HOME_BGM = \[(.*?)\];", HT, re.S).group(1)
ok("소리", "빗소리 곡을 뺐다", "bgm_rain" not in _bgm)
ok("소리", "그래도 여러 곡이 남아 있다", len(re.findall(r"/static/bgm_\w+\.mp3", _bgm)) >= 3,
   len(re.findall(r"/static/bgm_\w+\.mp3", _bgm)))
ok("스타일", "자유 대화 도와주기 초기값 「많이」",
   'id="scafSlider" min="0" max="3" value="3"' in HT)
ok("넛지", "호아랑이 드나드는 시간을 늘렸다", "transition: transform 1s cubic-bezier" in HT)

print("\n════════ ⑲ 화계 눈금 · 계획 만들기 (v120) ════════")
ok("화계", "합쇼체는 「낯선 사이」 칸에서만 (눈금 15)",
   "SPEECH_FAR = 15" in PY and "const SPEECH_FAR = 15;" in HT)
_sf = {"SPEECH_CLOSE": 60, "SPEECH_FAR": 15}
exec(re.search(r"def _speech_of\(.*?\n(?=\n\n)", PY, re.S).group(0), _sf)
ok("화계", "「아는 사이」(25)는 해요체다", _sf["_speech_of"](25, 50) == "polite", _sf["_speech_of"](25, 50))
ok("화계", "「낯선 사이」(10)는 합쇼체다", _sf["_speech_of"](10, 50) == "formal", _sf["_speech_of"](10, 50))
ok("계획", "말투 손질과 앞말 채우기를 나란히 돌린다",
   "await asyncio.gather(*jobs, return_exceptions=True)" in PY)
ok("계획", "만드는 동안 진행률이 보인다",
   "mkProgStart()" in HT and 'id="rpMakeFill"' in HT)
ok("계획", "거짓으로 100%를 채우지 않는다", "Math.min(95," in HT)
ok("계획", "진행 문구가 18개 언어에 다 있다",
   len(re.search(r"const MK_MSG = \{(.*?)\n    \};", HT, re.S).group(1).split("],")) - 1 == 18)
ok("스타일", "자유 대화 친밀도 초기값 75",
   'id="distSlider" min="0" max="100" value="75"' in HT)

print("\n════════ ⑰ 발화 연습 — 앞말 없는 대답 (v119) ════════")
_cm = {}
exec(re.search(r"_ANSWER_HEAD = .*?(?=\n\nasync def _fix_style)", PY, re.S).group(0), _cm)
_plan = {"stages": [{"expressions": [
    {"text": "네, 여기 신분증이요.", "cue": ""},
    {"text": "저기요, 이거 얼마예요?", "cue": ""},
    {"text": "알겠습니다.", "cue": ""},
    {"text": "네, 좋아요.", "cue": "이걸로 하시겠어요?"},
]}]}
_holes = [t for _, _, t in _cm["_cue_missing"](_plan)]
ok("연습", "「네, 여기 신분증이요.」는 대답이다 — 앞말을 채운다", "네, 여기 신분증이요." in _holes)
ok("연습", "「알겠습니다.」도 대답이다", "알겠습니다." in _holes)
ok("연습", "「저기요, 이거 얼마예요?」는 먼저 여는 말 — 건드리지 않는다",
   "저기요, 이거 얼마예요?" not in _holes)
ok("연습", "앞말이 이미 있으면 건드리지 않는다", len(_holes) == 2, _holes)
ok("연습", "계획을 만든 뒤 앞말을 채운다", "_fill_cues(plan, want_ai)" in PY)
ok("연습", "계획 프롬프트가 「대답에 cue를 비우지 마라」고 못 박는다", "그 말로 대화를 열 수는 없다" in PY)

print("\n════════ ⑮ 넛지가 0이 되는 길이 남았는가 (v107 최대 사고) ════════")
_fade = re.search(r'IDC_FADE_AT = \{IDC_LEVEL_MODEL: (\d+), IDC_LEVEL_PROMPT: (\d+)\}', PY)
_m, _p = int(_fade.group(1)), int(_fade.group(2))
ok("페이딩", f"자율 임계가 넉넉한가 ({_p}회)", _p >= 8, _p)
ok("페이딩", "「많이」에서는 자율 요소도 넛지가 나간다",
   "and scaf_level < 3" in PY and PY.count("and scaf_level < 3") >= 2)
ok("페이딩", "후보 고르기도 같은 규칙", "or scaf_level >= 3" in PY)
ok("페이딩", "기기 누적을 한 번 비운다", 'idcCountsVer") !== "3"' in HT)
ok("페이딩", "접속 때 자율 개수를 로그로 남긴다", "자율 도달" in PY)

# 여덟 요소가 모두 자율일 때 넛지가 나가는가 — 실제로 돌려 본다
_src = re.search(r'    def _stage_phase\(\).*?(?=\n    def _intv_overdue)', PY, re.S).group(0)
_src = "\n".join(l[4:] if l.startswith("    ") else l for l in _src.split("\n"))
_QL = [{"id": m.group(1), "el": m.group(2)}
       for m in re.finditer(r'\{"id":\s*"(\w+)",\s*"el":\s*"(\w+)"', PY)]
_ALLSOLO = {e: 1 for e in {q["el"] for q in _QL}}      # 1 = 자율
def _fit_solo(scaf):
    convo = [{"role": "ai", "text": "주말에 뭐 했어요?"}, {"role": "user", "text": "네"}]
    _ns = {"re": __import__("re"), "INTV_ANYTIME": INTV_ANYTIME, "convo": convo, "QUEST_LLM": _QL,
           "idc_state": {"intv_ids": set(), "levels": dict(_ALLSOLO)},
           "rp_progress": {"quests": set(), "total": 0, "done": set(), "percent": 0},
           "PHASE_BAN": PHASE_BAN, "INTV_EXCLUDE": INTV_EXCLUDE, "_user_turns": lambda: 1, "rp_plan": None,
           "IDC_LEVEL_MODEL": 3, "IDC_LEVEL_SOLO": 1, "scaf_level": scaf}
    exec(_src, _ns); return _ns["_fit_intervention"]()
ok("페이딩", "여덟 요소가 다 자율이어도 「많이」면 넛지가 나온다", bool(_fit_solo(3)), _fit_solo(3))
ok("페이딩", "「보통」에서는 자율 요소를 아낀다", not _fit_solo(2), _fit_solo(2))

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑫ 버전·배포 폴더 ════════")
v1 = re.search(r'APP_VERSION = "(v\d+)', PY).group(1)
v2 = re.search(r'APP_VERSION = "(v\d+)', HT).group(1)
sw = io.open(f"{ROOT}/static/sw.js", encoding="utf-8").read()
v3 = re.search(r"hoarang-(v\d+)", sw).group(1)
ok("배포", f"세 곳 버전 일치 ({v1})", v1 == v2 == v3, f"{v1}/{v2}/{v3}")
import hashlib as _h
def md5(p):
    try: return _h.md5(io.open(p, "rb").read()).hexdigest()[:10]
    except Exception: return None
FILES = ["main.py", "app.html", "templates/index.html", "templates/app.html",
         "static/sw.js", "static/outro.mp4", "static/outro.jpg",
         "requirements.txt", "render.yaml", "개발일지_CHANGELOG.md"]
for f in FILES:
    a, b = md5(f"{ROOT}/{f}"), md5(f"{ROOT}/깃헙에 올릴 파일/{f}")
    ok("배포", f"{f} 동기화", a is not None and a == b, f"{a} / {b}")
_pub = f"{ROOT}/깃헙에 올릴 파일"
# 배포 폴더가 없어도 검사가 죽지 않게 — 여기서 죽으면 뒤가 통째로 미검증이 된다
gz = os.path.getsize(f"{_pub}/app.html.gz") if os.path.isfile(f"{_pub}/app.html.gz") else 0
raw = os.path.getsize(f"{ROOT}/app.html")
ok("배포", f"app.html.gz 최신 ({gz//1024}KB / 원본 {raw//1024}KB)", gz > 100_000)

# ═══════════════════════════════════════════════════════════
print("\n" + "═" * 60)
if fail:
    print(f"💥 확인 필요 {len(fail)}건")
    for f in fail:
        print("   ·", f)
else:
    print("🎉 통합 점검 이상 없음")
print("═" * 60)
sys.exit(1 if fail else 0)

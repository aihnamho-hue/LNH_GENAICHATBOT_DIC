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
def _fit(last_ai, turns, done=(), stages=0, stages_done=0, percent=0):
    """stages=0 이면 자유 대화. stages>0 이면 주제 대화이고 stages_done 만큼 밟았다."""
    convo = []
    for t in turns[:-1]:
        convo += [{"role": "ai", "text": "네."}, {"role": "user", "text": t}]
    convo += [{"role": "ai", "text": last_ai}]
    if turns: convo.append({"role": "user", "text": turns[-1]})
    exec(__import__("re").search(r"INTV_ANYTIME\s*=\s*[\s\S]*?\n(?=[A-Z_]+\s*=|\n)", PY).group(0), globals())
    _ns = {"re": __import__("re"), "scaf_level": 2, "INTV_ANYTIME": INTV_ANYTIME, "convo": convo, "QUEST_LLM": _QL,
           "PHASE_BAN": PHASE_BAN, "_user_turns": lambda: len(turns),
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
ok("넛지", "도움말 첫 제안이 그것을 이어받는다",
   "첫 번째 제안은 이것이어야 한다" in PY and "focus_line" in PY)
ok("넛지", "두 차례가 지나면 흘려보낸다", '_user_turns() - _fc.get("turn", 0) <= 2' in PY)
ok("넛지", "한 번 쓰면 비운다", 'idc_state["hint_focus"] = None' in PY)

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
           "PHASE_BAN": PHASE_BAN, "_user_turns": lambda: 1, "rp_plan": None,
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

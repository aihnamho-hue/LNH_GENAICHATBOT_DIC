# -*- coding: utf-8 -*-
"""v107 통합 점검 — 코드 모양이 아니라 **실제로 돌려 보고** 확인한다.

정규식으로 '이렇게 생겼나'를 재는 검사는 조사·말투·판정 같은 것을 못 잡는다.
서버를 띄우지 않고 함수만 떼어 실행해, 학습자가 겪을 결과를 직접 만들어 본다."""
import re, io, sys, hashlib, base64, struct, asyncio, os, time

ROOT = "/sessions/great-dazzling-ramanujan/mnt/음성 대화형 챗봇"
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
# v114 — 서버가 고를 수 있는 넛지가 6개에서 27개로 늘면서, 그중 여섯에
# 문형이 없었다. 이름만 보여 주면 넛지가 아니라 수수께끼다. 그래서 20개.
ok("넛지", "문형 20개", len(FORM) == 20, len(FORM))
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
ok("짝", "문형 20개는 모두 서버에 있다", set(FORM) <= set(srv), set(FORM) - set(srv))
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
    ("말투 계산이 한 곳", HT.count("if (avg <= 15)") == 1),
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
_src = re.search(r'    def _fit_intervention\(\).*?(?=\n    def _intv_overdue)', PY, re.S).group(0)
_src = "\n".join(l[4:] if l.startswith("    ") else l for l in _src.split("\n"))
_QL = [{"id": m.group(1), "el": m.group(2)}
       for m in re.finditer(r'\{"id":\s*"(\w+)",\s*"el":\s*"(\w+)"', PY)]
def _fit(last_ai, turns, done=()):
    convo = []
    for t in turns[:-1]:
        convo += [{"role": "ai", "text": "네."}, {"role": "user", "text": t}]
    convo += [{"role": "ai", "text": last_ai}]
    if turns: convo.append({"role": "user", "text": turns[-1]})
    # v114 — _fit_intervention 이 re 와 INTV_ANYTIME 을 쓰게 됐다. 살림을 같이 넣어 준다.
    _ns = {"convo": convo, "QUEST_LLM": _QL, "re": re,
           "INTV_ANYTIME": _ANY,
           "idc_state": {"intv_ids": set(done), "levels": {}, "counts": {}},
           "rp_progress": {"quests": set()}, "IDC_LEVEL_MODEL": 3, "IDC_LEVEL_SOLO": 1}
    exec(_src, _ns); return _ns["_fit_intervention"]()
_ANY = eval(re.search(r"INTV_ANYTIME = (\[[^\]]*\])", PY).group(1)) if re.search(r"INTV_ANYTIME = (\[[^\]]*\])", PY) else []
for label, ai, turns, want in [
    ("물어봤는데 짧게만 답한다", "주말에 뭐 했어요?", ["네", "그냥요"], ("qKeepTurn", "qExpand")),
    # v114 — 이 문장은 **지난 일 이야기**다(과거형·질문 아님). 예전에는 '길다'만 보고
    # 요약 확인(qParaphrase)을 시켰는데, 이야기를 들려준 사람에게는 「그래서요?」·
    # 「그랬겠어요」가 먼저다. 이야기 표지가 길이보다 앞선다.
    ("상대가 이야기를 들려줬다", "저는 어제 친구랑 영화를 봤는데요, 그 영화가 정말 재미있었어요. 특히 마지막 장면이 인상 깊었어요.", ["아 그래요"], ("qContinuer", "qEmpathy", "qEcho")),
    ("길지만 이야기는 아니다", "저희 매장은 평일 열 시부터 아홉 시까지 열고 주말에는 여덟 시까지만 엽니다. 공휴일에는 문을 닫습니다.", ["아 네"], ("qParaphrase", "qEcho", "qAskSlow", "qAskAgain", "qAskEasy", "qCheckUnd")),
    ("물어봤고 길게 답했다", "주말에 뭐 했어요?", ["저는 친구를 만나서 같이 밥을 먹고 영화를 봤어요"], ("qEndTurn", "qExpand")),
    ("상대가 말을 맺었다", "저는 곶감을 제일 좋아해요.", ["아 네 저도요 저는 떡볶이도 좋아해요"], ("qExpand", "qNewTopic", "qEndTurn")),
    # v114 — 예전에는 아무것도 안 골랐다. 아무 말도 없는 자리야말로
    # 「먼저 말 걸기」가 필요한 자리다. 빈손으로 두지 않는다.
    ("대화가 아직 없다", "", [], ("qInitiate",)),
]:
    g = _fit(ai, turns)
    ok("맥락", f"{label:22} → {g or '(없음)'}", g in want, g)
_g1 = _fit("주말에 뭐 했어요?", ["네", "그냥요"])
_g2 = _fit("주말에 뭐 했어요?", ["네", "그냥요"], done=(_g1,))
ok("맥락", "이미 띄운 것은 다시 안 고른다", _g2 and _g2 != _g1, f"{_g1} → {_g2}")


# ═══════════════════════════════════════════════════════════
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
_src = re.search(r'    def _fit_intervention\(\).*?(?=\n    def _intv_overdue)', PY, re.S).group(0)
_src = "\n".join(l[4:] if l.startswith("    ") else l for l in _src.split("\n"))
_QL = [{"id": m.group(1), "el": m.group(2)}
       for m in re.finditer(r'\{"id":\s*"(\w+)",\s*"el":\s*"(\w+)"', PY)]
_ALLSOLO = {e: 1 for e in {q["el"] for q in _QL}}      # 1 = 자율
def _fit_solo(scaf):
    convo = [{"role": "ai", "text": "주말에 뭐 했어요?"}, {"role": "user", "text": "네"}]
    _ns = {"convo": convo, "QUEST_LLM": _QL, "re": re, "INTV_ANYTIME": _ANY,
           "idc_state": {"intv_ids": set(), "levels": dict(_ALLSOLO), "counts": {}},
           "rp_progress": {"quests": set()},
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
gz = os.path.getsize(f"{ROOT}/깃헙에 올릴 파일/app.html.gz")
raw = os.path.getsize(f"{ROOT}/app.html")
ok("배포", f"app.html.gz 최신 ({gz//1024}KB / 원본 {raw//1024}KB)", gz > 100_000)

# ═══════════════════════════════════════════════════════════
print("\n════════ ⑯ 파이썬 정적 검사 ════════")
# ★ v115에서 `shutil` 이 import 없이 쓰이고 있는 것을 찾았다. 그 자리는
#   app.html.gz 가 없을 때만 지나가는 **비상용 길**이라 한 번도 안 돌았고,
#   게다가 try/except 로 감싸 있어 터져도 한 줄 찍고 넘어갔다.
#   비상용 길은 정작 비상 때 처음 돌기 때문에, 사람 손으로는 못 찾는다.
#   그래서 기계에 맡긴다.
try:
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pyflakes", f"{ROOT}/main.py"],
                       capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    # '안 쓰는 지역 변수'는 읽기 좋으라고 남겨 둔 것이 있어 넘긴다.
    # 못 넘길 것은 **없는 이름을 부르는 것** — 그건 실행하면 터진다.
    fatal = [l for l in lines if "undefined name" in l]
    minor = [l for l in lines if l not in fatal]
    ok("정적", "없는 이름을 부르는 곳이 없다", not fatal, " / ".join(fatal))
    print(f"     (참고로 넘긴 것 {len(minor)}건" + (": " + minor[0].split(":", 1)[1].strip() if minor else "") + ")")
except FileNotFoundError:
    print("  ℹ️  pyflakes 가 없어 건너뜀 (pip install pyflakes)")
except Exception as e:
    print(f"  ℹ️  정적 검사 건너뜀 ({e})")

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

# -*- coding: utf-8 -*-
"""fittest.py — 넛지가 상황마다 다른 것을 고르는가 (v114)
   _fit_intervention 을 실제로 떼어 와 여러 대화 모양에 대고 돌려 본다."""
import io, sys, re, sys, textwrap
from collections import Counter

SRC = (sys.argv[1] if len(sys.argv) > 1 else "main.py")
s = io.open(SRC, encoding="utf-8").read()

QUEST_LLM = eval(re.search(r"QUEST_LLM = (\[.*?\n\])", s, re.S).group(1))
INTV_ANYTIME = eval(re.search(r"INTV_ANYTIME = (\[[^\]]*\])", s).group(1))
IDC_LEVEL_MODEL = int(re.search(r"IDC_LEVEL_MODEL\s*=\s*(\d+)", s).group(1))
IDC_LEVEL_SOLO  = int(re.search(r"IDC_LEVEL_SOLO\s*=\s*(\d+)", s).group(1))

# ★ v119부터 _fit_intervention 은 _stage_phase(대화의 자리)를 본다. 함께 떼어 온다.
PHASE_BAN = {}
exec(re.search(r"^PHASE_BAN = \{[\s\S]*?^\}", s, re.M).group(0), globals())
body = s[s.index("    def _stage_phase() -> str:"):s.index("    def _intv_overdue() -> bool:")]
src = ("def make(convo, idc_state, rp_progress, scaf_level, rp_plan=None):\n"
       + textwrap.indent(body, "")
       + "\n    _user_turns = lambda: len([m for m in convo if m['role'] == 'user'])"
       + "\n    return _fit_intervention()\n")
g = dict(re=re, QUEST_LLM=QUEST_LLM, INTV_ANYTIME=INTV_ANYTIME, PHASE_BAN=PHASE_BAN,
         IDC_LEVEL_MODEL=IDC_LEVEL_MODEL, IDC_LEVEL_SOLO=IDC_LEVEL_SOLO)
exec(src, g)
make = g["make"]

def st(): return {"intv_ids": set(), "levels": {}, "counts": {}}
def rp(): return {"quests": set()}
def run(ai, mes, scaf=2, state=None, prog=None):
    convo = []
    for m in mes[:-1] if mes else []:
        convo.append({"role": "user", "text": m})
    if ai: convo.append({"role": "ai", "text": ai})
    if mes: convo.append({"role": "user", "text": mes[-1]})
    return make(convo, state or st(), prog or rp(), scaf)

bad = 0
def ok(t, c, extra=""):
    global bad
    print(("  ✅ " if c else "  ❌ ") + t + (("   " + extra) if extra else ""))
    if not c: bad += 1

print("── ① 상황마다 다른 것이 나오는가 ──")
CASES = [
 ("아직 아무 말도 없다",        "",  [],                                     {"qInitiate"}),
 # ※ 원래 여기 쓰던 예문에 「환불은 어렵습니다」가 들어 있었다. 그건 **거절**이라
 #    「그래도 한 번만 부탁드려요」가 나오는 것이 맞다. 거절이 안 섞인 긴 문장으로 바꿨다.
 ("한꺼번에 아주 길게 말했다",
  "저희 가게는 평일에는 열 시부터 아홉 시까지 열고, 주말에는 여덟 시까지만 엽니다. "
  "그리고 매달 둘째 넷째 월요일은 정기 휴무라서 그날은 문을 닫습니다. 참고해 주세요.",
  ["네"],                                                                    {"qAskSlow","qParaphrase","qAskAgain","qCheckUnd"}),
 ("상대가 거절했다",            "죄송하지만 그건 좀 어렵습니다.", ["아…"],      {"qHold","qAlt","qCond"}),
 # ※ 「환불규정을 확인해 주세요」는 어려운 말이면서 **부탁**이기도 하다.
 #    표지가 겹치면 더 또렷한 쪽(부탁)이 이긴다 — 그게 맞다. 그래서 부탁이 아닌 문장으로 본다.
 ("어려운 말이 나왔다",          "그건 환불규정에 따라 처리됩니다.", ["아"],   {"qAskEasy","qAskAgain","qParaphrase"}),
 ("어려운 말 + 부탁 → 부탁이 이긴다", "환불규정을 먼저 확인해 주세요.", ["아"], {"qRefuse","qAlt","qCond","qCounter"}),
 ("감정이 실렸다",              "요즘 일이 많아서 좀 힘들어요.", ["그래요"],  {"qEmpathy","qContinuer"}),
 ("이야기를 하고 멈췄다",        "어제 친구를 만나서 같이 밥을 먹었어요.", ["네"], {"qContinuer","qEmpathy","qEcho"}),
 ("물었는데 짧게만 답한다",      "주말에 뭐 했어요?", ["네", "응"],           {"qKeepTurn","qExpand","qFiller"}),
 ("내가 길게 말했다",           "그렇군요.",
  ["저는 지난 주말에 친구들이랑 같이 한강에 가서 자전거를 타고 저녁까지 놀다 왔어요"],  {"qCheckUnd","qEndTurn"}),
 # ※ 예전에는 「내가 물었다」에 qHold(다시 청하기)를 붙여 놨었다. 잘못이었다 —
 #    다시 청하기는 **상대가 거절한 자리**에서만 말이 된다. 바로 위 항목이 그 자리다.
 #    내가 그냥 물은 자리는 특별할 것이 없으므로 아래층(아무 때나 되는 것)으로 간다.
 ("내가 물었다 (특별한 자리 아님)", "네, 맞아요.", ["이거 얼마예요?"],          {"qExpand","qNewTopic","qEndTurn","qTakeTurn","qEcho","qKeepTurn"}),
 ("여덟 차례를 넘겼다",          "그렇군요.", ["네"]*8,                        {"qCloseTopic","qShiftTopic","qReturn","qNewTopic","qCircum","qNative","qFiller"}),
 # v114에서 새로 연 자리 — 여기가 아니면 말이 안 되는 것들
 ("무언가를 청해 왔다",          "같이 저녁 먹으러 갈까요?", ["음"],            {"qRefuse","qAlt","qCond","qCounter"}),
 ("마침표 붙은 부탁",            "이거 좀 도와주세요.", ["아"],                {"qRefuse","qAlt","qCond","qCounter"}),
 ("상대가 되물었다",             "네?", ["제가 아까 말한 그거요"],             {"qRephrase","qCircum","qSelfFix"}),
 ("무슨 뜻이냐고 한다",          "무슨 뜻이에요?", ["그러니까요"],             {"qRephrase","qCircum","qSelfFix"}),
]
for name, ai, mes, expect in CASES:
    got = run(ai, mes)
    ok(name.ljust(22) + "→ " + (got or "(없음)"), got in expect, "" if got in expect else "기대: " + "/".join(sorted(expect)))

print("\n── ② 22개가 되살아났는가 (v113에서는 6개뿐) ──")
seen = set()
import random
random.seed(7)
POOL = [c[1:3] for c in CASES] + [
  ("네, 그럼 언제 오실 수 있으세요?", ["음"]),
  ("정말요? 그거 진짜 다행이네요!", ["네 다행이에요"]),
  ("예약확인서를 보여 주시겠어요?", ["네?"]),
]
# 「상대가 거듭 짧게만 답한다」는 한 번으로는 안 걸린다 — 발화가 둘 필요하다
SHORT2 = [{"role":"ai","text":"음."},{"role":"user","text":"네"},
          {"role":"ai","text":"네."},{"role":"user","text":"알겠어요"}]
for ai, mes in POOL:
    for scaf in (2, 3):
        state, prog = st(), rp()
        for _ in range(12):                       # 같은 자리에서 계속 뽑으면 다음 것으로 넘어간다
            q = make([{"role":"user","text":m} for m in mes[:-1]]
                     + ([{"role":"ai","text":ai}] if ai else [])
                     + ([{"role":"user","text":mes[-1]}] if mes else []),
                     state, prog, scaf)
            if not q: break
            seen.add(q); state["intv_ids"].add(q)
            el = next((x["el"] for x in QUEST_LLM if x["id"] == q), "")
            state["counts"][el] = state["counts"].get(el, 0) + 1
# 발화가 둘 이상 쌓인 대화도 한 번 훑는다
for scaf in (2, 3):
    state = st()
    for _ in range(14):
        q = make(SHORT2, state, rp(), scaf)
        if not q: break
        seen.add(q); state["intv_ids"].add(q)
        el = next((x["el"] for x in QUEST_LLM if x["id"] == q), "")
        state["counts"][el] = state["counts"].get(el, 0) + 1
allq = {q["id"] for q in QUEST_LLM}
print("     닿은 것 %d개 / 전체 %d개" % (len(seen), len(allq)))
print("     못 닿은 것: " + (", ".join(sorted(allq - seen)) or "없음"))
ok("v113(6개)보다 훨씬 많다", len(seen) >= 25, "%d개" % len(seen))
for q in ("qAskSlow", "qAskAgain", "qAskEasy", "qEmpathy", "qContinuer",
          "qCheckUnd", "qRefuse", "qAlt", "qCond", "qRephrase", "qSelfFix"):
    ok("되살아났다 · " + q, q in seen)
# qAskFast 만 일부러 자리를 안 줬다 — 말이 느린지는 글로 알 수 없다
ok("qAskFast 는 일부러 뺐다(주석 있음)", "qAskFast" not in seen
   and "말이 **느린지**는 글로는 알 수 없다" in s)

print("\n── ③ 요소가 한쪽으로 쏠리지 않는가 ──")
state, prog = st(), rp()
picks = []
for i in range(16):
    ai, mes = POOL[i % len(POOL)]
    q = make([{"role":"ai","text":ai}] + [{"role":"user","text":m} for m in mes], state, prog, 3)
    if not q: break
    picks.append(q); state["intv_ids"].add(q)
    el = next((x["el"] for x in QUEST_LLM if x["id"] == q), "")
    state["counts"][el] = state["counts"].get(el, 0) + 1
c = Counter(next(x["el"] for x in QUEST_LLM if x["id"] == q) for q in picks)
print("     " + str(dict(c)))
ok("한 요소가 절반을 넘지 않는다", picks and max(c.values()) <= len(picks) / 2 + 1,
   "최다 %d/%d" % (max(c.values()), len(picks)))
ok("네 갈래 이상이 나온다", len(c) >= 4, "%d갈래" % len(c))

print("\n── ④ 같은 것을 두 번 주지 않는가 ──")
ok("한 번 준 것은 다시 안 나온다", len(picks) == len(set(picks)))

print("\n" + ("💥 %d건" % bad if bad else "🎉 넛지 고르기 이상 없음"))
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
"""rotatetest.py — 다섯 편이 **돌아가며** 나오는가 (v140)

v139 까지 한 편만 계속 나왔다. 화면은 place 를, 서버는 id 를 봤기 때문이다.
문자열 검사로는 못 잡는다 — **화면이 하는 그대로** 열두 번 뽑아 본다.
★ 규칙을 베끼지 않는다. main.py 의 _idc_pick 을 떼어 그대로 돌린다.
"""
import io, re, os, sys, json
from pathlib import Path
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()
HT = io.open(f"{ROOT}/app.html", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else f"   {x}"))
    if not c: bad.append(m)

ns = {"os": os, "json": json, "Path": Path, "re": re,
      "_clean_str": lambda x, n=999: (str(x or "")[:n]).strip()}
for pat in (r"IDC_CORPUS_DIR = .*?\n_idc_corpus_dx = \{[^\}]*\}\n",
            r"def _load_idc_corpus\(\).*?\n\n\n",
            r"def _idc_pick\(.*?\n\n\n"):
    m = re.search(pat, PY, re.S)
    if not m:
        ok("main.py 에서 고르는 코드를 찾는다", False, pat[:40]); print("\n💥"); sys.exit(1)
    exec(m.group(0), ns)
ns["_idc_corpus"] = {}
os.chdir(ROOT)
ns["_load_idc_corpus"]()
pick = ns["_idc_pick"]

print("── ① 화면이 하는 그대로 열두 번 뽑는다 (화계는 고정)")
# 화면 쪽 규칙: 본 것을 pool-1 개만 쥔다
for key in sorted(ns["_idc_corpus"]):
    pool = ns["_idc_corpus"][key]
    keep = max(1, len(pool) - 1)
    seen, got = [], []
    for _ in range(12):
        it = pick(key, "polite", seen)          # 페이더를 안 건드린 학습자
        got.append(it["id"])
        seen = [x for x in seen if x != it["id"]] + [it["id"]]
        seen = seen[-keep:]
    c = Counter(got)
    ok(f"{key:<9} 다섯 편이 다 나온다 {len(c)}/{len(pool)}", len(c) == len(pool),
       " ".join(x.split("-")[-1] for x in got))
    ok(f"{key:<9} 같은 것이 잇달아 안 나온다",
       all(got[i] != got[i + 1] for i in range(len(got) - 1)),
       " ".join(x.split("-")[-1] for x in got))
    # 한 바퀴(=편 수)마다 겹침이 없어야 한다
    n = len(pool)
    rounds = [got[i:i + n] for i in range(0, len(got) - n + 1, n)]
    ok(f"{key:<9} 한 바퀴 안에서 안 겹친다",
       all(len(set(r)) == n for r in rounds if len(r) == n))

print("\n── ② 화계를 바꿔도 돌아간다")
for tier in ("formal", "polite", "banmal"):
    seen, got = [], []
    pool = ns["_idc_corpus"]["listen"]
    keep = max(1, len(pool) - 1)
    for _ in range(10):
        it = pick("listen", tier, seen)
        got.append(it["id"])
        seen = [x for x in seen if x != it["id"]] + [it["id"]]
        seen = seen[-keep:]
    ok(f"{tier:<7} 다섯 편이 다 나온다", len(set(got)) == len(pool),
       " ".join(x.split("-")[-1] for x in got))

print("\n── ③ 첫 판은 화계가 맞는 것으로 연다")
for tier in ("formal", "polite", "banmal"):
    hits = sum(1 for _ in range(30) if pick("move", tier, [])["tier"] == tier)
    ok(f"{tier:<7} 처음 열 때 그 화계가 나온다 {hits}/30", hits == 30)

print("\n── ④ 화면이 편 id 를 보내는가 (place 가 아니라)")
ok("seen 에 idlSeenGet 을 보낸다", "seen: idlSeenGet(" in HT)
ok("자리 설명은 avoid 로 따로 보낸다", "avoid: idlPlaces" in HT)
ok("받은 id 를 적어 둔다", re.search(r"idlSeenPut\(e\.key,\s*d\.id", HT) is not None)
ok("기기에 남긴다(새로 고쳐도)", "localStorage.setItem(IDL_SEEN_KEY" in HT)
ok("편 수보다 하나 적게 쥔다", "(pool || 5) - 1" in HT)
ok("서버가 편 수를 알려 준다", '"pool": len(_idc_corpus.get(key) or [])' in PY)

print("\n── ⑤ 힌트가 마흔 편에 다 있는가 (틀리면 되돌아가므로 꼭 있어야 한다)")
miss = [it["id"] for k in ns["_idc_corpus"] for it in ns["_idc_corpus"][k]
        if not (it["quiz"].get("hint") or "").strip()]
ok(f"힌트가 빈 편이 없다 {40 - len(miss)}/40", not miss, ", ".join(miss[:6]))

print("\n" + (f"💥 {len(bad)}건" if bad else "🎉 돌려 뽑기 이상 없음"))
sys.exit(1 if bad else 0)

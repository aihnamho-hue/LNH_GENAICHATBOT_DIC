# -*- coding: utf-8 -*-
"""corpustest.py — 검수한 대화문이 서버에 제대로 물렸는가 (v135)

35편을 만들어 놓고 **앱이 안 쓰면** 아무 소용이 없다. 그 연결만 본다.
"""
import io, re, json, os, sys, asyncio
from pathlib import Path
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()
HT = io.open(f"{ROOT}/app.html", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else f"   {x}"))
    if not c: bad.append(m)

print("── ① 코퍼스를 읽어 오는가")
ns = {"os": os, "json": json, "Path": Path, "re": re,
      "_clean_str": lambda x, n=999: (str(x or "")[:n]).strip()}
for pat in (r"IDC_CORPUS_DIR = .*?\n_idc_corpus_dx = \{[^\}]*\}\n",
            r"def _load_idc_corpus\(\).*?\n\n\n",
            r"def _idc_pick\(.*?\n\n\n",
            r"def _idc_corpus_scene\(.*?\n            \"sub\": item\.get\(\"sub\", \"\"\), \"topic_lv\": item\.get\(\"topic_lv\", \"\"\)\}"):
    m = re.search(pat, PY, re.S)
    if not m: ok("main.py 에서 코퍼스 코드를 찾는다", False, pat[:40]); print("\n💥"); sys.exit(1)
    exec(m.group(0), ns)
ns["_idc_corpus"] = {}
os.chdir(ROOT)
ns["_load_idc_corpus"]()
C = ns["_idc_corpus"]
ok(f"편이 다 실렸다 ({ns['_idc_corpus_dx']['items']}편)", ns["_idc_corpus_dx"]["items"] >= 35)
ok("읽다 만 것이 없다", not ns["_idc_corpus_dx"]["err"], ns["_idc_corpus_dx"]["err"])

print("\n── ② 요소 이름이 서버 목록과 맞는가")
keys = set(re.findall(r'\{"key": "(\w+)"', re.search(r"IDC_LESSON = \[(.*?)\n\]", PY, re.S).group(1)))
ok(f"코퍼스 요소가 다 서버에 있다 {sorted(C)}", set(C) <= keys, set(C) - keys)
ok("검수본이 없는 요소도 안다", keys - set(C) == {"stage"}, keys - set(C))

print("\n── ③ 고르기")
for k, v in sorted(C.items()):
    ok(f"{k} {len(v)}편 · 세 화계가 다 있다", len({x['tier'] for x in v}) == 3,
       Counter(x["tier"] for x in v))
_p = ns["_idc_pick"]
for k in sorted(C):
    for t in ("formal", "polite", "banmal"):
        got = [_p(k, t, []) for _ in range(15)]
        ok(f"{k}/{t} 화계가 맞는 것만 나온다", all(g["tier"] == t for g in got),
           {g["tier"] for g in got})
seen = [x["id"] for x in C["repair"][:4]]
ok("본 것은 뒤로 미룬다", {_p("repair", "formal", seen)["id"] for _ in range(20)}
   == {C["repair"][4]["id"]})
ok("다 봤으면 다시 처음부터", _p("repair", "polite", [x["id"] for x in C["repair"]]) is not None)

print("\n── ④ 내보내는 모양이 예전과 같은가")
it = C["context"][0]
sc = ns["_idc_corpus_scene"](it, {})
for k in ("from", "place", "place_n", "script", "mark", "quiz"):
    ok(f"열쇠 {k}", k in sc)
ok("표시할 줄이 학습자 발화", sc["script"][sc["mark"]]["speaker"] == "user")
ok("quiz 가 a·b·c 와 ans 를 낸다", all(x in sc["quiz"] for x in ("a", "b", "c", "ans", "n")))
ok("ans 가 실제 정답을 가리킨다", sc["quiz"][sc["quiz"]["ans"]] == it["quiz"]["right"])
ok("정답 자리가 섞인다",
   len({ns["_idc_corpus_scene"](it, {})["quiz"]["ans"] for _ in range(40)}) == 3)
ok("문형·연습거리를 함께 넘긴다", sc["forms"] and sc["drills"])

print("\n── ⑤ 서버가 검수본을 **먼저** 쓰는가")
ok("/idc-lesson 이 _idc_pick 을 먼저 부른다",
   re.search(r"picked = _idc_pick\(key, tier, seen\)[\s\S]{0,2000}?_idc_scene\(el", PY) is not None)
ok("검수본이면 모델을 안 부르고 곧바로 돌려준다",
   re.search(r"if picked is not None:[\s\S]{0,900}?return \{\"el\": key", PY) is not None)
ok("meaning 열쇠가 화면이 읽는 것과 같다 (ko/native)",
   '{"ko": t, "native"' in PY and "m.ko" in HT)
ok("검수본 판을 따로 센다", '_idc_dx.get("corpus"' in PY)
ok("/version 에 corpus·gen·have 가 보인다",
   '"corpus": _idc_dx.get("corpus", 0)' in PY and '"have": {k: len(v)' in PY)

print("\n── ⑥ ④문형·⑤연습도 검수본을 쓰는가")
ok("화면이 편 id 를 같이 보낸다", 'id: d.id || ""' in HT)
ok("/idc-drill 이 id 로 검수본을 찾는다", '_cid = _clean_str(b.get("id"), 24)' in PY)
ok("찾으면 모델을 안 부른다",
   re.search(r'if _out:[\s\S]{0,200}?return \{"drills": _out\}', PY) is not None)
ok("④문형은 검수본을 먼저 쓴다", "(d.forms && d.forms.length) ? d.forms.slice()" in HT)
ok("검수본 문형이 없을 때만 QUEST_FORM", "if (!(d.forms && d.forms.length)) {" in HT)

print("\n── ⑦ 코퍼스가 웹으로 새지 않는가")
ok("static/ 밑이 아니다", not os.path.isdir(f"{ROOT}/static/idc_corpus"))
ok("정답이 들어 있으므로 공개되면 안 된다", "IDC_CORPUS_DIR" in PY
   and 'StaticFiles(directory="idc_corpus"' not in PY)

print("\n" + (f"💥 {len(bad)}건\n   " + "\n   ".join(bad) if bad else "🎉 코퍼스 연결 이상 없음"))
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
"""sharesrv.py — 교실 공유의 **서버 쪽**을 실제로 돌려 본다 (v142)

★ 규칙을 베끼지 않는다. main.py 에서 코드를 떼어 그대로 실행한다.
  코드 만들기 · 읽기 · 지난 것 치우기 · 넘칠 때 밀어내기까지.
"""
import io, re, os, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else f"   {x}"))
    if not c: bad.append(m)

ns = {"os": os, "time": time, "re": re,
      "_clean_str": lambda x, n=999: (str(x or "")[:n]).strip()}
for pat in (r"SHARE_TTL = .*?\n_share_box: dict = \{\}.*?\n",
            r"def _share_gc\(\).*?\n\n\n",
            r"def _share_code\(\).*?\n\n\n"):
    m = re.search(pat, PY, re.S)
    if not m:
        ok("main.py 에서 공유 코드를 찾는다", False, pat[:40]); print("\n💥"); sys.exit(1)
    exec(m.group(0), ns)

print("── ① 코드가 겹치지 않는가")
box = ns["_share_box"]
codes = set()
for _ in range(3000):
    c = ns["_share_code"]()
    box[c] = {"turns": [], "title": "", "at": time.time()}
    codes.add(c)
ok(f"3000개를 만들어도 다 다르다 {len(codes)}", len(codes) == 3000)
ok("네 글자다", all(len(c) == 4 for c in codes))
ok("헷갈리는 글자가 없다 (0·O·1·I·L)",
   not any(ch in "01OIL" for c in codes for ch in c),
   "".join(sorted({ch for c in codes for ch in c})))

print("\n── ② 지난 것을 치우는가")
box.clear()
box["OLD1"] = {"turns": [], "title": "", "at": time.time() - ns["SHARE_TTL"] - 10}
box["NEW1"] = {"turns": [], "title": "", "at": time.time()}
ns["_share_gc"]()
ok("두 시간 지난 것은 사라진다", "OLD1" not in box)
ok("아직 살아 있는 것은 남는다", "NEW1" in box)

print("\n── ③ 넘치면 오래된 것부터 밀어내는가")
box.clear()
for i in range(ns["SHARE_MAX"] + 25):
    box[f"C{i:04d}"] = {"turns": [], "title": "", "at": time.time() - (1000 - i)}
ns["_share_gc"]()
ok(f"보관은 {ns['SHARE_MAX']}건까지 {len(box)}", len(box) <= ns["SHARE_MAX"])
ok("가장 오래된 것이 먼저 나간다", "C0000" not in box and f"C{ns['SHARE_MAX']+24:04d}" in box)

print("\n── ④ 한 반(45명)이 한꺼번에 써도 되는가")
box.clear()
for _ in range(45):
    box[ns["_share_code"]()] = {"turns": [{"r": "me", "t": "x"}], "title": "", "at": time.time()}
ns["_share_gc"]()
ok("마흔다섯 건이 다 남는다", len(box) == 45, len(box))

print("\n── ⑤ 무엇을 담기로 했는가 (main.py 를 읽는다)")
ok("이름을 안 담는다", "이름은 담지 않는다" in PY)
ok("열두 줄까지만", "raw[:12]" in PY)
ok("한 줄은 400자까지", '_clean_str(x.get("t"), 400)' in PY)
ok("메모리에만 둔다(파일로 안 남긴다)",
   "_share_box" in PY and not re.search(r"_share_box.*open\(", PY))

print("\n" + (f"💥 {len(bad)}건" if bad else "🎉 서버 쪽 이상 없음"))
sys.exit(1 if bad else 0)

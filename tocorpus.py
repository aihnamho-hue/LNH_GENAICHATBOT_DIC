# -*- coding: utf-8 -*-
"""tocorpus.py — 검토본(IDC대화문/)을 앱이 읽는 곳(idc_corpus/)으로 옮긴다

★ 왜 따로 두나
  검토는 IDC대화문/ 에서 하고, 앱은 idc_corpus/ 를 읽는다.
  같은 파일을 두 곳에 두면 **한쪽만 고치는 사고**가 난다. 실제로 두 번 났다.
  그래서 옮기는 일을 손이 아니라 이 파일이 한다.

  python3 tocorpus.py         옮긴다
  python3 tocorpus.py --check 옮겼는지만 본다 (안 맞으면 1로 끝난다)
"""
import json, io, os, sys, glob

SRC, DST = ".", "../idc_corpus"
SKIP = {"lv13.json", "lv23.json"}
check = "--check" in sys.argv

os.makedirs(DST, exist_ok=True)
bad, n = [], 0
for p in sorted(glob.glob(os.path.join(SRC, "*.json"))):
    b = os.path.basename(p)
    if b in SKIP: continue
    src = io.open(p, encoding="utf-8").read()
    d = os.path.join(DST, b)
    old = io.open(d, encoding="utf-8").read() if os.path.exists(d) else ""
    if src == old:
        print(f"  = {b}"); n += 1; continue
    if check:
        bad.append(b); print(f"  ✗ {b}  ← idc_corpus 가 낡았다"); continue
    io.open(d, "w", encoding="utf-8").write(src)
    J = json.loads(src)
    print(f"  → {b}  {len(J['items'])}편"); n += 1

if bad:
    print(f"\n  ✗ {len(bad)}개가 안 옮겨졌다.  python3 tocorpus.py  를 돌려 주세요.")
    sys.exit(1)
print(f"\n  ✓ {n}개 파일이 idc_corpus/ 와 같다")

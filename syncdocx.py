# -*- coding: utf-8 -*-
"""syncdocx.py — 선생님이 docx 에서 고친 것을 json 으로 되돌린다.

검토는 docx 로 하고 앱은 json 을 쓰므로, 고친 것이 json 에 안 들어가면
**검토가 헛일이 된다.** 물음·선택지·힌트를 docx 기준으로 덮어쓴다.
(대화문·뜻풀이·문형·연습은 표 밖에 있어 자리를 잡기 어려우므로 여기서는 다루지 않는다)
"""
from docx import Document
import json, io, glob, re, sys

M = {"01": "repair", "02": "strategy", "03": "turn", "04": "topic",
     "05": "move", "06": "listen", "07": "context", "08": "stage"}
tot = 0
for f in sorted(glob.glob("IDC학습_대화문_*.docx")):
    n = re.search(r"_(\d\d)_", f).group(1); key = M[n]
    d = Document(f)
    blocks = []
    for t in d.tables:
        cells = [r.cells[0].text.strip() for r in t.rows]
        if cells and cells[0].startswith("②"):
            blocks.append(cells)
    p = f"{key}.json"
    J = json.load(io.open(p, encoding="utf-8"))
    hit = 0
    for it, cs in zip(J["items"], blocks):
        q = it["quiz"]
        newq = cs[0][3:].strip()
        if newq and newq != q.get("q", ""):
            q["q"] = newq; hit += 1
        opts, right = [], None
        for c in cs[1:]:
            if c.startswith(("ⓐ", "ⓑ", "ⓒ")):
                txt = c[2:].split("← 정답")[0].strip()
                opts.append(txt)
                if "← 정답" in c: right = txt
            elif c.startswith("틀렸을 때"):
                h = c.split("→", 1)[1].strip()
                if h and h != q.get("hint", ""):
                    q["hint"] = h; hit += 1
        if right is not None and len(opts) == 3:
            wrongs = [o for o in opts if o != right]
            if q.get("right") != right: q["right"] = right; hit += 1
            # ★ docx 의 ⓐⓑⓒ 는 **섞어서** 찍는다(정답이 늘 ⓐ면 검토자가 안 읽고 안다).
            #   그래서 읽어 온 차례를 그대로 wrong1·wrong2 에 넣으면, 고친 것이 없어도
            #   둘이 자리를 바꾸며 「되돌림」이 잡힌다. 돌려도 돌려도 안 끝난다.
            #   내용이 그대로면 자리도 그대로 둔다.
            if sorted(wrongs) == sorted([q.get("wrong1", ""), q.get("wrong2", "")]):
                wrongs = [q.get("wrong1", ""), q.get("wrong2", "")]
            for i, w in enumerate(wrongs, 1):
                if q.get(f"wrong{i}") != w: q[f"wrong{i}"] = w; hit += 1
    if hit:
        io.open(p, "w", encoding="utf-8").write(json.dumps(J, ensure_ascii=False, indent=1))
    print(f"  {key:<10} {hit}군데 되돌림")
    tot += hit
print(f"\n  모두 {tot}군데")

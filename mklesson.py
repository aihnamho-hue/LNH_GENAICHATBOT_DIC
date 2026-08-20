# -*- coding: utf-8 -*-
"""mklesson.py — 화면 검사가 먹을 /idc-lesson 응답을 **main.py 로 만든다**

  python3 mklesson.py       →  /tmp/w/lesson.json · /tmp/w/lesson_stage.json

★ 왜 손으로 안 적나
  검사가 원본을 베끼면, 원본이 바뀌어도 검사는 옛말을 하고 있게 된다.
  실제로 다섯 번 그랬다. 그래서 여기서는 main.py 의 **코드를 떼어 그대로 돌린다.**
  main.py 가 바뀌면 이 파일이 내는 것도 저절로 바뀐다. (corpustest.py 와 같은 방식)
"""
import io, re, os, sys, json
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()

ns = {"os": os, "json": json, "Path": Path, "re": re,
      "_clean_str": lambda x, n=999: (str(x or "")[:n]).strip()}
for pat in (r"IDC_CORPUS_DIR = .*?\n_idc_corpus_dx = \{[^\}]*\}\n",
            r"def _load_idc_corpus\(\).*?\n\n\n",
            r"def _idc_pick\(.*?\n\n\n",
            r"def _idc_corpus_scene\(.*?\n            \"sub\": item\.get\(\"sub\", \"\"\), \"topic_lv\": item\.get\(\"topic_lv\", \"\"\)\}"):
    mt = re.search(pat, PY, re.S)
    if not mt:
        print("  ❌ main.py 에서 코퍼스 코드를 못 찾음:", pat[:44]); sys.exit(1)
    exec(mt.group(0), ns)

# IDC_ELS 도 main.py 에서 읽는다 — 이름·이모지를 손으로 적으면 어긋난다
els = {}
for mt in re.finditer(r'\{"key":\s*"(\w+)",\s*"easy":\s*"([^"]*)",\s*"acad":\s*"([^"]*)"'
                      r'(?:[^\}]*?"emoji":\s*"([^"]*)")?', PY):
    k = mt.group(1)
    els.setdefault(k, {"key": k, "easy": mt.group(2), "acad": mt.group(3),
                       "emoji": mt.group(4) or "💭"})

ns["_idc_corpus"] = {}
os.chdir(ROOT)
ns["_load_idc_corpus"]()

OUT = "/tmp/w"; os.makedirs(OUT, exist_ok=True)
for name, key in (("lesson.json", "topic"), ("lesson_stage.json", "stage")):
    item = ns["_idc_pick"](key, "polite", [])
    if item is None:
        print(f"  ❌ {key} 코퍼스가 안 실렸다"); sys.exit(1)
    tr = {}                                   # 한국어로 볼 때 — 번역이 0회다
    scene = ns["_idc_corpus_scene"](item, tr)
    el = els.get(key, {"easy": key, "acad": key, "emoji": "💭"})
    d = {"el": key, "easy": el["easy"], "acad": el["acad"], "emoji": el["emoji"],
         "meaning": [{"ko": t, "native": ""} for t in (item.get("meaning") or [])],
         **scene}
    io.open(f"{OUT}/{name}", "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    ff = d.get("forms_filled") or []
    print(f"  → {OUT}/{name}   {d['id']}  문형 {len(d.get('forms') or [])}개"
          f" · 채운 꼴 {len(ff)}개 · 물음 {d['quiz'].get('type', 'pick')}")

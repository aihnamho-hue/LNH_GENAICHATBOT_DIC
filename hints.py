# -*- coding: utf-8 -*-
"""hints.py — 힌트가 빈 13편을 채운다 (v140)

★ 왜 필요해졌나
  v140부터 틀리면 1초 뒤 저절로 첫 화면으로 돌아간다. 몇 번이든 다시 고를 수 있다.
  그런데 **짚어 주는 말이 없으면 다시 고르는 것이 찍기**가 된다.
  40편 중 13편에 힌트가 비어 있었다 — 있는 27편과 없는 13편이 섞여 있었던 것이다.

★ 어떻게 쓰나
  정답을 말해 주지 않는다. **어디를 다시 보라**고만 한다.
  「~를 다시 읽어 보세요」처럼 자리를 가리키는 말이다.
  화계는 그 편의 것을 따른다(반말 편은 반말로).
"""
import json, io, glob, sys

HINT = {
 "move-2":     "「가고 싶은데」로 시작했잖아. 가기 싫다는 말이었을까?",
 "move-3":     "「안 될까요?」에서 한 번 막혔어요. 그다음에 무엇을 했는지 보세요.",
 "move-4":     "「그래」를 이미 받았어. 그런데 왜 말을 더 이었을까?",
 "repair-2":   "모르는 말이 하나 나왔습니다. 그 말을 어떻게 했는지 보십시오.",
 "repair-3":   "친구가 「어… 응」 하고 흐렸어. 그다음에 왜 같은 말을 두 번 했을까?",
 "repair-5":   "호아랑이 「역 안입니까?」 하고 되물었습니다. 그다음에 무엇을 바꿔 말했는지 보십시오.",
 "strategy-2": "「퍼」는 한국어가 아니야. 그걸 알면서 왜 그대로 말했을까?",
 "strategy-4": "바로 대답을 못 했습니다. 그 자리에서 무엇을 먼저 했는지 보십시오.",
 "strategy-5": "「졸다」라는 말을 안 썼어. 대신 무엇으로 말했는지 봐.",
 "topic-2":    "친구 이야기를 받기만 했을까? 내 이야기도 하나 붙였잖아.",
 "topic-4":    "가야 한다는 말만 한 게 아니에요. 뒤에 무엇을 더 붙였는지 보세요.",
 "topic-5":    "상대가 먼저 자기 이야기를 했습니다. 그다음에 무엇을 했는지 보십시오.",
 "turn-5":     "상대가 말을 자르고 들어왔어요. 그때 무엇을 했는지 보세요.",
}

hit, left = 0, []
for f in sorted(glob.glob("*.json")):
    if f in ("lv13.json", "lv23.json"): continue
    J = json.load(io.open(f, encoding="utf-8"))
    for it in J["items"]:
        h = (it["quiz"].get("hint") or "").strip()
        if h: continue
        if it["id"] not in HINT:
            left.append(it["id"]); continue
        it["quiz"]["hint"] = HINT[it["id"]]; hit += 1
    io.open(f, "w", encoding="utf-8").write(json.dumps(J, ensure_ascii=False, indent=1))

n = sum(1 for f in glob.glob("*.json") if f not in ("lv13.json", "lv23.json")
        for it in json.load(io.open(f, encoding="utf-8"))["items"]
        if (it["quiz"].get("hint") or "").strip())
print(f"  {hit}편에 힌트를 넣음 · 이제 힌트 있는 편 {n}/40")
if left:
    print("  ✗ 아직 빈 편:", ", ".join(left)); sys.exit(1)

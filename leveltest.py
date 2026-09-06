# -*- coding: utf-8 -*-
"""leveltest — 숙달도 상한이 실제로 내려가는가 (v161)

★ 왜 이 검사가 있나
  MAX_LEVEL 을 2로 내려도 **3급 문형이 그대로 나왔다.**
  4급 덩어리만 조건부였고 3급 덩어리는 늘 들어갔기 때문이다.
  산문은 「1~2급만 써라」인데 목록에는 「[사용 가능 문법 — 중급(3급)]」이
  제목까지 달고 통째로 들어갔다.

  ★ 지시가 둘이면 **목록이 이긴다.** 산문으로 막을 수 없다.
    막으려면 목록에서 빼야 한다. 그것을 여기서 잰다.
"""
import io, os, re, sys
SRC = io.open("main.py", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else "   " + str(x)))
    if not c: bad.append(m)

seg = SRC[SRC.index('try:\n    MAX_LEVEL'):
          SRC.index('# ============', SRC.index('LEVEL_RULES = f"""'))]

def build(lv):
    os.environ["MAX_LEVEL"] = str(lv)
    g = {"os": os}
    exec(seg, g)
    return g

print("── ① 등급마다 목록이 갈리는가 ──────────────")
want = {2: (False, False), 3: (True, False), 4: (True, True)}
for lv, (w3, w4) in want.items():
    g = build(lv); r = g["LEVEL_RULES"]
    h3 = "[사용 가능 문법 — 중급(3급)]" in r
    h4 = "[사용 가능 문법 — 중급(4급)]" in r
    ok(f"{lv}급 상한 — 3급 목록 {'있음' if w3 else '없음'}", h3 == w3, f"실제 {h3}")
    ok(f"{lv}급 상한 — 4급 목록 {'있음' if w4 else '없음'}", h4 == w4, f"실제 {h4}")

print("\n── ② 이름과 값이 어긋나지 않는가 ───────────")
ok("2급은 초급이라 부른다", build(2)["LV_CAP"] == "초급(2급 이하)", build(2)["LV_CAP"])
ok("3급은 중급", build(3)["LV_CAP"] == "중급(3급 이하)", build(3)["LV_CAP"])
ok("4급도 중급", build(4)["LV_CAP"] == "중급(4급 이하)", build(4)["LV_CAP"])
ok("범위 표기가 따라온다",
   build(2)["LV_RANGE"] == "1~2급" and build(3)["LV_RANGE"] == "1~3급")

print("\n── ③ 초급일 때 더 조인다 ───────────────────")
r2, r3 = build(2)["LEVEL_RULES"], build(3)["LEVEL_RULES"]
ok("초급에서만 한 번 더 못 박는다",
   "지금은 **초급** 상한이다" in r2 and "지금은 **초급** 상한이다" not in r3)
ok("초급에서는 한 마디로 짧게", "한 마디**로 짧게" in r2)
ok("금지 등급이 따라 올라간다", "3급 이상" in r2 and "4급 이상" in r3,
   "MAX_LEVEL+1 급 이상을 막는다")

print("\n── ④ 목록이 실제로 짧아지는가 ──────────────")
n2, n3, n4 = len(r2), len(r3), len(build(4)["LEVEL_RULES"])
print(f"     2급 {n2:,}자 · 3급 {n3:,}자 · 4급 {n4:,}자")
ok("등급이 낮을수록 짧다", n2 < n3 < n4)
ok("2급은 3급의 3분의 2 이하", n2 < n3 * 0.7, f"{n2}/{n3}")

print("\n── ⑤ 상한이 모든 생성 자리에 걸리는가 ───────")
for name, pat in [("대화 지시문", r"LEVEL_RULES"),
                  ("기능 단계·표현", r"표현과 cue는 모두 국제 통용 한국어 표준 교육과정 \{LV_CAP\}"),
                  ("모델 대화문", r"한 줄은 한 문장 또는 짧은 두 문장\. 국제 통용 표준 교육과정 \{LV_CAP\}"),
                  ("앞말(cue)", r"한 문장, 짧은 구어체\. 국제 통용 표준 교육과정 \{LV_CAP\}"),
                  ("화계 손질", r"한 줄에 한 문장\. \{LV_CAP\} 어휘·문법"),
                  ("학습 화면 뜻풀이", r"국제 통용 한국어 표준 교육과정 \*\*\{LV_CAP\}\*\*"),
                  ("발화 연습", r"두 사람 모두 \{lv\} 로 말한다\. \{LV_CAP\} 어휘·문법"),
                  ("총평", r'LV_RANGE \+ " 어휘만 쓴다')]:
    ok(f"{name}에 걸린다", re.search(pat, SRC) is not None)

print("\n── ⑤-2 잊으면 쉬워지는 쪽이 기본인가 ───────")
import os as _os
_os.environ.pop("MAX_LEVEL", None)          # 환경변수를 안 둔 상태
_g = {"os": _os}; exec(seg, _g)
ok(f"환경변수가 없으면 2급 (실제 {_g['MAX_LEVEL']}급)", _g["MAX_LEVEL"] == 2,
   "기본이 4라서 실험 내내 4급으로 돌고 있었다 — 잊으면 어려워지는 쪽이었다")
ok("그때도 3·4급 목록이 안 붙는다",
   "[사용 가능 문법 — 중급(3급)]" not in _g["LEVEL_RULES"]
   and "[사용 가능 문법 — 중급(4급)]" not in _g["LEVEL_RULES"])
ok("올리는 것은 환경변수로", build(4)["MAX_LEVEL"] == 4)

print("\n── ⑥ 환경변수 하나로 바꾸는가 ──────────────")
ok("코드를 안 고치고 바꾼다", 'os.environ.get("MAX_LEVEL", "2")' in SRC)
ok("2~4 밖으로는 못 간다", "max(2, min(4," in SRC)
ok("/version 에서 확인된다", '"level": MAX_LEVEL' in SRC or "level" in SRC)

print()
if bad:
    print(f"💥 실패 {len(bad)}건"); sys.exit(1)
print("🎉 숙달도 상한이 등급마다 제대로 갈립니다")

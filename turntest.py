# -*- coding: utf-8 -*-
"""turntest.py — 한 턴 길이의 눈금이 **하나뿐인지** 잰다 (v162)

왜 이 검사가 있나
-----------------
v161에서 MAX_LEVEL 을 2로 내렸는데도 호아랑의 말이 안 짧아졌다.
어휘·문법 눈금만 등급을 따랐고, **길이 눈금은 네 곳에 흩어져 있었다.**

    BASE_PERSONA「발화 스타일(공통)」  2~3문장
    감정 지침                          1~2문장
    상황극 진행 규칙                   1~2문장
    LEVEL_RULES(초급)                  한 문장

지시가 여럿이면 큰 쪽이 이긴다. 「공통」이라 적힌 2~3문장이 늘 이겼다.

★ 그래서 이 검사는 **개수나 글자를 대조하지 않는다.**
  「같은 것을 두 곳에서 재고 있지 않은가」라는 **성질**을 잰다.
  길이 문구를 다시 다듬어도 이 검사는 안 깨지고,
  숫자가 다른 자리에 되살아나면 반드시 깨진다.

돌리는 법:  python turntest.py
"""
import io
import os as _os
import re
import sys

HERE = _os.path.dirname(_os.path.abspath(__file__))
SRC = io.open(_os.path.join(HERE, "main.py"), encoding="utf-8").read()

ok = fail = 0


def T(name, cond, msg=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}" + (f"  — {msg}" if msg else ""))


# ────────────────────────────────────────────────────────────
# 등급 셋을 실제로 지어 본다.
# BASE_PERSONA 부터 자리표를 갈아 끼우는 줄까지를 통째로 떼어 실행한다.
# (leveltest.py 는 등급 블록만 떼지만, 길이 눈금은 BASE_PERSONA 에 꽂히므로
#  여기서는 더 넓게 떼어야 조립된 결과를 볼 수 있다.)
# ────────────────────────────────────────────────────────────
_beg = SRC.index('BASE_PERSONA = """')
_end = SRC.index('BASE_PERSONA = BASE_PERSONA.replace("{한턴길이}", TURN_LEN_RULE)')
_end = SRC.index("\n", _end) + 1
SEG = SRC[_beg:_end]


def build(lv):
    """MAX_LEVEL 을 lv 로 두고 프롬프트 조각을 실제로 짓는다."""
    if lv is None:
        _os.environ.pop("MAX_LEVEL", None)
    else:
        _os.environ["MAX_LEVEL"] = str(lv)
    g = {"os": _os}
    exec(SEG, g)
    g["_ALL"] = g["BASE_PERSONA"] + g["LEVEL_RULES"] + g["SPOKEN_RULES"]
    return g


_saved = _os.environ.get("MAX_LEVEL")
try:
    B = {lv: build(lv) for lv in (2, 3, 4)}
    B[None] = build(None)          # 환경변수를 지운 상태
finally:
    if _saved is None:
        _os.environ.pop("MAX_LEVEL", None)
    else:
        _os.environ["MAX_LEVEL"] = _saved

print("\n[0] main.py 가 컴파일되는가")
#   ★ 이 검사가 없어서 v162 작업 중 f-string 안 역슬래시로 파일이 통째로
#     안 열리는 상태가 될 뻔했다. node --check 도 부분 exec 도 이걸 못 잡는다.
try:
    compile(SRC, "main.py", "exec")
    T("main.py 전체가 컴파일된다", True)
except SyntaxError as e:
    T("main.py 전체가 컴파일된다", False, f"{e.lineno}줄: {e.msg}")

print("\n[1] 자리표가 남아 있지 않은가")
for lv, g in B.items():
    T(f"lv={lv}: 「{{한턴길이}}」 자리표가 갈아 끼워졌다",
      "{한턴길이}" not in g["_ALL"],
      "자리표가 그대로 프롬프트에 나간다 — 모델이 중괄호를 읽는다")

print("\n[2] 눈금이 하나인가 — 정의는 딱 한 번만 나온다")
HEAD = "[한 턴 길이] — 음성 대화다."
for lv, g in B.items():
    n = g["_ALL"].count(HEAD)
    T(f"lv={lv}: 길이 규칙의 정의가 {n}번 (1이어야 한다)", n == 1,
      "두 번 이상이면 같은 것을 두 곳에서 재고 있다")

print("\n[3] 옛 눈금이 되살아나지 않았는가")
#   숫자로 된 턴 길이는 정의 블록 **안에서만** 허용된다.
NUM = re.compile(r"[0-9]\s*~\s*[0-9]\s*문장|한 턴에\s*[0-9]")
for lv, g in B.items():
    body = g["_ALL"]
    # 정의 블록을 도려내고 남은 자리에 숫자가 있는지 본다
    i = body.find(HEAD)
    rest = body[:i] + body[body.find("\n\n", i):] if i >= 0 else body
    hits = NUM.findall(rest)
    T(f"lv={lv}: 정의 밖에 숫자 눈금이 없다", not hits, f"찾음: {hits}")

print("\n[4] 등급이 길이를 실제로 가르는가")
T("2급의 길이 규칙과 3급의 길이 규칙이 다르다",
  B[2]["TURN_LEN_RULE"] != B[3]["TURN_LEN_RULE"])
T("2급 규칙이 3급 규칙보다 길다(초급일수록 더 못 박는다)",
  len(B[2]["TURN_LEN_RULE"]) > len(B[3]["TURN_LEN_RULE"]),
  f"2급 {len(B[2]['TURN_LEN_RULE'])}자 / 3급 {len(B[3]['TURN_LEN_RULE'])}자")
T("3급과 4급의 길이 규칙은 같다(길이는 3급에서 이미 상한)",
  B[3]["TURN_LEN_RULE"] == B[4]["TURN_LEN_RULE"])

print("\n[5] 2급일 때 실제로 짧아지는가")
r2 = B[2]["TURN_LEN_RULE"]
T("2급: 「한 문장」을 못 박는다", "한 문장" in r2)
T("2급: 물음 하나는 허용한다(차례를 넘길 도구)", "물음" in r2)
T("2급: 좋은 보기와 나쁜 보기를 같이 준다", "(○)" in r2 and "(✕)" in r2)
T("2급: 「2~3문장」이 프롬프트 어디에도 없다", "2~3문장" not in B[2]["_ALL"])
T("3급: 「2~3문장」이 있다", "2~3문장" in B[3]["_ALL"])
T("2급: LV_TURN 이 한 문장 쪽이다", "한 문장" in B[2]["LV_TURN"])
T("3급: LV_TURN 이 2~3문장 쪽이다", "2~3문장" in B[3]["LV_TURN"])

print("\n[6] 환경변수가 없어도 짧은 쪽인가")
T("MAX_LEVEL 을 안 두면 2급 길이 규칙", B[None]["TURN_LEN_RULE"] == B[2]["TURN_LEN_RULE"],
  "잊으면 쉬워지는 쪽이 기본이어야 한다")

print("\n[7] 다른 자리는 숫자 대신 이름으로 가리키는가 (원문 검사)")
#   감정 · 차례 관리 elicit · 상황극 진행 규칙 — 세 자리 모두 이름 참조여야 한다.
for label, needle in (
    ("감정 지침", "- 감정은 한 번에 하나. 길이는 [한 턴 길이] 그대로다."),
    ("차례 관리 elicit", "네가 [한 턴 길이]를 넘기면 실패다."),
    ("상황극 진행 규칙", "네 발화 길이는 [한 턴 길이] 그대로다."),
    ("LEVEL_RULES", "한 턴에 몇 문장인지는 [한 턴 길이]에서 정한다."),
):
    T(f"{label}: 숫자 대신 [한 턴 길이]로 가리킨다", needle in SRC)

T("상황극 첫 발화도 같은 눈금을 쓴다", "{LV_TURN}. 그보다 길게 말하지 마라." in SRC)
#   예외가 있다면 **선언되어 있어야** 한다. 말없이 어기는 자리가 있으면 그것이 새 눈금이다.
T("화계 교정만 예외로 선언돼 있다",
  "[한 턴 길이]의 **하나뿐인 예외**다" in SRC,
  "화계 교정 ①②③은 한 턴 길이를 넘는다 — 선언 없이 넘으면 눈금이 다시 둘이 된다")
T("초급이면 그 예외마저 두 마디로 줄인다",
  '①을 접고 ②③만 한 번에 붙여라' in SRC)

print("\n[8] main.py 전체에 떠도는 숫자 눈금이 없는가")
stray = []
for i, line in enumerate(SRC.split("\n"), 1):
    if 425 <= i <= 450:          # 눈금 정의와 그 주석은 예외
        continue
    if line.lstrip().startswith("#"):
        continue
    if NUM.search(line):
        stray.append((i, line.strip()[:70]))
T("정의 밖 어디에도 턴 길이 숫자가 없다", not stray, f"{stray}")

print("\n[9] 화계 교정 블록이 실제로 렌더되는가 (f-string 안이라 컴파일만으로는 부족하다)")
_i = SRC.index('    coord = f"""')
_j = SRC.index('\n    sep = """', _i)
COORD = "\n".join(l[4:] if l.startswith("    ") else l for l in SRC[_i:_j].split("\n"))


def render_coord(lv, mine="banmal", yours="banmal"):
    g = {"os": _os, "d": 75, "p": 50, "d_band": "친한", "p_band": "대등",
         "mine": mine, "yours": yours,
         "LV_KO": {"formal": "합쇼체", "polite": "해요체", "banmal": "해체(반말)"},
         "LV_SHORT": {"formal": "합쇼체", "polite": "해요체", "banmal": "해체(반말)"},
         "MAX_LEVEL": lv}
    exec(COORD, g)
    return g["coord"]


for lv in (2, 3, 4):
    try:
        txt = render_coord(lv)
        T(f"lv={lv}: 화계 블록이 렌더된다", True)
        T(f"lv={lv}: 예외 선언이 들어 있다", "하나뿐인 예외" in txt)
        T(f"lv={lv}: 초급 축약 줄은 2급에만", ("①을 접고" in txt) == (lv <= 2))
    except Exception as e:
        T(f"lv={lv}: 화계 블록이 렌더된다", False, f"{type(e).__name__}: {e}")

print("\n[10] 구어 꼬리말 — 등급 밖이면 **선언**돼 있는가")
#   지우는 것이 답이 아니었다. 「-거든」·「-잖아」는 입말에서 너무 흔해 남긴다.
#   다만 말없이 남기면 그것이 두 번째 눈금이다. 선언돼 있어야 예외다.
for lv, g in B.items():
    sp = g["SPOKEN_RULES"]
    low = (lv is None or lv <= 2)
    T(f"lv={lv}: 덩어리 표현 등급이 값과 맞다",
      ("초급 수준 안에서" in sp) == low,
      "「중급 수준 안에서」가 초급 상한에 그대로 남아 있으면 지시가 싸운다")
    if low:
        T(f"lv={lv}: 「-거든」·「-잖아」는 남아 있다", "-거든" in sp and "-잖아" in sp)
        T(f"lv={lv}: 목록 밖이라고 **선언**한다", "문법 목록(1·2급) **밖**이다" in sp)
        T(f"lv={lv}: 한 턴에 하나로 막는다", "한 턴에 하나까지만" in sp)
        T(f"lv={lv}: 나머지 3급 문형은 여전히 금지", "다른 3급 문형은 여전히 금지" in sp)
        T(f"lv={lv}: 「-더라고요」(4급)는 뺐다", "더라고요" not in sp)
    else:
        T(f"lv={lv}: 중급이면 「-더라고요」까지 쓴다", "더라고요" in sp)

print(f"\n{'=' * 52}\n  turntest — 통과 {ok} / 실패 {fail}\n{'=' * 52}")
sys.exit(1 if fail else 0)

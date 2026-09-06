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
NUM = re.compile(r"[0-9]\s*~\s*[0-9]\s*문장|한 턴에\s*[0-9]|[0-9]+\s*어절")
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

print("\n[5] 재는 자가 어절인가 — 문장 수로는 긴 문장을 못 막는다")
r2 = B[2]["TURN_LEN_RULE"]
T("2급: 문장 수가 아니라 어절로 잰다고 못 박는다", "문장 수가 아니라 어절 수" in r2)
T("2급: 한 문장 어절 상한이 7", B[2]["LV_W_SENT"] == 7)
T("2급: 한 턴 어절 상한이 15", B[2]["LV_W_TURN"] == 15)
T("3급: 상한이 더 넉넉하다",
  B[3]["LV_W_SENT"] > B[2]["LV_W_SENT"] and B[3]["LV_W_TURN"] > B[2]["LV_W_TURN"])
T("한 턴 상한이 한 문장 상한보다 크다(문장 둘 이상이 들어갈 자리)",
  all(g["LV_W_TURN"] > g["LV_W_SENT"] for g in B.values()))
T("2급: 문장 셋까지 허용한다(경험담을 말할 자리를 남긴다)", "**셋까지**" in r2)
T("2급: 왜 셋까지인지 까닭을 준다", "더 물어볼 거리" in r2)
T("2급: 물음은 맨 끝에 하나만", "맨 끝에 하나만" in r2)
T("2급: 셀 수 없을 때 쓸 대체 자를 준다(숨 한 번)", "숨 한 번에" in r2)
T("2급: 좋은 보기와 나쁜 보기를 같이 준다", "(○)" in r2 and "(✕)" in r2)
T("나쁜 보기는 **문장이 하나여도** 길다는 것을 보인다", "문장이 하나여도 이건 길다" in r2)
T("2급: LV_TURN 에 두 숫자가 다 들어 있다",
  "7어절" in B[2]["LV_TURN"] and "15어절" in B[2]["LV_TURN"])
T("옛 눈금 「2~3문장」이 프롬프트 어디에도 없다",
  all("2~3문장" not in g["_ALL"] for g in B.values()))

print("\n[5-b] ○ 보기가 스스로 상한을 지키는가 (보기가 규칙을 어기면 보기가 이긴다)")
import re as _re
_ok = _re.search(r'\(○\) "([^"]+)"', r2)
if _ok:
    _sents = [s for s in _re.split(r"(?<=[.!?])\s+", _ok.group(1)) if s.strip()]
    _w = [len(s.split()) for s in _sents]
    T(f"○ 보기의 문장별 어절 {_w} 이 모두 상한 이하", all(x <= B[2]["LV_W_SENT"] for x in _w))
    T(f"○ 보기의 턴 합 {sum(_w)}어절이 상한 이하", sum(_w) <= B[2]["LV_W_TURN"])
    T(f"○ 보기의 문장이 셋 이하 ({len(_sents)}문장)", len(_sents) <= 3)
else:
    T("○ 보기를 찾았다", False)

print("\n[6] 환경변수가 없어도 짧은 쪽인가")
T("MAX_LEVEL 을 안 두면 2급 길이 규칙", B[None]["TURN_LEN_RULE"] == B[2]["TURN_LEN_RULE"],
  "잊으면 쉬워지는 쪽이 기본이어야 한다")

print("\n[7] 다른 자리는 숫자 대신 이름으로 가리키는가 (원문 검사)")
#   감정 · 차례 관리 elicit · 상황극 진행 규칙 — 세 자리 모두 이름 참조여야 한다.
for label, needle in (
    ("감정 지침", "- 감정은 한 번에 하나. 길이는 [한 턴 길이] 그대로다."),
    ("차례 관리 elicit", "네가 [한 턴 길이]를 넘기면 실패다."),
    ("상황극 진행 규칙", "네 발화 길이는 [한 턴 길이] 그대로다."),
    ("LEVEL_RULES", "한 턴을 몇 어절로 할지는 [한 턴 길이]에서 정한다."),
):
    T(f"{label}: 숫자 대신 [한 턴 길이]로 가리킨다", needle in SRC)

T("상황극 첫 발화도 같은 눈금을 쓴다", "{LV_TURN}. 그보다 길게 말하지 마라." in SRC)
#   예외가 있다면 **선언되어 있어야** 한다. 말없이 어기는 자리가 있으면 그것이 새 눈금이다.
#   ★ v162 후반 — 어절로 재니 화계 교정이 예외일 까닭이 없어졌다.
#     세 마디를 짧게 하면 7어절이라 그냥 들어간다. **예외가 하나 줄었다.**
T("화계 교정에 예외를 두지 않는다", "**예외가 아니다**" in SRC)
T("옛 예외 선언이 남아 있지 않다", "하나뿐인 예외" not in SRC)
T("초급이면 그래도 더 줄일 수 있게 해 둔다", "①을 접고 ②③만 붙여도 된다" in SRC)

print("\n[8] main.py 전체에 떠도는 숫자 눈금이 없는가")
#   ★ 줄 번호로 예외를 두지 않는다 — 줄이 밀리면 검사가 거짓말을 한다.
#     지어 본 규칙 문자열 안에 있는 줄만 예외로 친다.
DEFN = "\n".join(g["TURN_LEN_RULE"] for g in B.values())
stray = []
for i, line in enumerate(SRC.split("\n"), 1):
    t = line.strip()
    if not t or t.startswith("#"):
        continue
    if not NUM.search(line):
        continue
    if t in DEFN or "LV_W_SENT" in line or "LV_W_TURN" in line:
        continue
    stray.append((i, t[:70]))
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
        T(f"lv={lv}: 화계 교정도 같은 눈금을 지킨다", "**예외가 아니다**" in txt)
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

print("\n[11] 한 판 시간 제한 (app.html)")
APP = io.open(_os.path.join(HERE, "app.html"), encoding="utf-8").read()
_m = re.search(r"const TALK_LIMIT_MS = (\d+) \* 60 \* 1000", APP)
T("TALK_LIMIT_MS 를 분 단위로 읽을 수 있다", bool(_m))
if _m:
    T(f"한 판이 15분이다 (지금 {_m.group(1)}분)", _m.group(1) == "15",
      "수업 시연이 10분에 끊겼다 — 15분이어야 한다")
_w = re.search(r"const TALK_WARN_MS = (\d+) \* 1000", APP)
T("1분 전 알림은 그대로", bool(_w) and _w.group(1) == "60")
T("남은 시간 안내가 총 시간을 글로 박지 않는다(「1분 남았어요」)",
  "1분 남았어요" in APP and "10분 남" not in APP)

print(f"\n{'=' * 52}\n  turntest — 통과 {ok} / 실패 {fail}\n{'=' * 52}")
sys.exit(1 if fail else 0)

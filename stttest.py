# -*- coding: utf-8 -*-
"""stttest.py — 전사에 섞여 오는 잡음 표식을 제대로 거르는지 본다 (v145)

★ 왜 따로 검사하나
  전사는 **조각으로 흘러온다.** `<noise>` 가 `<no` + `ise>` 로 쪼개져 오면
  조각마다 정규식을 걸어서는 영영 못 잡는다. 이 검사는 일부러 조각을 쪼개
  넣어 그 자리를 지킨다.

  main.py 를 통째로 import 하면 Gemini 클라이언트가 뜨므로,
  필요한 함수 덩어리만 떼어 내 돌린다.

    python3 stttest.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")


def load():
    """main.py 에서 STT 필터 덩어리만 떼어 낸다."""
    src = io.open(MAIN, encoding="utf-8").read()
    a = src.index("STT_UNHEARD =")
    b = src.index("def _stt_blank")
    b = src.index("\n\n", src.index("return not re.sub", b))
    ns = {"re": re}
    exec(src[a:b], ns)          # noqa: S102 — 우리 파일이다
    need = ["_stt_feed", "_stt_clean", "_stt_blank", "STT_UNHEARD"]
    miss = [n for n in need if n not in ns]
    if miss:
        raise SystemExit(f"✗ main.py 에서 {miss} 를 못 찾았습니다 — 이름이 바뀌었나요?")
    return ns


def main():
    ns = load()
    feed, clean, blank = ns["_stt_feed"], ns["_stt_clean"], ns["_stt_blank"]
    UN = ns["STT_UNHEARD"]

    def stream(frags):
        """흘러오는 조각을 실제와 같은 차례로 먹인다."""
        hold, out = "", ""
        for f in frags:
            s, hold = feed(hold, f)
            out += s
        return out + clean(hold)

    fails = []

    def ck(no, name, got, want=None, pred=None):
        ok = (pred(got) if pred else (got == want))
        print(f"  {'✅' if ok else '❌'} {no:<3} {name:<24} {got!r}")
        if not ok:
            fails.append(f"{no} {name} — 얻은 것 {got!r} / 바란 것 {want!r}")

    print("── 잡음 표식 거르기 ──────────────────────────────")

    ck("①", "한 조각에 통째로",
       stream(["안녕하세요 <noise> 반갑습니다"]),
       f"안녕하세요 {UN} 반갑습니다")

    ck("②", "★ 두 조각으로 쪼개짐",
       stream(["안녕 <no", "ise> 반가워"]),
       f"안녕 {UN} 반가워")

    ck("③", "★ 한 글자씩 쪼개짐",
       stream(list("네 <noise> 좋아요")),
       f"네 {UN} 좋아요")

    ck("④", "잇달아 붙은 것은 하나로",
       stream(["<noise><noise> 네"]).strip(),
       f"{UN} 네")

    ck("⑤", "대괄호 꼴",
       stream(["[inaudible] 감사합니다"]),
       f"{UN} 감사합니다")

    ck("⑥", "대문자여도",
       stream(["떡볶이 <INAUDIBLE> 주세요"]),
       f"떡볶이 {UN} 주세요")

    ck("⑦", "빈칸이 끼어도",
       stream(["< noise > 네"]).strip(),
       f"{UN} 네")

    print("\n── 안 건드려야 하는 것 ───────────────────────────")

    ck("⑧", "진짜 부등호는 살린다",
       stream(["3 < 5 입니다"]),
       "3 < 5 입니다")

    ck("⑨", "괄호 안 우리말은 살린다",
       stream(["가격은 (삼천 원) 입니다"]),
       "가격은 (삼천 원) 입니다")

    ck("⑩", "표식이 없으면 그대로",
       stream(["안녕하세요 반갑습니다"]),
       "안녕하세요 반갑습니다")

    print("\n── 「말한 것이 없다」 가려내기 ────────────────────")

    ck("⑪", "표식뿐이면 빈 발화", blank(UN), True)
    ck("⑫", "표식+문장부호도 빈 발화", blank(f"{UN} ... {UN}"), True)
    ck("⑬", "한 글자라도 있으면 아님", blank(f"{UN} 네"), False)
    ck("⑭", "보통 말은 아님", blank("안녕하세요"), False)

    print("\n── 붙들어 둔 꼬리 ────────────────────────────────")

    # 표식이 될 뻔했지만 끝내 안 닫힌 토막은 흘려보내야 한다
    ck("⑮", "안 닫힌 꼬리도 잃지 않는다",
       stream(["값은 <"]), "값은 <")

    hold_out, hold = ns["_stt_feed"]("", "안녕 <no")
    ck("⑯", "붙들 것은 붙든다",
       (hold_out, hold), ("안녕 ", "<no"))

    print()
    if fails:
        print(f"❌ {len(fails)}개 틀림")
        for f in fails:
            print("   ·", f)
        sys.exit(1)
    print("✅ 16개 모두 통과 — 잡음 표식은 「(안 들림)」으로 바뀝니다")


if __name__ == "__main__":
    main()

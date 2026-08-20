# -*- coding: utf-8 -*-
"""대화문 묶음 자체 검사 — 선생님께 드리기 전에 한 번 더 본다."""
import json, io, re, sys
from collections import Counter
SRC = sys.argv[1] if len(sys.argv) > 1 else "corpus/repair.json"
MAIN = sys.argv[2] if len(sys.argv) > 2 else "main.py"
s = io.open(MAIN, encoding="utf-8").read()
ns = {"re": re}
exec(re.search(r"_ONE_WORD = .*?\n(?=\n)", s, re.S).group(0), ns)
exec(re.search(r"def _speech_level\(.*?\n(?=\n\n)", s, re.S).group(0), ns)
lv = ns["_speech_level"]
d = json.load(io.open(SRC, encoding="utf-8"))
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else "   " + str(x)))
    if not c: bad.append(m)

print(f"══ {d['acad']} · {len(d['items'])}편 ══")
print("\n── ① 표시할 줄은 학습자 발화")
for it in d["items"]:
    ok(f"{it['id']}", it["script"][it["mark"]]["speaker"] == "user")

print("\n── ② 존대↔반말이 섞이지 않았나")
# ★ 합쇼체↔해요체는 실제 입말에서 늘 섞인다(「감사합니다」). 존대 안에서의 넘나듦은 잘못이 아니다.
#   잘못은 **존대 대화에 반말이 섞이는 것**이다 — 배우는 사람이 그대로 따라 한다.
# ★★ 화자마다 따로 잰다 (맥락·정체성 묶음에서 드러난 것).
#   예전에는 대화문 **전체**를 한 화계로 재고 있었다. 그러면
#   「나는 존댓말, 선생님은 반말」 같은 **비대칭 대화가 아예 못 들어온다.**
#   그런데 비대칭이야말로 한국어 학습자가 가장 어려워하는 자리이고,
#   〈표 4-x〉가 「가장 어려워하는 지점」이라고 못 박은 곳이다.
#   검사가 가르쳐야 할 것을 막고 있었던 셈이다.
#   → tier 는 **학습자**의 화계, partner_tier 는 **상대**의 화계.
#     partner_tier 를 안 적으면 예전처럼 둘이 같은 것으로 본다(기존 30편 그대로).
for it in d["items"]:
    want = {"user": it["tier"] == "banmal",
            "ai":   it.get("partner_tier", it["tier"]) == "banmal"}
    wrong = [f"{l['speaker']}: {l['text']}" for l in it["script"]
             if lv(l["text"]) and (lv(l["text"]) == "banmal") != want[l["speaker"]]]
    tag = it["tier"] + ("/" + it["partner_tier"] if it.get("partner_tier") else "")
    ok(f"{it['id']} {tag}", not wrong, wrong[:1])

# ★ v136 — 「기능 단계의 조직」 묶음만 물음이 다르다.
#   한 발화를 보는 것이 아니라 **대화 한 판의 흐름**을 보므로,
#   세 갈래 고르기가 아니라 **차례 맞히기**다(조각을 순서대로 쌓는다).
#   검사가 한 가지 꼴만 알면 새 꼴이 들어올 때 통째로 막는다 — ②에서 겪었다.
def _is_order(it): return it.get("quiz_type") == "order"
_pick = [x for x in d["items"] if not _is_order(x)]
_ord = [x for x in d["items"] if _is_order(x)]

print("\n── ③ 세 갈래 물음" + (f" (차례 맞히기 {len(_ord)}편은 ③-2 에서)" if _ord else ""))
for it in _pick:
    q = it["quiz"]; c = [q["right"], q["wrong1"], q["wrong2"]]
    ok(f"{it['id']} 셋이 서로 다르다", len(set(c)) == 3)
    ok(f"{it['id']} 오답이 엉뚱하지 않다", all(abs(len(x) - len(q["right"])) < 22 for x in c[1:]),
       [len(x) for x in c])

if _ord:
    print("\n── ③-2 차례 맞히기")
    for it in _ord:
        st = it.get("stages") or []
        ok(f"{it['id']} 단계가 3~6개", 3 <= len(st) <= 6, len(st))
        ok(f"{it['id']} 단계 이름이 서로 다르다", len({x["name"] for x in st}) == len(st))
        ats = [x["at"] for x in st]
        ok(f"{it['id']} 첫 단계가 첫 줄에서 시작", ats[:1] == [0], ats[:1])
        ok(f"{it['id']} 줄 번호가 오름차순", ats == sorted(ats) and len(set(ats)) == len(ats), ats)
        ok(f"{it['id']} 줄 번호가 대화문 안에 있다", all(0 <= a < len(it["script"]) for a in ats), ats)
        # 차례를 맞히려면 처음과 끝이 다 보여야 한다 — 그래서 이 묶음만 길다
        ok(f"{it['id']} 8줄 이상 (처음과 끝이 다 보이게)", len(it["script"]) >= 8, len(it["script"]))
        ok(f"{it['id']} 마지막 단계가 뒤쪽에 있다", ats[-1] >= len(it["script"]) - 3, (ats[-1], len(it["script"])))
        ok(f"{it['id']} 물음·힌트가 있다", bool(it["quiz"].get("q")) and bool(it["quiz"].get("hint")))
        ok(f"{it['id']} 세 갈래 열쇠는 없다", not any(k in it["quiz"] for k in ("right", "wrong1", "wrong2")))

print("\n── ④ 연습거리 둘 · 앞말 · 이어짐")
for it in d["items"]:
    ok(f"{it['id']}", len(it["drills"]) == 2 and all(x["cue"] and x["text"] for x in it["drills"]))
    a, b = it["drills"][0]["text"], it["script"][it["mark"]]["text"]
    ok(f"{it['id']} 첫 연습이 표시한 줄에서 이어진다", a[:8] in b or b[:8] in a, f"{a[:18]} / {b[:18]}")

print("\n── ⑤ 뜻풀이 셋 · 문형 2~4")
for it in d["items"]:
    ok(f"{it['id']}", len(it["meaning"]) == 3 and 2 <= len(it["forms"]) <= 4)

print("\n── ⑥ 화계가 다섯 편에 흩어졌나")
c = Counter(x["tier"] for x in d["items"])
ok(f"세 화계가 다 나온다 {dict(c)}", len(c) == 3)

print("\n── ⑦ 입말 티 (담화표지·조각문)")
# ★ 말끝이 아니라 **말머리·군말**을 센다. 앞의 목록이 좁아서
#   「아… 네」「어… 그…」「저기요」 같은 뚜렷한 입말을 못 잡고 있었다.
M = ("아,", "아…", "아!", "어,", "어…", "어!", "음", "그…", "그럼", "저기요", "저,",
     "네?", "네,", "네…", "우와", "오,", "오!", "헐", "야,", "글쎄", "진짜", "맞아", "응", "거봐", "그러니까",
     "에이", "아이고", "아유", "어머", "아하", "참,",
     "잠깐", "잠시만", "뭐라고", "있잖아", "어서")
for it in d["items"]:
    n = sum(1 for l in it["script"] if any(m in l["text"] for m in M))
    ok(f"{it['id']} {n}/{len(it['script'])}줄", n >= 3, n)

print("\n── ⑧ 〈표 33〉 세부 요소를 다 덮었나")
# ★ 다섯 편이 모두 달라야 하는 것이 아니다. 세부 요소는 넷이므로 하나는 겹친다.
#   재야 할 것은 ㄱ) 넷을 다 덮었는가 ㄴ) 겹친 편이 **자리와 화계가 다른가** 이다.
#   같은 자리·같은 화계로 두 번 하면 그건 사례가 둘이 아니라 하나다.
# ★ 차례 맞히기 묶음은 sub 가 **대화 유형 이름**(구매 대화·전화 상담…)이다.
#   세부 요소(시작·전개·마무리)는 편마다가 아니라 **단계 목록 안에** 들어 있다.
#   〈표 33〉을 덮었는지도 거기서 봐야 한다.
if _ord:
    _all = [st["acad"] for x in _ord for st in (x.get("stages") or [])]
    subs = []
    if any("시작" in a or "안내" in a or "구체화" in a or "문제규정" in a for a in _all): subs.append("시작")
    if any(a not in ("시작 단계", "마무리 단계") for a in _all): subs.append("전개")
    if any("마무리" in a or "합의" in a or "검토" in a or "예고" in a for a in _all): subs.append("마무리")
else:
    subs = [x["sub"].split(" (")[0] for x in d["items"]]
need = d.get("subs_t33") or []
ok(f"표 33 의 세부 요소를 다 덮었다 {need}", all(n in subs for n in need),
   [n for n in need if n not in subs])
from collections import defaultdict
dup = defaultdict(list)
for x in _pick: dup[x["sub"].split(" (")[0]].append(x)
if _ord:
    ok(f"대화 유형이 서로 다르다", len({x["sub"] for x in _ord}) == len(_ord),
       [x["sub"] for x in _ord])
for k, v in dup.items():
    if len(v) < 2: continue
    ok(f"겹친 「{k}」 {len(v)}편은 자리가 다르다", len({x["place"] for x in v}) == len(v))
    ok(f"겹친 「{k}」 {len(v)}편은 화계가 다르다", len({x["tier"] for x in v}) == len(v),
       [x["tier"] for x in v])

print("\n── ⑨ 주제가 2·3급 안에 있는가 〈표12 최종 주제 등급화〉")
# ★★ 중급 학습자에게 친숙한 주제는 **2·3급에서 이미 배운 것**이다.
#   학교 상담의 비자·근로시간, 주민센터의 전입신고·등본 같은 행정 주제는
#   어느 급에도 없다. 요소를 가르치려다 낯선 주제로 학습자를 막으면 안 된다.
# ★ lv23.json 은 대화문 파일 **옆에** 있다. 예전에는 "corpus/lv23.json" 으로
#   박아 두어, 폴더를 옮기면 검사가 통째로 죽었다.
import os
LV23 = json.load(io.open(os.path.join(os.path.dirname(os.path.abspath(SRC)) or ".", "lv23.json"),
                         encoding="utf-8"))
for it in d["items"]:
    tag = it.get("topic_lv", "")
    ok(f"{it['id']} 급·주제 딱지가 있다", bool(tag), tag)
    if not tag: continue
    ok(f"{it['id']} 〈표12〉 범주다 · {tag}",
       any(k in tag for k in LV23), tag)
    ok(f"{it['id']} 2급 또는 3급", ("2급" in tag or "3급" in tag), tag)

print("\n── ⑩ 대화 길이·마디 길이")
for it in d["items"]:
    _lo = 8 if _is_order(it) else 6      # 차례를 맞히려면 처음과 끝이 다 보여야 한다
    ok(f"{it['id']} {_lo}~10줄", _lo <= len(it["script"]) <= 10, len(it["script"]))
    lg = [l["text"] for l in it["script"] if len(l["text"]) > 60]
    ok(f"{it['id']} 한 마디가 너무 길지 않다", not lg, lg[:1])

print("\n── ⑪ 물음·뜻풀이에 반대쪽 화계가 섞이지 않았나")
# ★ 처음에 「마지막 어미가 편의 화계와 같은가」로 쟀더니 24건이 쏟아졌다. 과잉이었다.
#   ②에 이미 답이 있었다 — **합쇼체↔해요체는 실제 입말에서 늘 섞인다.**
#   뜻풀이도 같은 잣대로 봐야 한다. 잘못은 넘나듦이 아니라 **반대쪽으로 넘어가는 것**이다.
#     · 반말 편의 설명에 존댓말이 섞이면 잘못 (반말 대화를 읽다 설명만 존댓말)
#     · 존대 편의 설명에 반말이 섞이면 잘못
#   같은 원칙을 두 곳에서 다르게 재면, 검사가 스스로 어긋난다.
def _mixed(text, want_ban):
    for one in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        g = lv(one)
        if g and (g == "banmal") != want_ban:
            return one
    return ""
for it in d["items"]:
    wb = it["tier"] == "banmal"
    lines = [it["quiz"].get(k, "") for k in ("q", "right", "wrong1", "wrong2", "hint")] \
            + list(it["meaning"])
    off = [x for x in (_mixed(l, wb) for l in lines) if x]
    ok(f"{it['id']} {it['tier']}", not off, off[:1])

print("\n── ⑫-2 화면에 그대로 뜰 것이 섞이지 않았나")
# ★ 굵게 쓰려고 **별표**를 넣었는데, 화면은 그냥 별표 두 개로 보여 준다.
#   글이 강조되는 게 아니라 **어수선해지고, 무엇보다 AI 가 쓴 티가 난다.**
#   (선생님이 직접 걷어내셨다 — 같은 일이 다시 생기지 않게 검사로 못 박는다)
for it in d["items"]:
    F = [it["quiz"].get(k, "") for k in ("q", "right", "wrong1", "wrong2", "hint")]
    F += list(it["meaning"]) + [st.get("name", "") for st in (it.get("stages") or [])]
    star = [t for t in F if "**" in t or "__" in t]
    ok(f"{it['id']} 별표·밑줄 표시가 없다", not star, (star[:1] or [""])[0][:40])

print("\n── ⑬-0 설명하는 말이 3급 초입 수준인가")
# ★★ 대상은 **초급을 막 마치고 3급에 들어온 학습자**다.
#   「북돋우다」「비꼬다」「얹다」는 모어 화자에게는 쉬워도 그들에게는 처음 보는 말이다.
#   요소를 가르치려다 **설명에서 막히면** 아무것도 안 남는다.
#   ※ 대화문·문형·연습은 안 본다 — 그건 배울 거리 자체이고, 쉽게 바꾸면 가르칠 것이 사라진다.
#     여기서 재는 것은 **설명하는 말**(물음·선택지·힌트·뜻풀이)뿐이다.
TOO_HARD = ("북돋", "비꼬", "얹어", "얹고", "낱말", "되짚", "멈칫", "김이 빠", "애매",
            "물러서", "자리를 뜨", "한마디", "돌려 말", "서운", "감탄", "촉구", "유도",
            "실현", "위계", "무안", "머쓱", "선뜻", "얼버무", "넌지시", "에둘러",
            "짐작", "가늠", "빌미", "구실", "반문", "환기", "부각")
for it in d["items"]:
    q = it["quiz"]
    lines = [q.get(k, "") for k in ("q", "right", "wrong1", "wrong2", "hint")] + list(it["meaning"])
    hit = sorted({w for w in TOO_HARD for l in lines if w in l})
    ok(f"{it['id']} 어려운 말이 없다", not hit, hit)

print("\n── ⑬ 정답이 눈에 띄게 길지 않은가")
# ★★ 안 읽고 **가장 긴 것**을 고르면 맞는 문항은 문항이 아니다.
#   ③의 기준(22자)이 너무 헐렁해서 못 잡고 있었다.
#   길이는 내용이 아니다 — 정답에만 이유를 다 적어 넣으면 길이가 답을 새게 한다.
#   이유는 ③추측이 아니라 ③뜻풀이에서 말하면 된다.
for it in _pick:      # 차례 맞히기 편은 선택지가 없다
    q = it["quiz"]; L = [len(q["right"]), len(q["wrong1"]), len(q["wrong2"])]
    lead = L[0] - max(L[1], L[2])
    ok(f"{it['id']} 정답이 8자 넘게 길지 않다 {L}", lead < 8, f"+{lead}자")
    # 반대도 마찬가지다 — 정답만 유난히 **짧아도** 눈에 띈다.
    short = min(L[1], L[2]) - L[0]
    ok(f"{it['id']} 정답이 10자 넘게 짧지도 않다", short < 10, f"-{short}자")

print("\n── ⑫ 표시한 줄이 그 편에서 유일하게 또렷한가")
# ★ 표시 안 한 줄이 같은 일을 하고 있으면 「왜 저 줄만 표시했지?」가 된다.
#   문형 목록에 있는 말이 학습자의 **다른** 줄에도 통째로 들어 있으면 알린다.
# ★ 차례 맞히기 편은 **표시한 줄이 요점이 아니라 흐름 전체**가 요점이다.
#   문형이 여러 줄에 나오는 것이 오히려 자연스럽다(단계 표지니까).
for it in _pick:
    mk = it["script"][it["mark"]]["text"]
    others = [l["text"] for i, l in enumerate(it["script"])
              if l["speaker"] == "user" and i != it["mark"]]
    dup = [o for o in others for f in it["forms"]
           if len(f) >= 4 and f.rstrip("?~ ") in o]
    ok(f"{it['id']} 표시 줄만 그 문형을 쓴다", not dup, dup[:1])

print("\n── ⑭ 문형이 대화문의 말로 채워졌는가")
# ★ 「나도 ~한 적 있어」만 보이면 3급 초입 학습자는 무엇을 넣을지 모른다.
#   그래서 편마다 그 대화문의 말로 **채운 꼴**을 함께 담는다 (forms_filled, v138).
#     붉은색 = 그대로 외울 뼈대   ·   검은색 = 갈아 끼우는 자리
#   조각을 이어 붙이면 학습자가 화면에서 보는 한 줄이 된다.
for it in d["items"]:
    fs, ff = it.get("forms") or [], it.get("forms_filled") or []
    ok(f"{it['id']} 채운 꼴의 수가 문형 수와 같다 {len(ff)}/{len(fs)}", len(ff) == len(fs))
    for i, x in enumerate(fs):
        if i >= len(ff): break
        parts = ff[i]
        joined = "".join(t for t, _ in parts)
        ok(f"{it['id']} 「{x}」에 ~ 가 안 남았다", "~" not in joined, joined)
        if "~" in x:
            # 「~」가 있던 자리는 반드시 **검은 칸**으로 채워져 있어야 한다
            ok(f"{it['id']} 「{x}」에 갈아 끼우는 칸이 있다",
               any(c == 0 for _, c in parts), joined)
        # 뼈대가 하나도 없으면 무엇을 외울지가 안 보인다
        ok(f"{it['id']} 「{x}」에 외울 뼈대가 있다", any(c == 1 for _, c in parts), joined)
        # 조각을 자모로 쪼개면 화면에서 「기다리ㄹ게」처럼 깨져 보인다
        ok(f"{it['id']} 「{x}」가 음절 가운데서 안 잘렸다",
           not any(("\u1100" <= t[0] <= "\u11FF" or "\u3131" <= t[0] <= "\u318E")
                   for t, _ in parts if t), joined)

print("\n" + (f"💥 {len(bad)}건" if bad else "🎉 이상 없음"))
sys.exit(1 if bad else 0)

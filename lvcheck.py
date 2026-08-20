# -*- coding: utf-8 -*-
"""lvcheck.py — 학습자가 보는 글이 1~3급 어휘·문법 안에 있는가

대상은 **2급을 수료하고 3급에 들어온 학습자**다. 최대 3급까지.
기준은 〈2017 국제 통용 한국어 표준 교육과정(4단계)〉 어휘·문법 등급 목록.

형태소 분석기 없이 **어간을 벗겨** 목록과 맞춘다.
못 맞춘 것은 「모름」으로 따로 모아 사람이 본다 — 기계가 4급이라고
단정하면 멀쩡한 말도 잡는다. 판단은 사람이 한다.
"""
import json, io, glob, re, sys
from collections import Counter, defaultdict

LV = json.load(io.open("lv13.json", encoding="utf-8"))
VOC, POS = LV["vocab"], LV["pos"]
MAX = int(sys.argv[1]) if len(sys.argv) > 1 else 3

# 활용 어미를 벗겨 어간 후보를 만든다
TAIL = ["으셨습니다","었습니다","았습니다","겠습니다","습니다","ㅂ니다","십시오",
        "으세요","이에요","예요","했어요","해요","어요","아요","네요","군요","지요","죠",
        "으려고","려고","으면서","면서","으니까","니까","아서","어서","여서",
        "겠어","았어","었어","했어","이야","이지","잖아","거든","구나","는데","은데","ㄴ데",
        "으로","에서","에게","한테","까지","부터","보다","처럼","마다","밖에",
        "들","은","는","이","가","을","를","에","도","만","의","와","과","고","며",
        "하다","되다","하는","하고","해서","한","할","함","해","했","하","되","된","될"]
# -(으)ㄹ 이 앞말에 받침 ㄹ 을 남기는 어미들
L_TAIL = ["게요", "게", "까요", "까", "래요", "래", "걸요", "걸", "텐데",
          "수가", "수는", "수도", "지도", "지언정", "뿐", "테니까", "테니"]

def unl(w):
    """「볼」처럼 **-(으)ㄹ 이 붙어 생긴 받침 ㄹ** 을 떼어 어간을 되살린다 → 「보」

    ★ 왜 필요했나
      「가 볼게요」의 「볼게요」를 어미만 벗기면 「볼」이 남는다.
      그런데 목록의 「볼」은 **뺨(4급)** 이다. 그래서 1급 낱말 「보다」가
      4급으로 잡혔다. 「-(으)ㄹ게요」는 어미이지 낱말이 아니다.
      받침 ㄹ 을 떼면 「보」가 되고 「보다」를 찾을 수 있다.
    """
    if not w: return None
    ch = w[-1]
    if not ("가" <= ch <= "힣"): return None
    code = ord(ch) - 0xAC00
    if code % 28 != 8:                 # 받침이 ㄹ 이 아니면 건드리지 않는다
        return None
    return w[:-1] + chr(0xAC00 + code - 8)

def stems(w):
    out = {w}
    for t in TAIL:
        if w.endswith(t) and len(w) > len(t):
            s = w[:-len(t)]
            out.add(s); out.add(s + "다"); out.add(s + "하다")
    if len(w) > 1:
        for i in (1, 2):
            if len(w) > i: out.add(w[:-i] + "다"); out.add(w[:-i] + "하다"); out.add(w[:-i])
    # 받침 ㄹ 이 **-(으)ㄹ 어미에서 온 것**일 때만 떼어 본다.
    # ★ 아무 데나 떼면 「볼(뺨)」「출산」「솔직히」 같은 4급 낱말이 1~2급으로 새 버린다.
    #   (한 번 그렇게 해 봤더니 4급 22개를 놓쳤다 — 오탐 하나 잡으려다 스물둘을 흘린 셈이다)
    #   그래서 「-(으)ㄹ게/-(으)ㄹ까/-(으)ㄹ래…」가 실제로 붙은 자리에만 쓴다.
    for t in L_TAIL:
        if w.endswith(t) and len(w) > len(t):
            b = unl(w[:-len(t)])
            if b: out.add(b); out.add(b + "다")
    return out

def grade(w):
    """가장 **낮은** 등급을 고른다.

    ★ 어간을 벗기다 보면 「해서」가 「해서다(4급)」 같은 엉뚱한 것에 걸린다.
      한 낱말이 여러 어간으로 풀리면 **가장 쉬운 쪽**이 맞다고 본다 —
      학습자는 아는 쪽으로 읽지, 모르는 쪽으로 읽지 않는다.
      그리고 「하다/되다/있다/없다」 같은 기본 용언에서 나온 꼴은
      그 자체를 1급으로 본다(목록에 활용형이 다 실려 있지 않다)."""
    # ㉠ 불규칙 활용은 어간을 벗겨도 원형이 안 나온다.
    #    「몰라서」→「몰라」(모르다), 「골라」(고르다), 「부끄러워서」(부끄럽다).
    #    자주 쓰는 것만 손으로 짚어 둔다 — 이게 없으면 1급 낱말이 4급으로 잡힌다.
    IRREG = {"몰라":"모르다","몰랐":"모르다","골라":"고르다","골랐":"고르다",
             "달라":"다르다","다르":"다르다","부끄러워":"부끄럽다","부끄러웠":"부끄럽다",
             "어려워":"어렵다","쉬워":"쉽다","가까워":"가깝다","더워":"덥다","추워":"춥다",
             "들어":"듣다","물어":"묻다","걸어":"걷다","도와":"돕다","고와":"곱다",
             "몰랐어":"모르다","봬요":"뵈다","뵐":"뵈다"}
    for k, base in IRREG.items():
        if w.startswith(k):
            g = VOC.get(base)
            if g is not None: return g
    for base in ("하다", "되다", "있다", "없다", "이다", "말하다", "보다", "가다", "오다",
                 "모르다", "알다", "고르다", "부끄럽다", "듣다", "묻다", "주다", "받다",
                 "만들다", "쓰다", "놓다", "넣다", "찾다", "생각하다", "이야기하다"):
        core = base[:-1]
        if w.startswith(core) and len(w) <= len(core) + 4:
            return VOC.get(base, 1)
    best = None
    for s in stems(w):
        g = VOC.get(s)
        if g is not None and (best is None or g < best): best = g
    return best

# 이건 등급 목록에 없어도 학습자가 알아야 하는 말 (선생님 지시)
# 어미·조사가 낱말처럼 떨어져 나온 것 — 어휘가 아니므로 세지 않는다
ENDING = {"라고","해서","합니다","해요","했어요","했을까","했을까요","됩니다","할지",
          "있어요","있습니다","있어","있지","있죠","처럼","부터","인데","해도","해야",
          "하면","하고","하는","한다","해라","하지","이라고","이에요","예요","이야",
          "먼저","그때","그럼","그래서","그리고","그런데","하지만","이렇게","그렇게",
          "어떻게","무엇을","무슨","어디","언제","누구","왜"}
ALLOW = {"확인","단어","공손","존댓말","반말","대화","연습","표현","문장","단계",
         "상대","상대방","질문","대답","친구","선생님","호아랑","한국어","이야기"}

def scan(only_ids=None):
    unknown, over = Counter(), Counter()
    where = defaultdict(list)
    for f in sorted(glob.glob("*.json")):
        if f in ("lv13.json", "lv23.json"): continue
        for it in json.load(io.open(f, encoding="utf-8"))["items"]:
            q = it["quiz"]
            fields = [("물음", q.get("q","")), ("정답", q.get("right","")),
                      ("오답1", q.get("wrong1","")), ("오답2", q.get("wrong2","")),
                      ("힌트", q.get("hint",""))]
            fields += [(f"뜻{i+1}", m) for i, m in enumerate(it.get("meaning") or [])]
            for st in (it.get("stages") or []):
                fields.append(("단계", st.get("name", "")))
            for k, t in fields:
                t = re.sub(r"[「」*·…—\-\(\)\[\]~?!.,:;]", " ", t)
                for w in re.findall(r"[가-힣]+", t):
                    if w in ALLOW or len(w) < 2: continue
                    if w in ENDING: continue        # 어미·조사 조각
                    g = grade(w)
                    if g is None: unknown[w] += 1; where[w].append((it["id"], k))
                    elif g > MAX: over[w] += 1; where[w].append((it["id"], k))
    return unknown, over, where

# ── 문법 — 4급 이상 문형이 설명하는 말에 섞였는가 ──
GRAM = LV["gram"]
G4 = sorted([g for g, n in GRAM.items() if n > MAX and len(g) >= 3],
            key=len, reverse=True)
# 문형 글자가 그대로 들어 있지만 **그 문형이 아닌** 자리
FALSE = {
    "-는 한":   ("때는 한 ", "에는 한 ", "로는 한 ", "는 한 번", "는 한 개", "는 한 사람"),
    "-고 해서": ("려고 해서", "라고 해서", "다고 해서"),
}

def gram_scan():
    hit = defaultdict(list)
    for f in sorted(glob.glob("*.json")):
        if f in ("lv13.json", "lv23.json"): continue
        for it in json.load(io.open(f, encoding="utf-8"))["items"]:
            q = it["quiz"]
            F = [("물음", q.get("q","")), ("정답", q.get("right","")),
                 ("오답1", q.get("wrong1","")), ("오답2", q.get("wrong2","")),
                 ("힌트", q.get("hint",""))]
            F += [(f"뜻{i+1}", m) for i, m in enumerate(it.get("meaning") or [])]
            for st in (it.get("stages") or []): F.append(("단계", st.get("name","")))
            for k, t in F:
                tt = t.replace("~", "").replace("-", "")
                for g in G4:
                    gg = g.replace("-", "").replace("(으)", "").replace("으", "")
                    if len(gg) < 3 or gg not in tt: continue
                    # ★★ 짧은 문형은 **딴 말 속에 그대로 들어 있다.**
                    #   글자만 찾으면 검사가 거짓말을 한다 —
                    #     「-는 한」  ← 「때는 한 번」의 「한」(관형사)
                    #     「-고 해서」 ← 「-려고 해서」(-려고 하다 + -아서)
                    #   앞뒤를 함께 보고 거른다. 실제로 걸린 것만 짚어 둔다.
                    j = tt.index(gg)
                    around = tt[max(0, j - 3): j + len(gg) + 2]
                    if any(x in around for x in FALSE.get(g, ())): continue
                    nxt = tt[j + len(gg): j + len(gg) + 1]
                    if gg.endswith(" 한") and nxt and nxt != " ": continue
                    hit[g].append((it["id"], k, t[:56]))
    return hit

unk, over, where = scan()
print(f"══ 기준 {MAX}급 이하 · 〈2017 국제 통용 한국어 표준 교육과정〉 ══\n")
print(f"── ① {MAX}급을 넘는 것으로 확인된 말: {len(over)}개")
for w, n in over.most_common():
    i, k = where[w][0]
    print(f"   {w:<10} {VOC.get(w) or grade(w)}급 · {n}군데   ({i} {k})")
gh = gram_scan()
print(f"\n── ①-2 {MAX}급을 넘는 문형: {len(gh)}개")
if not gh: print("   ✅ 없음")
for g, v in sorted(gh.items(), key=lambda x: -len(x[1])):
    print(f"   {g:<16} {GRAM[g]}급 · {len(v)}군데")
    for i, k, t in v[:2]: print(f"       {i} {k}  {t}")

print(f"\n── ② 목록에서 못 찾은 말: {len(unk)}개 (사람이 봐야 함)")
for w, n in unk.most_common(60):
    i, k = where[w][0]
    print(f"   {w:<12} {n}군데   ({i} {k})")

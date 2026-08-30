# -*- coding: utf-8 -*-
"""orgnametest — 소속이 드라이브까지 닿는가 (v153)

★ 왜 이 검사가 있나
  파일 이름을 「어떻게 지을지」는 main.py 안쪽에 묻혀 있어서
  눈으로는 못 본다. 실제 학습자 이름·기관·반을 넣어 **문자열을 만들어 본다.**
  이름으로 정렬해야 KIIP·언어교육원·연세대가 폴더에서 갈린다.
"""
import io, re, sys
s = io.open("main.py", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else "   " + str(x)))
    if not c: bad.append(m)

# main.py 에서 이름 짓는 대목만 떼어 그대로 돌린다 — 베껴 쓰면 두 벌이 된다
seg = re.search(r'_org = \(\{"kiip".*?_D\{d\}_P\{p\}"\)', s, re.S)
ok("이름 짓는 대목을 찾았다", seg is not None)
if not seg: sys.exit(1)
code = re.sub(r"^\s{8}", "", seg.group(0), flags=re.M)

def _clean_str(v, n):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]

def name_of(org="", orgName="", orgClass="", kind="주제",
            ts="20260830_080224", safe_name="Purna", d=74, p=50):
    g = {"_clean_str": _clean_str, "re": re, "org": org, "orgName": orgName,
         "orgClass": orgClass, "kind": kind, "ts": ts,
         "safe_name": safe_name, "d": d, "p": p}
    exec(code, g)
    return g["base"]

print("── 소속이 이름에 들어가는가 ─────────────────")
n1 = name_of("kiip", "KIIP 사회통합프로그램", "2반")   # 반은 이제 화면이 안 보내지만, 와도 안 깨져야 한다
print("     " + n1)
ok("기관이 들어간다", "KIIP" in n1)
ok("긴 이름 대신 짧은 표를 쓴다", "사회통합" not in n1,
   "「KIIP사회통합프로그램(3단계」처럼 괄호가 잘려 반 이름과 엉겼다")
ok("KIIP 과 언어교육원이 갈린다",
   name_of("kiip", "", "").split("_")[2] != name_of("cau", "", "").split("_")[2],
   "둘 다 중앙대라 「중앙대」로 적으면 폴더에서 또 엉킨다")
ok("반이 들어간다", "2반" in n1)
ok("갈래가 앞에 온다", n1.startswith("호아랑대화_주제_"))
ok("소속이 날짜 앞에 온다", n1.index("KIIP") < n1.index("20260830"))
ok("이름과 D·P 는 그대로", n1.endswith("_Purna_D74_P50"))

print("\n── 안 골랐어도 이름이 깨지지 않는가 ─────────")
n2 = name_of("", "", "", kind="자유")
print("     " + n2)
ok("소속 칸이 통째로 빠진다", n2 == "호아랑대화_자유_20260830_080224_Purna_D74_P50")
n3 = name_of("cau", "언어교육원 한국어교육과정", "")   # 아는 기관 — 짧은 표를 쓴다
print("     " + n3)
ok("아는 기관은 짧게 적는다", n3.split("_")[2] == "언어교육원", n3)
n4 = name_of("kiip", "KIIP", "")     # 반이 없을 때
ok("반이 없으면 - 가 안 붙는다", "KIIP_2026" in n4, n4)

print("\n── 이름을 망가뜨리는 글자를 막는가 ──────────")
n5 = name_of("etc", "우리/학원\\\\3반: <A>", "가/나")
print("     " + n5)
ok("경로 글자가 안 남는다", not any(c in n5 for c in '/\\:<>"|?*'))
ok("그래도 알아볼 수는 있다", "학원" in n5 and "가나" in n5)
ok("기타는 학습자가 적은 이름을 쓴다", "우리" in n5)
n6 = name_of("etc", "가" * 40, "나" * 20)
ok("아주 긴 이름도 잘린다", len(n6) < 90, len(n6))

print("\n── 정렬하면 기관별로 모이는가 ───────────────")
rows = sorted([name_of("kiip", "KIIP", "2반", ts="20260830_1"),
               name_of("yonsei", "연세대", "A", ts="20260829_1"),
               name_of("kiip", "KIIP", "1반", ts="20260828_1"),
               name_of("cau", "언어교육원", "3급", ts="20260827_1")])
for r in rows: print("     " + r)
tags = [r.split("_")[2].split("-")[0] for r in rows]
ok("같은 기관끼리 붙는다", tags == sorted(tags), tags)

print()
if bad:
    print(f"💥 실패 {len(bad)}건"); sys.exit(1)
print("🎉 소속이 파일 이름까지 닿습니다")

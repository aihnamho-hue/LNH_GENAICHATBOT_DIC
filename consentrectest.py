# -*- coding: utf-8 -*-
"""consentrectest — 동의 기록 한 장이 드라이브까지 닿는가 (v155)

★ 왜 이 검사가 있나
  동의 버전·시각은 대화 자료(.json)마다 실려 간다. 그러나 그것은
  **대화가 있어야** 남는다. 동의만 하고 그만둔 학습자는 아무 데도 안 남는다.
  「누가 언제 무엇에 동의했나」를 이름으로 훑을 명단이 따로 있어야 한다.
"""
import io, re, sys
py = io.open("main.py", encoding="utf-8").read()
ht = io.open("app.html", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else "   " + str(x)))
    if not c: bad.append(m)

print("── 서버가 받을 자리가 있는가 ────────────────")
ok("동의 기록 쪽이 있다", '@app.post("/consent-record")' in py)
seg = re.search(r'@app\.post\("/consent-record"\)[\s\S]*?(?=\n@app\.)', py)
ok("함수를 찾았다", seg is not None)
if not seg: sys.exit(1)
fn = seg.group(0)

for f in ["name", "org", "orgName", "orgVer", "at", "ver", "lang"]:
    ok(f"{f} 를 받는다", re.search(rf"\n\s+{f}: str = Form", fn) is not None)

print("\n── 파일이 제대로 지어지는가 ──────────────────")
ok("이름이 「호아랑동의」로 시작한다", '"호아랑동의"' in fn)
ok("소속을 이름에 넣는다", "_tag" in fn and 'f"_{_tag}"' in fn)
ok("아는 기관은 짧은 표로", '"kiip": "KIIP"' in fn and '"cau": "언어교육원"' in fn)
ok("학습자 이름도 넣는다", "_ntag" in fn)
ok("때가 이름에 들어간다", "%Y%m%d_%H%M%S" in fn)
ok("경로 글자를 막는다", r'[^\w가-힣.-]' in fn or r"[^\w가-힣]" in fn)

print("\n── 안에 무엇이 적히는가 ──────────────────────")
for line in ["동의한 사람", "소속", "동의한 때", "동의서 버전", "이름표 버전", "화면 언어"]:
    ok(f"「{line}」 줄이 있다", f'"{line}' in fn or f"{line} " in fn)
ok("BOM 을 붙인다 (메모장에서 안 깨지게)", '"﻿" + body' in fn)
ok("드라이브에 올린다", "_gdrive_upload_sync" in fn)
ok("드라이브가 꺼져 있으면 그냥 넘어간다", "if not GDRIVE_ENABLED" in fn)

print("\n── 터져도 대화를 막지 않는가 ─────────────────")
ok("서버가 예외를 삼키되 남긴다",
   "except Exception as e" in fn and "[동의] ★ 기록 실패" in fn,
   "삼키기만 하면 왜 안 남았는지 영영 모른다")
ok("화면도 실패를 견딘다", "catch (e) {}" in ht.split("function sendConsentRecord")[1][:900])

print("\n── 두 번 보내지 않는가 ───────────────────────")
cl = ht.split("function sendConsentRecord")[1][:1200]
ok("버전·소속을 표시로 남긴다", 'lsGet("consent.sent") === tag' in cl)
ok("보내기 전에 먼저 찍는다", cl.index('lsPut("consent.sent", tag)') < cl.index("fetch("),
   "응답을 기다렸다 찍으면 그 사이에 또 눌려 두 장이 된다")
ok("실패하면 표시를 지운다 (다음에 다시)", cl.count('lsPut("consent.sent", "")') >= 2)
ok("동의·소속이 다 갖춰진 뒤에 부른다",
   re.search(r"if \(!ORG\.ok\)[^\n]*\n\s*sendConsentRecord\(\);", ht) is not None,
   "소속 없이 부르면 명단에 소속 칸이 빈다")

print("\n── 정식 문안 (v1.1) ──────────────────────────")
doc = re.search(r'async def consent_doc[\s\S]*?(?=\n@app\.)', py).group(0)
ok("버전이 1.1", 'CONSENT_DOC_VER = "1.1"' in py)
ok("화면 버전과 같다", 'const CONSENT_VER = "1.1"' in ht,
   "어긋나면 동의서에 찍히는 버전과 실제가 다르다")
ok("돈 항목을 뺐다", "<h2>4. 돈</h2>" not in doc and "돈을 내지 않습니다" not in doc)
ok("연구 범위에서 학교를 뺐다",
   "중앙대학교 한국어교육학 연구" not in doc and "<b>한국어교육학 연구</b>" in doc)
ok("연구 책임자 소속은 남는다", "중앙대학교 대학원 국어국문학과" in doc)
for h in ["연구의 목적", "수집하는 항목", "자료의 이용 및 익명 처리",
          "참여의 자발성 및 동의 철회", "참여에 따르는 이익과 불이익",
          "자료의 보관 및 파기", "문의"]:
    ok(f"「{h}」 항목이 있다", h in doc)
ok("제3자 제공이 없음을 밝힌다", "제3자에게 자료를 제공하지 않습니다" in doc)
ok("성적과 무관함을 밝힌다", "성적에 어떠한 영향도 미치지 않으며" in doc)
ok("파기 시점을 못 박는다", "연구 종료 후 3년" in doc)
ok("동의 확인 문구가 있다", "자발적인 의사로 연구 참여" in doc)
ok("동의 시각이 무엇인지 밝힌다", "동의 의사를 표시한 시각" in doc)
# ★ v157 — 학습자가 읽는 문서에 버전 번호를 찍지 않는다.
#   읽는 사람에게는 아무 뜻이 없는 숫자다. 어느 글에 동의했는지는
#   드라이브에 쌓이는 동의 기록과 대화 자료(.json)가 이미 갖고 있다.
ok("문서에 버전 번호를 안 찍는다",
   "버전 {esc(q.get('ver')" not in doc and "CONSENT_DOC_VER}" not in doc,
   "읽는 사람에게 뜻이 없는 숫자다")
ok("그래도 기록에는 남는다", '"동의서 버전 : ' in py or "동의서 버전 :" in py)
ok("「판본」을 안 쓴다", "판본" not in py and "판본" not in ht,
   "한국 사람이 쓰는 말로 — 버전은 버전이다")

print()
if bad:
    print(f"💥 실패 {len(bad)}건"); sys.exit(1)
print("🎉 동의 기록이 드라이브까지 닿습니다")

# -*- coding: utf-8 -*-
"""consentrectest — 동의 기록 한 장이 드라이브까지 닿는가 (v155)

★ 왜 이 검사가 있나
  동의 판본·시각은 대화 자료(.json)마다 실려 간다. 그러나 그것은
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
for line in ["동의한 사람", "소속", "동의한 때", "문안 판본", "이름표 판본", "화면 언어"]:
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
ok("판본·소속을 표시로 남긴다", 'lsGet("consent.sent") === tag' in cl)
ok("보내기 전에 먼저 찍는다", cl.index('lsPut("consent.sent", tag)') < cl.index("fetch("),
   "응답을 기다렸다 찍으면 그 사이에 또 눌려 두 장이 된다")
ok("실패하면 표시를 지운다 (다음에 다시)", cl.count('lsPut("consent.sent", "")') >= 2)
ok("동의·소속이 다 갖춰진 뒤에 부른다",
   re.search(r"if \(!ORG\.ok\)[^\n]*\n\s*sendConsentRecord\(\);", ht) is not None,
   "소속 없이 부르면 명단에 소속 칸이 빈다")

print()
if bad:
    print(f"💥 실패 {len(bad)}건"); sys.exit(1)
print("🎉 동의 기록이 드라이브까지 닿습니다")

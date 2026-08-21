# -*- coding: utf-8 -*-
"""sharesrv.py — 교실 화면의 **서버 쪽**을 실제로 돌려 본다 (v143)

★ 규칙을 베끼지 않는다. main.py 에서 코드를 떼어 그대로 실행한다.
"""
import io, re, os, sys, time, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = io.open(f"{ROOT}/main.py", encoding="utf-8").read()
bad = []
def ok(m, c, x=""):
    print(("  ✅ " if c else "  ❌ ") + m + ("" if c else f"   {x}"))
    if not c: bad.append(m)

ns = {"os": os, "time": time, "re": re, "hashlib": hashlib,
      "_clean_str": lambda x, n=999: (str(x or "")[:n]).strip()}
for pat in (r"BOARD_TTL = .*?\n_board: list = \[\].*?\n",
            r"def _board_gc\(\).*?\n\n\n"):
    m = re.search(pat, PY, re.S)
    if not m:
        ok("main.py 에서 교실 보드를 찾는다", False, pat[:40]); print("\n💥"); sys.exit(1)
    exec(m.group(0), ns)
board, gc = ns["_board"], ns["_board_gc"]

def put(name, n=3, at=None):
    board.insert(0, {"id": name, "name": name, "title": "", "mode": "rp",
                     "turns": [{"r": "me", "t": "x"}] * n, "at": at or time.time()})

print("── ① 하루가 지난 것은 사라지는가")
board.clear()
put("어제", at=time.time() - ns["BOARD_TTL"] - 10)
put("오늘")
gc()
ok("지난 것은 빠진다", all(x["name"] != "어제" for x in board), [x["name"] for x in board])
ok("오늘 것은 남는다", any(x["name"] == "오늘" for x in board))

print("\n── ② 한 반(45명)이 한꺼번에 끝내도 되는가")
board.clear()
for i in range(45):
    put(f"학생{i:02d}")
gc()
ok("마흔다섯 명이 다 남는다", len(board) == 45, len(board))
ok("새것이 앞에 온다", board[0]["name"] == "학생44", board[0]["name"])

print("\n── ③ 넘치면 오래된 것부터 밀어내는가")
board.clear()
for i in range(ns["BOARD_MAX"] + 30):
    put(f"C{i:04d}", at=time.time() - (2000 - i))
gc()
ok(f"보관은 {ns['BOARD_MAX']}건까지 {len(board)}", len(board) <= ns["BOARD_MAX"])

print("\n── ④ 무엇을 담기로 했는가 (main.py 를 읽는다)")
ok("대화가 끝나면 저절로 올라온다", '@app.post("/class-log")' in PY)
ok("목록을 주는 길이 있다", '@app.get("/class-list")' in PY)
ok("하나를 꺼내 주는 길이 있다", '@app.get("/class-one/{cid}")' in PY)
ok("목록에는 대화문을 안 싣는다", "대화문은 안 싣는다" in PY)
ok("같은 판을 두 번 보내면 갈아 끼운다", "앞엣것을 갈아 끼운다" in PY)
ok("한 판은 예순 줄까지", "raw[:60]" in PY)
ok("메모리에만 둔다(파일로 안 남긴다)",
   "_board" in PY and not re.search(r"_board.*open\(", PY))
ok("옛 코드 방식은 걷어냈다", "/share" not in PY and "SHARE_ALPHABET" not in PY)

print("\n── ⑤ 교사 화면에 판단이 안 뜨는가")
# ★ **정말 그려지는 것**만 본다 — 설명글(docstring)까지 훑으면 검사가 거짓말을 한다.
#   실제로 「점수도 … 안 띄운다」는 주석을 잡고 빨간불을 냈다.
m = re.search(r'async def class_screen\(\).*?return HTMLResponse\(f"""(.*?)"""\)', PY, re.S)
ui = m.group(1) if m else ""
ok("교사 화면을 찾았다", bool(ui))
for w in ("점수", "idcTotal", "selfCheck", "selfNote", "총평", "review", "별점"):
    ok(f"「{w}」가 안 뜬다", w not in ui)
ok("대화문은 뜬다", 'b.className = "bub"' in ui and "호아랑" in ui)
ok("목록에서 골라 본다", 'id="side"' in ui and "/class-list" in ui and "/class-one/" in ui)
ok("글자 크기를 바꿀 수 있다", 'id="plus"' in ui and 'id="minus"' in ui)
ok("수업 중 저절로 새로 고친다", "setInterval(loadList" in ui)

print("\n" + (f"💥 {len(bad)}건" if bad else "🎉 교실 화면 서버 쪽 이상 없음"))
sys.exit(1 if bad else 0)

# -*- coding: utf-8 -*-
"""main.py 안의 **없는 이름**을 찾는다.

왜 필요한가 — v122에서 send_hints 안에 `native` 를 썼는데 그 스코프에는
그런 이름이 없었다. 파이썬은 실행하기 전에는 모르고, 그 자리는 예외를
삼키는 try 안이라, **도움말이 두 판 내내 한 번도 안 만들어졌는데도**
아무도 몰랐다. ast.parse 도 node --check 도 이걸 못 잡는다.

symtable 은 스코프를 실제로 계산한다. 함수 안에서 쓰였는데
 · 그 함수의 지역도 아니고
 · 감싸는 함수의 지역도 아니고 (그러면 free 로 잡힌다)
 · 모듈 전역도 아니고
 · 내장도 아니면
→ 실행하는 순간 NameError 다.
"""
import io, sys, symtable, builtins

SRC = sys.argv[1] if len(sys.argv) > 1 else "main.py"
code = io.open(SRC, encoding="utf-8").read()
top = symtable.symtable(code, SRC, "exec")
mod = set(top.get_identifiers())
bad = []

def walk(tab, path):
    if tab.get_type() == "function":
        for sym in tab.get_symbols():
            n = sym.get_name()
            if sym.is_assigned() or sym.is_parameter() or sym.is_imported():
                continue
            if not sym.is_referenced():
                continue
            if sym.is_free() or sym.is_local():
                continue
            if n in mod or hasattr(builtins, n):
                continue
            bad.append((" → ".join(path), n, tab.get_lineno()))
    for ch in tab.get_children():
        walk(ch, path + [ch.get_name()])

walk(top, ["(모듈)"])
if bad:
    print(f"💥 없는 이름 {len(bad)}개 — 실행하면 NameError 가 난다")
    for where, n, ln in bad:
        print(f"   · {where}  ({ln}줄 부근)  →  {n}")
    sys.exit(1)
print(f"✅ 없는 이름 없음 ({SRC})")

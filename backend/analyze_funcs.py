# -*- coding: utf-8 -*-
"""分析单个 python 文件里各顶层函数的行数体量。"""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "app/routers/admin.py"
src = open(p, encoding="utf-8").read().splitlines()
marks = []
for i, l in enumerate(src, 1):
    if l.startswith("@router.") or l.startswith("@app.") or l.startswith("async def ") or l.startswith("def "):
        marks.append((i, l.strip()[:70]))
for j, (ln, t) in enumerate(marks):
    end = marks[j + 1][0] - 1 if j + 1 < len(marks) else len(src)
    print(f"{ln:5d}-{end:5d} ({end - ln + 1:4d}行)  {t}")

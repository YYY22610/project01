# -*- coding: utf-8 -*-
"""统计软著申报相关的代码体量（剔除空行、注释、docstring）。"""
import os

ROOT = r"D:/27475/WorkBuddy-搭建网站/travel-experiment-platform"
SKIP_DIRS = {"node_modules", "venv", ".git", "dist", "__pycache__", ".vite",
             "browser_shots", "walkthrough_tools", ".pytest_cache"}
EXT = (".py", ".ts", ".tsx", ".sql")

buckets, files_detail = {}, []
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
    for f in files:
        if not f.endswith(EXT):
            continue
        p = os.path.join(root, f)
        try:
            src = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except Exception:
            continue
        n = 0
        for l in src:
            s = l.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            if s.startswith('"""') or s.startswith("'''"):
                continue
            n += 1
        key = os.path.relpath(root, ROOT).replace("\\", "/")
        buckets[key] = buckets.get(key, 0) + n
        files_detail.append((n, key, f))

tot = sum(buckets.values())
print("有效代码总行数:", tot)
print("\n--- 按目录 ---")
for k, v in sorted(buckets.items(), key=lambda x: -x[1])[:14]:
    print(f"{v:6d}  {k}")

print("\n--- 单文件 TOP 15 ---")
for n, d, f in sorted(files_detail, reverse=True)[:15]:
    print(f"{n:6d}  {d}/{f}")

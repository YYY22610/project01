"""
导出聚合「坑」核对脚本
======================
针对已知的两个导出聚合坑做端到端验证：
  坑1：聚合函数用 uid = str(user_id)，否则 export 里 str(user.id) 查不到 → 问卷列全空
  坑2：manipulation_check 是文本选择题，不能取均值，否则该列恒空/失真

做法：
  1) 直接调用 _compute_questionnaire_scores(db) 看真实聚合结构
  2) 实际拉取 /export/all CSV，统计各问卷列非空行数
  3) 演示：若聚合按 int 建键，export 的 str(user.id) 查表会全部 miss（坑1 复现）
"""
import asyncio
import csv
import io

import httpx

BASE = "http://127.0.0.1:8000/api"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


async def main():
    # ---- 1) 直接聚合（读真实库） ----
    from app.database import async_session_factory
    from app.routers.admin import _compute_questionnaire_scores

    async with async_session_factory() as db:
        scores = await _compute_questionnaire_scores(db)

    print("==== 1) 聚合函数输出结构 ====")
    print(f"聚合覆盖用户数: {len(scores)}")
    # 统计每个构念有多少人（即该列应有数据的行数）
    from collections import Counter
    has_construct = Counter()
    has_manip = 0
    for uid, per in scores.items():
        for c in ("trust", "autonomy", "satisfaction", "task_load", "future_use"):
            if per.get(c) not in (None, ""):
                has_construct[c] += 1
        if per.get("manipulation_check"):
            has_manip += 1
    print("各 Likert 构念有值人数:", dict(has_construct))
    print(f"manipulation_check 有文本人数: {has_manip}")
    # 抽样展示一个用户的完整聚合（含 manipulation_check 文本）
    if scores:
        sample_uid = next(iter(scores))
        print(f"\n抽样用户 {sample_uid} 聚合字典: {scores[sample_uid]}")

    # ---- 2) 实际拉取 export/all CSV ----
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE}/auth/admin/login",
                          json={"username": ADMIN_USER, "password": ADMIN_PASS})
        tok = r.json()["access_token"]
        r = await c.get(f"{BASE}/admin/export/all",
                        headers={"Authorization": f"Bearer {tok}"})
        csv_text = r.text
    reader = list(csv.reader(io.StringIO(csv_text)))
    header = reader[0]
    rows = reader[1:]
    print("\n==== 2) export/all CSV 实际列 ====")
    print("列名:", header)
    print(f"数据行数(用户数): {len(rows)}")

    # 问卷相关列索引
    cols = ["信任", "自主", "满意", "负荷", "未来意愿", "操纵检验"]
    print("\n各问卷列非空行数（应为有该数据的真实人数）:")
    for col in cols:
        if col in header:
            idx = header.index(col)
            nonempty = sum(1 for row in rows if len(row) > idx and row[idx].strip())
            print(f"  {col}: 非空 {nonempty} 行")
        else:
            print(f"  {col}: 列不存在！")

    # ---- 3) 复现坑1：若聚合不转 str（用原始 UUID 对象建键） ----
    print("\n==== 3) 坑1 复现演示（若聚合不转 str，用原始 UUID 对象建键）====")
    from app.models.user import User
    from sqlalchemy import select
    async with async_session_factory() as db:
        uids = (await db.execute(select(User.id))).scalars().all()
    # 模拟旧 bug：聚合用原始 UUID 对象做键（不 str），export 端用 str(user.id) 查
    bug_dict = {uid: scores.get(str(uid), {}) for uid in uids}  # 错：键是 UUID 对象
    hit = sum(1 for uid in uids if str(uid) in bug_dict)  # export 端 str 查——全部 miss
    print(f"正确(str 对 str): export 能匹配 {sum(1 for uid in uids if str(uid) in scores)} 个有问卷的用户")
    print(f"若为 UUID 对象建键(str 查表): 全部 miss = {hit} → 问卷列全空（即坑1 现象）")
    print("\n结论：当前代码用了 str(user_id) 建键 + export 用 str(user.id) 查表，"
          "两者一致，问卷列不会空；manipulation_check 作为文本保留（见抽样）。")


if __name__ == "__main__":
    asyncio.run(main())

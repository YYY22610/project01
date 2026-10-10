"""
实验前清理账号脚本（破坏性操作，默认 DRY RUN）
==============================================
用途：正式收数据前，把库里早期测试 / 种子残留的账号清掉，只保留受邀者，
      再让新参与者 signup 时 assign_group 重新均衡三组比例。

安全设计：
  - 默认只「列出」会被删的账号，不删任何东西（DRY RUN）。
  - 真正删除必须同时提供：
      1) --delete           显式开关
      2) --keep <文件>      受邀者白名单（邮箱，每行一个）；白名单内绝不删
  - 删除顺序：先删 moa_group_sessions（外键子表），再删 users，避免外键约束报错。
  - 若没有提供 --keep，即使加了 --delete 也会拒绝执行（防止误删受邀者）。

用法：
    ../venv/Scripts/python.exe cleanup_users.py                 # 仅预览
    ../venv/Scripts/python.exe cleanup_users.py --delete --keep invited.txt
"""
import argparse
import asyncio
import sys

from app.database import async_session_factory
from app.models.user import User
from app.models.moa_group_session import MoaGroupSession
from sqlalchemy import delete, select, func


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--delete", action="store_true", help="真正删除（仍需 --keep）")
    p.add_argument("--keep", help="受邀者白名单文件（邮箱，每行一个）；白名单内不删")
    args = p.parse_args()

    keep = set()
    if args.keep:
        try:
            with open(args.keep, encoding="utf-8") as f:
                for line in f:
                    e = line.strip()
                    if e:
                        keep.add(e.lower())
        except FileNotFoundError:
            print(f"[!] 白名单文件不存在: {args.keep}")
            sys.exit(1)

    async with async_session_factory() as db:
        total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        # 待删 = 不在白名单的账号
        rows = (await db.execute(select(User.id, User.email, User.group))).all()
        to_delete = [(uid, email, grp) for (uid, email, grp) in rows
                     if (email or "").lower() not in keep]
        keep_count = total - len(to_delete)
        grp_dist = {}
        for _, _, grp in to_delete:
            key = grp.value if grp else "NULL"
            grp_dist[key] = grp_dist.get(key, 0) + 1

        print(f"库内总用户: {total}    白名单保留: {keep_count}    待删: {len(to_delete)}")
        print(f"待删分组分布: {grp_dist}")
        # 预览前 20 个
        for uid, email, grp in to_delete[:20]:
            print(f"  - {email}  ({grp.value if grp else 'NULL'})")
        if len(to_delete) > 20:
            print(f"  ... 其余 {len(to_delete) - 20} 个省略")

        if not args.delete:
            print("\n[DRY RUN] 未删除任何数据。加 --delete --keep invited.txt 才真正执行。")
            return

        if not keep:
            print("[!] 未提供 --keep 白名单，拒绝执行，避免误删受邀者。")
            sys.exit(1)

        # 真正删除：先子表后主表
        ids = [uid for (uid, _, _) in to_delete]
        await db.execute(delete(MoaGroupSession).where(MoaGroupSession.user_id.in_(ids)))
        await db.execute(delete(User).where(User.id.in_(ids)))
        await db.commit()
        print(f"\n[已删除] {len(ids)} 个账号（及对应 MOA 会话态）。白名单 {keep_count} 人保留。")


if __name__ == "__main__":
    asyncio.run(main())

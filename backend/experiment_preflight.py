"""
实验前一键自检
==============
开实验前一条命令查清关键就绪项，避免踩已知坑（尤其 agent_service_paused 残留为 true
会让所有 SOA/MOA 用户的 AI 调用直接 403）。

检查项：
  1. 后端可达 + LLM 模式（mock/real）
  2. AI 助理暂停开关 agent_service_paused（核心：必须为 false）
  3. 实验开关 experiment_active
  4. 任务配置（目的地/天数/预算/人数）
  5. 用户分组分布（H/SOA/MOA 平衡）
  6. 测试账号残留（email 以 conc_test_ 开头）
  7. 管理员默认口令 admin/admin123 是否仍生效（安全）

用法（在 backend 目录下用 venv 运行）：
    ../venv/Scripts/python.exe experiment_preflight.py
"""
import asyncio
import sys

import httpx
from sqlalchemy import select, func

from app.config import settings
from app.database import async_session_factory
from app.models.user import User
from app.models.system_config import SystemConfig

BASE = "http://127.0.0.1:8000/api"


async def get_cfg(db, key: str, default: str = ""):
    r = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    c = r.scalar_one_or_none()
    return c.value if c else default


async def main():
    problems: list[str] = []
    warns: list[str] = []
    print("==== 实验前自检 ====")

    # 1) 后端可达 + LLM 模式 + 管理员默认口令
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BASE}/health")
            h = r.json()
            mode = h.get("llm_mode", "?")
            print(f"[1] 后端可达: ✅  {h}")
            # 管理员默认口令探测
            ar = await c.post(f"{BASE}/auth/admin/login",
                              json={"username": "admin", "password": "admin123"})
            if ar.status_code == 200:
                warns.append("管理员默认口令 admin/admin123 仍可用——公网/正式环境务必改掉，否则任何人可接管。")
                print("[1] 管理员口令: ⚠️ 默认 admin/admin123 仍生效")
            else:
                print("[1] 管理员口令: ✅ 默认口令已修改（或被锁定）")
    except Exception as e:
        print(f"[1] 后端可达: ❌  {e}")
        print("    后端未运行或与 BASE 不通，无法继续。请先启动后端。")
        sys.exit(1)

    # 2) LLM 模式
    if mode == "mock":
        warns.append("LLM 处于 MOCK 模式——返回的是写死的虚假回答，禁止用于收实验数据！"
                     "请配置 LLM_API_KEY，或在 .env 设 ALLOW_MOCK_LLM=false 后重启。")
        print(f"[2] LLM 模式: ⚠️  mock（虚假回答，不可用）")
    else:
        print(f"[2] LLM 模式: ✅  real（模型 {settings.LLM_MODEL}）")

    async with async_session_factory() as db:
        # 3) AI 助理暂停开关
        paused = await get_cfg(db, "agent_service_paused", "false")
        if paused == "true":
            problems.append("agent_service_paused=true：所有 SOA/MOA 用户的 AI 助理调用会直接 403，"
                            "开实验前必须置为 false（后台「暂停/恢复 AI 助理」开关，或改 system_config）。")
            print(f"[3] AI助理暂停开关: ❌  paused={paused}")
        else:
            print(f"[3] AI助理暂停开关: ✅  paused={paused}")

        # 4) 实验开关
        active = await get_cfg(db, "experiment_active", "true")
        if active != "true":
            warns.append(f"experiment_active={active}（非 true）——前台可能未对用户开放注册/实验入口。")
            print(f"[4] 实验开关: ⚠️  {active}")
        else:
            print(f"[4] 实验开关: ✅  {active}")

        # 5) 任务配置
        dest = await get_cfg(db, "destination", "")
        days = await get_cfg(db, "task_days", "")
        budget = await get_cfg(db, "task_budget", "")
        travelers = await get_cfg(db, "task_travelers", "")
        print(f"[5] 任务配置: 目的地={dest or '(空)'} 天数={days or '(空)'} "
              f"预算={budget or '(空)'} 人数={travelers or '(空)'}")
        if not (dest and days and budget):
            warns.append("任务配置（目的地/天数/预算）存在空值，开实验前请确认设置正确且符合你的实验设计。")

        # 6) 分组分布
        res = await db.execute(select(User.group, func.count(User.id)).group_by(User.group))
        dist = {(g.value if g is not None else None): n for g, n in res.all()}
        total = sum(dist.values())
        print("[6] 用户分组分布(共 %d 人): %s" % (
            total, ", ".join(f"{k or 'NULL'}={v}" for k, v in sorted(
                dist.items(), key=lambda kv: (kv[0] is None, str(kv[0])))) or "（暂无用户）"))
        # 平衡性提示：仅当 SOA/MOA 都有人时提示失衡
        soa = dist.get("SOA", 0)
        moa = dist.get("MOA", 0)
        if total and total > 50:
            warns.append(f"当前库已有 {total} 个用户，若其中包含早期测试/种子数据，"
                         "正式实验前建议清空非受邀账号，再让 assign_group 重新均衡分组。")
        if soa and moa and abs(soa - moa) > 2:
            warns.append(f"SOA({soa}) 与 MOA({moa}) 人数差较大；若需两组对照平衡，"
                         "可用后台「设置分组」手动补齐，或清空后重新随机分配。")

        # 7) 测试账号残留
        res = await db.execute(select(func.count(User.id)).where(User.email.like("conc_test_%")))
        test_cnt = res.scalar() or 0
        if test_cnt:
            warns.append(f"数据库残留 {test_cnt} 个测试账号（email 以 conc_test_ 开头），"
                         "会污染样本，建议用 test_concurrent_users_chat.py 的清理逻辑或手动删除。")
            print(f"[7] 测试账号残留: ⚠️  {test_cnt} 个")
        else:
            print("[7] 测试账号残留: ✅  0")

    # 结论
    print("\n==== 结论 ====")
    if problems:
        print("❌ 必须处理的问题：")
        for p in problems:
            print("   -", p)
        sys.exit(2)
    print("✅ 无阻断性问题，可以开实验。")
    if warns:
        print("⚠️ 需留意：")
        for w in warns:
            print("   -", w)


if __name__ == "__main__":
    asyncio.run(main())

"""验证无密码注册 + 人口统计采集 + 同意 链路（内进程 ASGI，真实 Postgres）。"""
import asyncio
import os

os.environ.setdefault("LLM_API_KEY", "")  # mock LLM，避免真实调用

import httpx
from app.main import app
from app.database import engine, async_session_factory
from sqlalchemy import select, text
from app.models.user import User


async def run():
    transport = httpx.ASGITransport(app=app)
    test_email = "pwless_verify@example.com"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. 无密码注册
        r = await c.post("/api/auth/register", json={"email": test_email})
        assert r.status_code == 200, f"注册失败: {r.status_code} {r.text}"
        token = r.json()["access_token"]
        print("[OK] 无密码注册 ->", r.status_code)

        headers = {"Authorization": f"Bearer {token}"}

        # 2. 采集人口统计
        r = await c.post(
            "/api/auth/demographics",
            json={
                "age": 22,
                "gender": "male",
                "education": "bachelor",
                "tech_frequency": "daily",
                "ai_experience": "intermediate",
            },
            headers=headers,
        )
        assert r.status_code == 200, f"人口统计失败: {r.status_code} {r.text}"
        print("[OK] 人口统计采集 ->", r.status_code, r.json())

        # 3. 同意
        r = await c.post("/api/auth/consent", headers=headers)
        assert r.status_code == 200, f"同意失败: {r.status_code} {r.text}"
        print("[OK] 知情同意 ->", r.status_code, "status=", r.json().get("status"))

        # 4. 校验库里 password_hash 为 NULL、demographics 已写入
        async with async_session_factory() as db:
            u = (await db.execute(select(User).where(User.email == test_email))).scalar_one()
            assert u.password_hash is None, "password_hash 应仍为 NULL"
            assert u.age == 22 and u.gender == "male", "人口统计未入库"
            assert u.status.value == "consented", f"状态应为 consented, 实际 {u.status}"
            print("[OK] 库校验通过: password_hash=None, age=22, status=consented")

    # 清理
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM users WHERE email = :e"), {"e": test_email})
        await db.commit()
    print("[CLEAN] 测试用户已删除")


async def run_all():
    try:
        await run()
        print("\nALL PASS ✅")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_all())

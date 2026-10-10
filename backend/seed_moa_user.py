"""预置一个 MOA 组测试用户，供浏览器端到端点击验证登录使用。"""
import asyncio
from sqlalchemy import select

from app.database import async_session_factory
from app.models.user import User, ExperimentGroup, UserStatus
from app.services.auth_service import hash_password

EMAIL = "moaval@test.com"
PW = "Test1234!"


async def main():
    async with async_session_factory() as db:
        res = await db.execute(select(User).where(User.email == EMAIL))
        u = res.scalar_one_or_none()
        if u:
            u.group = ExperimentGroup.MOA
            u.status = UserStatus.CONSENTED
            u.password_hash = hash_password(PW)
            print("updated existing user", u.id)
        else:
            u = User(
                email=EMAIL,
                password_hash=hash_password(PW),
                group=ExperimentGroup.MOA,
                status=UserStatus.CONSENTED,
            )
            db.add(u)
            print("created user")
        await db.commit()
        await db.refresh(u)
        print("email=", u.email, "group=", u.group, "status=", u.status)


if __name__ == "__main__":
    asyncio.run(main())

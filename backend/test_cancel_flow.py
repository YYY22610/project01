"""
干预能力（取消）专项测试：
① /agent/cancel 端点鉴权 + 校验 + 置位标志（真实 HTTP via httpx ASGI，命中真实 DB）
② BaseAgent.chat 在 cancel_check 命中时：yield cancelled 事件、且不执行后续工具
   （证明"参与者中断能真正拦住运行中的操作，如发邮件/生成Word"）
"""
import asyncio
import os
os.environ.setdefault("LLM_API_KEY", "")  # 强制 mock LLM，确定性无网络

import httpx
from sqlalchemy import select
from passlib.context import CryptContext

from app.main import app
from app.database import async_session_factory, engine
from app.services.agents.base_agent import BaseAgent
from app.services.agents.tools import agent_tools as at

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
results = []


def record(feat, ok, detail):
    results.append((feat, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {feat:<14} {detail}")


# ---------- ② BaseAgent 单元级：取消拦截后续工具执行 ----------
class FakeLLM:
    def __init__(self, tool_calls):
        self._tool_calls = tool_calls
        self._calls = 0

    async def chat(self, messages, tools):
        self._calls += 1
        if self._calls == 1:
            return {"content": "", "tool_calls": self._tool_calls}
        return {"content": "final", "tool_calls": None}


class FakeDB:
    def add(self, *a, **k):
        pass

    async def flush(self):
        pass

    async def execute(self, *a, **k):
        class R:
            def scalars(self):
                class S:
                    def all(self):
                        return []
                return S()
        return R()

    async def commit(self):
        pass


async def test_base_agent_cancel():
    captured = []  # (type, data)

    # base_agent 内部直接引用导入的 execute_tool 名，无法被模块属性 monkeypatch；
    # 改用真实工具执行，但 spy 包一层以观测调用（通过替换 base 模块内的引用名）。
    import app.services.agents.base_agent as ba
    orig = ba.execute_tool

    async def spying_exec(tool_name, arguments):
        captured.append(("exec", tool_name))
        return await orig(tool_name, arguments)

    ba.execute_tool = spying_exec
    try:
        agent = BaseAgent("soa", "sys", tools=["search_attractions", "generate_docx"])
        agent.llm = FakeLLM([
            {"function": {"name": "search_attractions", "arguments": "{}"}},
            {"function": {"name": "generate_docx", "arguments": "{}"}},
        ])

        cancel_state = {"flag": False}

        async def cancel_check():
            return cancel_state["flag"]

        # 两个工具：用户在第 1 个工具调用后点击停止，第 2 个工具应被真正拦住
        async for chunk in agent.chat("user-x", "请帮我搜索并生成文档", FakeDB(), cancel_check=cancel_check):
            captured.append((chunk.get("type"), chunk.get("data")))
            if chunk.get("type") == "tool_call":
                cancel_state["flag"] = True  # 模拟用户点击"停止"

        types = [c[0] for c in captured]
        exec_tools = [c[1] for c in captured if c[0] == "exec"]
        record("②", "cancelled" in types,
               f"events={types}; executed={exec_tools}")
        # 第 1 个工具(search)已执行；第 2 个工具(generate_docx)在取消后被拦截
        record("②-拦截", "generate_docx" not in exec_tools,
               f"取消后第2个工具不应执行，实际={exec_tools}")
    finally:
        ba.execute_tool = orig


# ---------- ① /agent/cancel 端点（真实 HTTP via httpx ASGI） ----------
async def test_cancel_endpoint():
    from app.models.user import User, ExperimentGroup

    email = "cancel_test_e2e@example.com"
    password = "CancelTest123!"
    h = pwd_ctx.hash(password)

    async with async_session_factory() as s:
        existing = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            existing.password_hash = h
            existing.group = ExperimentGroup.SOA
        else:
            s.add(User(email=email, password_hash=h, group=ExperimentGroup.SOA))
        await s.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/login", json={"email": email, "password": password})
        record("①-登录", r.status_code == 200, f"status={r.status_code}")
        if r.status_code != 200:
            return
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        rc = await client.post("/api/agent/cancel", json={"agent_id": "soa"}, headers=headers)
        record("①-取消有效", rc.status_code == 200 and rc.json().get("status") == "cancelled",
               f"status={rc.status_code} body={rc.json()}")

        rb = await client.post("/api/agent/cancel", json={"agent_id": "moa_a"}, headers=headers)
        record("①-越权拒绝", rb.status_code == 400, f"status={rb.status_code}")

        # 未带 token 应 401
        rn = await client.post("/api/agent/cancel", json={"agent_id": "soa"})
        record("①-未鉴权拒绝", rn.status_code == 401, f"status={rn.status_code}")

    # 清理数据库中的测试用户
    async with async_session_factory() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if u:
            await s.delete(u)
            await s.commit()


async def run_all():
    await test_base_agent_cancel()
    await test_cancel_endpoint()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_all())
    fails = [r for r in results if not r[1]]
    print(f"\nTOTAL {len(results)}  PASS {len(results)-len(fails)}  FAIL {len(fails)}")
    import sys
    sys.exit(1 if fails else 0)

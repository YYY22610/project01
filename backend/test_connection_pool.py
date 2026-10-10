"""回归测试：验证 SSE 流在 LLM 调用期间不占用数据库连接（修复连接池长占问题）。

根因回顾：原 agent.chat 接收一个长生命周期会话 db，从「存用户消息」一直用到
「整场 LLM 多轮对话结束」才提交，导致连接被长占数分钟。当 30+ 用户同时对话时，
30 条连接（pool_size=10 + max_overflow=20）被全部占满，登录/注册/问卷等普通请求
全部阻塞。

本测试做法：mock LLM 客户端，在其 .chat() 被调用时检查连接池 checkedout() 数。
若修复有效，此时应为 0 —— 说明 agent.chat 的 DB 短操作（存用户消息、读历史、
存助手消息）已在 LLM 调用前/后各自释放连接，整场对话期间不会占池。

运行：backend/venv/Scripts/python.exe test_connection_pool.py
"""
import asyncio
import os
import warnings

# 必须在 import app 之前设置，避免真实 LLM 客户端初始化报错
os.environ.setdefault("LLM_API_KEY", "test-dummy-for-pool-test")
warnings.filterwarnings("ignore", message=r'Field name "construct".*', category=UserWarning)

from sqlalchemy import text

from app.database import engine, async_session_factory
from app.models.user import User, ExperimentGroup
from app.models.chat_message import ChatMessage
from app.services.agents.base_agent import BaseAgent

import app.services.agents.base_agent as ba


class FakeLLM:
    """在被调用（即 LLM 推理阶段）时记录连接池占用。"""
    observed_checkedout = None

    async def chat(self, messages, tools=None):
        # 关键检查点：此时 agent 不应持有任何长生命周期连接
        FakeLLM.observed_checkedout = engine.pool.checkedout()
        return {"content": "这是测试用的固定回复", "tool_calls": None}


# 注入 mock：必须在实例化 BaseAgent 之前
ba.get_llm_client = lambda: FakeLLM()


async def main():
    # 1) 准备一个真实测试用户（ChatMessage.user_id 有外键约束）
    async with async_session_factory() as db:
        user = User(
            email="pool_regression_test@example.com",
            group=ExperimentGroup.SOA,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        uid = str(user.id)

    try:
        # 2) 运行 agent.chat（不传 db，验证新签名）；注意全程不应长占连接
        agent = BaseAgent(agent_id="soa", system_prompt="test", tools=[])
        events = []
        async for chunk in agent.chat(uid, "你好"):
            events.append(chunk)
        tail = events[-1].get("type") if events else None
        print("agent.chat 事件尾类型:", tail)

        observed = FakeLLM.observed_checkedout
        print("LLM 调用时连接池 checkedout() =", observed)

        # 3) 断言：LLM 推理阶段连接池必须完全空闲
        assert observed == 0, (
            f"连接池在 LLM 调用期间仍被占用（checkedout={observed}），"
            f"说明长生命周期会话未被修复"
        )

        # 4) 额外断言：agent.chat 新签名不再要求外部 db 参数
        import inspect
        params = list(inspect.signature(BaseAgent.chat).parameters)
        assert "db" not in params, "BaseAgent.chat 不应再接收 db 参数"
        print("BaseAgent.chat 签名已不含 db 参数:", params)

        print("\nPASS ✅ agent.chat 在 LLM 调用期间未占用数据库连接")
    finally:
        # 5) 清理测试数据
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM chat_messages WHERE user_id = :u"), {"u": uid}
            )
            await db.execute(
                text("DELETE FROM users WHERE id = :u"), {"u": uid}
            )
            await db.commit()
        print("已清理测试用户及聊天记录")


if __name__ == "__main__":
    asyncio.run(main())

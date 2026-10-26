# -*- coding: utf-8 -*-
"""验证 base_agent 多轮工具循环修复效果。

复现截图场景：用户发「根据景点帮我排 3 天行程，预算控制在 2000 内」，
修复前模型第二轮仍想调工具 → tool_calls 被丢弃 → 只回「操作完成。」。
修复后应返回有实际内容的行程规划。

用真实 LLM，走完整的 chat() 流式生成器。
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, ".")

from app.services.agents.agent_factory import get_agent
from app.database import async_session_factory
from sqlalchemy import text

PROMPT = "先帮我搜一下杭州有哪些必去的景点，再根据搜索结果给我排 3 天行程，预算 2000 内"


async def main():
    # 建一个临时账号（chat_messages 有外键约束），跑完删掉
    async with async_session_factory() as db:
        tmp_uid = str(uuid.uuid4())
        await db.execute(text(
            "insert into users (id, email, status, \"group\") "
            "values (:i, :e, 'task_in_progress', 'SOA')"
        ), {"i": tmp_uid, "e": f"probe_mr_{uuid.uuid4().hex[:6]}@test.local"})
        await db.commit()

    agent = get_agent("soa")

    events = []
    content_parts = []
    tool_names = []

    print(f"用户提问：{PROMPT}\n")
    print("流式输出：")
    async for ev in agent.chat(
        user_id=tmp_uid,
        message=PROMPT,
        cancel_check=None,
    ):
        events.append(ev["type"])
        if ev["type"] == "content":
            piece = ev["data"] if isinstance(ev["data"], str) else str(ev["data"])
            content_parts.append(piece)
            print(piece, end="", flush=True)
        elif ev["type"] == "tool_call":
            tool_names.append(ev["data"].get("tool"))
            print(f"\n  [工具调用] {ev['data'].get('tool')} {ev['data'].get('arguments')}")
        elif ev["type"] == "tool_result":
            print(f"  [工具完成] {ev['data'].get('status')}")
        elif ev["type"] == "error":
            print(f"\n  [错误] {ev['data']}")

    full = "".join(content_parts)
    print("\n\n=== 结论 ===")
    print(f"工具调用次数: {len(tool_names)} -> {tool_names}")
    print(f"最终回复长度: {len(full)} 字")
    print(f"是否仍为『操作完成。』兜底: {'是 ❌' if full.strip() in ('操作完成。', '') else '否 ✅'}")

    # 清理本次产生的 chat_messages
    async with async_session_factory() as db:
        await db.execute(text("delete from chat_messages where user_id = :u"), {"u": tmp_uid})
        await db.execute(text("delete from behavior_logs where user_id = :u"), {"u": tmp_uid})
        await db.execute(text("delete from users where id = :u"), {"u": tmp_uid})
        await db.commit()
    print("临时账号已清理")


asyncio.run(main())

# -*- coding: utf-8 -*-
"""探针：复现「AI 只回『操作完成。』」的问题。

模拟 base_agent.chat 的完整两轮流程：
  第 1 轮：带工具定义请求 → 期望返回 tool_calls
  第 2 轮：把工具结果按 OpenAI function-calling 格式回填 → 期望返回自然语言

重点观察第 2 轮的 raw content / reasoning_content / finish_reason，
判断是模型返回空、还是请求构造有误。
"""
import asyncio
import json
import sys

import httpx

sys.path.insert(0, ".")

from app.config import settings
from app.services.agents.tools.agent_tools import TOOL_DEFINITIONS, execute_tool


async def call_llm(messages, tools=None):
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": settings.LLM_MODEL, "messages": messages}
    if tools:
        payload["tools"] = [{"type": "function", "function": t} for t in tools]
    if settings.LLM_MODEL.startswith("qwen3"):
        payload["enable_thinking"] = False
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{settings.LLM_API_BASE_URL}/chat/completions",
            headers=headers, json=payload,
            timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
        )
        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {r.text[:400]}")
            return None
        return r.json()


async def main():
    print(f"模型: {settings.LLM_MODEL}\n")

    # ---- 第一轮 ----
    msgs = [
        {"role": "system", "content": "你是杭州旅行规划助理。用户问什么你就回答，需要信息时调用工具。"},
        {"role": "user", "content": "根据景点帮我排 3 天行程，预算控制在 2000 内"},
    ]
    data1 = await call_llm(msgs, TOOL_DEFINITIONS)
    if not data1:
        return
    choice1 = data1["choices"][0]
    msg1 = choice1["message"]
    print("=== 第 1 轮 ===")
    print("finish_reason:", choice1.get("finish_reason"))
    print("content:", repr((msg1.get("content") or "")[:200]))
    print("reasoning_content:", repr((msg1.get("reasoning_content") or "")[:150]))
    print("tool_calls:", json.dumps(msg1.get("tool_calls"), ensure_ascii=False)[:400])

    tool_calls = msg1.get("tool_calls")
    if not tool_calls:
        print("\n!! 第 1 轮没有 tool_calls，探针结束（说明模型未触发工具）")
        return

    # ---- 回填工具结果（照 base_agent.py 的写法）----
    msgs.append({
        "role": "assistant",
        "content": msg1.get("content") or "",
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                },
            }
            for tc in tool_calls
        ],
    })
    for tc in tool_calls:
        name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        print(f"\n执行工具 {name}({args}) ...")
        result = await execute_tool(name, args, user_id=None)
        print("结果摘要:", json.dumps(result, ensure_ascii=False)[:300])
        msgs.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": json.dumps(result, ensure_ascii=False),
        })

    # ---- 第二轮 ----
    data2 = await call_llm(msgs, None)
    if not data2:
        return
    choice2 = data2["choices"][0]
    msg2 = choice2["message"]
    print("\n=== 第 2 轮（这就是用户看到的回复）===")
    print("finish_reason:", choice2.get("finish_reason"))
    print("usage:", data2.get("usage"))
    print("content 长度:", len(msg2.get("content") or ""))
    print("content:", repr((msg2.get("content") or "")[:400]))
    print("reasoning_content 长度:", len(msg2.get("reasoning_content") or ""))
    print("reasoning_content:", repr((msg2.get("reasoning_content") or "")[:300]))

    if not (msg2.get("content") or "").strip():
        print("\n>>> 复现成功：第 2 轮 content 为空，会落进 base_agent 的“操作完成。”兜底 <<<")


asyncio.run(main())

"""Verify Qwen-style empty-content / reasoning_content handling.

模拟 Qwen3 等"思考"模型：choices[0].message.content 为 None，
正式回答在 reasoning_content。验证 RealLLMClient 能回退、base_agent 不再因 None 崩溃。
真实库只读（查询系统配置），不写入，安全。
"""
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, ".")

from app.services.agents.llm_client import RealLLMClient


def _fake_qwen3_response():
    """模拟 DashScope 返回的 Qwen3 思考模型响应：content=None，回答在 reasoning_content。"""
    payload = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "reasoning_content": "杭州西湖很值得一去，建议上午去。",
                "tool_calls": None,
            }
        }]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=payload)
    return resp


def _fake_empty_no_reasoning():
    """更极端：content=None 且 reasoning_content 也缺失。应回退为空串而不崩溃。"""
    payload = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": None,
            }
        }]
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(return_value=payload)
    return resp


async def run():
    # 用例1：Qwen3 content=None + reasoning_content -> 应取 reasoning_content
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_fake_qwen3_response())
        MockClient.return_value.__aenter__.return_value = mock_client
        result = await RealLLMClient().chat([{"role": "user", "content": "推荐景点"}], None)
    assert result["content"] == "杭州西湖很值得一去，建议上午去。", result
    assert result["tool_calls"] is None
    print("[OK] 用例1 Qwen3 content=None -> 回退 reasoning_content:", repr(result["content"]))

    # 用例2：content=None 且无 reasoning_content -> 回退为 "" 不崩溃
    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_fake_empty_no_reasoning())
        MockClient.return_value.__aenter__.return_value = mock_client
        result = await RealLLMClient().chat([{"role": "user", "content": "你好"}], None)
    assert result["content"] == "", repr(result["content"])
    print("[OK] 用例2 content=None 且无 reasoning -> 安全回退为空串:", repr(result["content"]))

    # 用例3：base_agent 直接消费（router 才补 done，此处不断言 done）
    # 验证：content=None 不抛 TypeError；正常 content 能产出 content 事件
    from app.services.agents.base_agent import BaseAgent

    class FakeDB:
        def add(self, obj):
            pass

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

        async def execute(self, *a, **k):
            m = MagicMock()
            m.scalars.return_value.all.return_value = []
            return m

    # 3a：正常内容 -> 应产出 content 事件
    class FakeLLMNormal:
        async def chat(self, messages, tools=None):
            return {"content": "你好，我来帮你规划杭州行程。", "tool_calls": None}

    agent = BaseAgent("soa", "sys", tools=[])
    agent.llm = FakeLLMNormal()
    events = []
    async for chunk in agent.chat("u1", "你好", db=FakeDB()):
        events.append(chunk)
    assert any(e.get("type") == "content" for e in events), "正常 content 应产出 content 事件"
    print("[OK] 用例3a 正常 content 产出 content 事件数:", len(events))

    # 3b：content=None -> 不应在 re.findall 抛 TypeError（之前"发送成功但无输出"的根因）
    class FakeLLMNone:
        async def chat(self, messages, tools=None):
            return {"content": None, "tool_calls": None}

    agent.llm = FakeLLMNone()
    events_none = []
    async for chunk in agent.chat("u1", "你好", db=FakeDB()):
        events_none.append(chunk)
    # 空 content 不会产生 content 事件（交由 router 补 done），关键是迭代不抛异常
    print("[OK] 用例3b content=None 未崩溃，事件数:", len(events_none))
    print("ALL PASS ✅")


if __name__ == "__main__":
    asyncio.run(run())

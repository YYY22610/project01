"""LLM Client — Mock and real implementations.

When LLM_API_KEY is configured, uses the real API.
Otherwise, uses MockLLMClient that simulates responses based on keywords.
"""
import json
import asyncio
from typing import AsyncGenerator
from app.config import settings


class MockLLMClient:
    """Mock LLM that simulates responses based on keyword matching."""

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Return a mock response. Simulates tool calls based on keywords."""
        await asyncio.sleep(0.5)  # Simulate latency

        last_message = messages[-1]["content"].lower() if messages else ""

        # Simulate tool calls based on keywords
        if any(kw in last_message for kw in ["搜索", "查找", "景点", "推荐", "search"]):
            return {
                "content": "我来帮你搜索杭州的景点信息。",
                "tool_calls": [{
                    "id": "call_mock_1",
                    "function": {
                        "name": "search_attractions",
                        "arguments": json.dumps({"query": "杭州景点"})
                    }
                }]
            }
        elif any(kw in last_message for kw in ["文档", "word", "生成", "行程", "规划", "docx"]):
            return {
                "content": "我来帮你生成行程规划文档。",
                "tool_calls": [{
                    "id": "call_mock_2",
                    "function": {
                        "name": "generate_docx",
                        "arguments": json.dumps({
                            "title": "杭州三日游行程规划",
                            "content": "# 杭州三日游行程规划\n\n## 第一天\n- 上午：西湖风景区\n- 下午：灵隐寺\n- 晚上：河坊街\n\n## 第二天\n- 上午：千岛湖\n- 下午：宋城\n- 晚上：《宋城千古情》演出\n\n## 第三天\n- 上午：西溪湿地\n- 下午：龙井村\n- 晚上：返程"
                        })
                    }
                }]
            }
        elif any(kw in last_message for kw in ["提醒", "日历", "remind", "calendar"]):
            return {
                "content": "我来帮你设置旅行提醒。",
                "tool_calls": [{
                    "id": "call_mock_3",
                    "function": {
                        "name": "set_reminder",
                        "arguments": json.dumps({
                            "reminder_datetime": "2026-08-01T08:00:00",
                            "content": "出发前往杭州"
                        })
                    }
                }]
            }
        elif any(kw in last_message for kw in ["邮件", "发送", "email", "send"]):
            return {
                "content": "我来帮你发送行程邮件。",
                "tool_calls": [{
                    "id": "call_mock_4",
                    "function": {
                        "name": "send_email",
                        "arguments": json.dumps({
                            "to_email": settings.SENDER_EMAIL,
                            "subject": "杭州三日游行程规划",
                            "content": "请查收附件中的杭州三日游行程规划。"
                        })
                    }
                }]
            }
        else:
            return {
                "content": f"我理解你的需求：「{messages[-1]['content']}」。我可以帮你搜索景点、生成行程文档、设置提醒或发送邮件。请告诉我你需要什么帮助？",
                "tool_calls": None
            }


class RealLLMClient:
    """Real LLM client using OpenAI-compatible API."""

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.LLM_MODEL,
            "messages": messages,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.LLM_API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]["message"]
        return {
            "content": choice.get("content"),
            "tool_calls": choice.get("tool_calls"),
        }


def get_llm_client():
    """Factory: return Mock or Real LLM client based on config."""
    if settings.use_mock_llm:
        return MockLLMClient()
    return RealLLMClient()

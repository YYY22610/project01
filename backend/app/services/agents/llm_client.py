"""LLM Client — Mock and real implementations.

When LLM_API_KEY is configured, uses the real API.
Otherwise, uses MockLLMClient that simulates responses based on keywords.
"""
import json
import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- 限流保护
# DashScope(Qwen/OpenAI 兼容)有 QPS 限制，多个参与者同时对话时，
# 单次聊天 + MOA 群辩会短时间并发打出大量 LLM 请求，容易触发 429(限流)，
# 导致正在对话的参与者被中断——这会污染实验数据。
#
# 用「进程级信号量」把同时在飞的 LLM 请求数限制在安全阈值内：
# 超出的请求排队等待，而不是直接打上游被拒。
# 单实例部署下这是足够的（与 --workers 1 的约束一致）。
# ⚠️ 若将来改多实例部署，信号量不跨进程，需要换成 Redis 等共享限流器。
_llm_semaphore: asyncio.Semaphore | None = None
# 等待信号量的最长秒数：超过则快速失败，避免请求无限排队后超时。
_LLM_ACQUIRE_TIMEOUT = float(getattr(settings, "LLM_CONCURRENCY_WAIT_TIMEOUT", 180))


def _get_llm_semaphore() -> asyncio.Semaphore:
    """惰性创建 LLM 并发信号量（必须在事件循环内创建，故不能放模块导入期）。"""
    global _llm_semaphore
    if _llm_semaphore is None:
        limit = max(1, int(getattr(settings, "LLM_MAX_CONCURRENCY", 5)))
        _llm_semaphore = asyncio.Semaphore(limit)
        logger.info("LLM 并发限流已启用，最大并发=%d，等待超时=%ss", limit, _LLM_ACQUIRE_TIMEOUT)
    return _llm_semaphore


@asynccontextmanager
async def _llm_slot():
    """获取一个 LLM 调用许可；等待超时则抛出，调用方按现有错误路径返回友好提示。"""
    sem = _get_llm_semaphore()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=_LLM_ACQUIRE_TIMEOUT)
    except asyncio.TimeoutError:
        raise RuntimeError(
            "LLM 请求排队超时：当前并发较高，请稍后重试。"
        ) from None
    try:
        yield
    finally:
        sem.release()


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

    # 真实 Qwen/DashScope 偶发读取超时（httpx.ReadTimeout），重试可消化大部分瞬断。
    _TRANSIENT = (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.RemoteProtocolError)

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """对外入口：先过并发限流，再执行真实请求。

        限流在此处（而非 _chat_uncapped）统一生效，单助理 chat 与 MOA 群辩
        多 Agent 的每一次调用都会经过，排队时不会打断正在进行的对话。
        """
        async with _llm_slot():
            return await self._chat_uncapped(messages, tools)

    async def _chat_uncapped(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
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
        # Qwen3 系列默认开启长链「思考」，单次调用可达 100s+，整场规划 8 分钟，
        # 实时交互 UI 无法接受。规划类任务无需深度推理，对 qwen3 关闭思考以大幅降时延。
        # 仅对 qwen3 生效，其他模型不受影响；如需恢复思考可在 .env 改模型或此处调整。
        if settings.LLM_MODEL.startswith("qwen3"):
            # DashScope Qwen3 兼容接口：关闭长链思考以降低时延。
            # 官方对原生 HTTP(body 顶层)与 OpenAI SDK(extra_body)两种传法表述不一，
            # 这里两种都带上，确保至少一种被识别。
            payload["enable_thinking"] = False
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        last_err: Exception | None = None
        # 最多重试 3 次（首次 + 2 次重试），退避 1s / 2s，消化偶发网络超时。
        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    # 连接 10s，读取 120s（带思维链的模型首字较慢，给足余量）
                    response = await client.post(
                        f"{settings.LLM_API_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
                    )
                    if response.status_code != 200:
                        # Surface provider error detail so invalid-key / quota issues are diagnosable
                        raise RuntimeError(
                            f"LLM API error {response.status_code}: {response.text}"
                        )
                    data = response.json()
                    break
            except self._TRANSIENT as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise

        choice = data["choices"][0]["message"]
        raw_content = choice.get("content")
        reasoning = choice.get("reasoning_content")
        # Qwen3 / 带"思考"的模型常把正式回答放在 reasoning_content，content 可能为空串或 None；
        # 此处回退，避免真实模型返回空 content 导致前端收不到任何文本帧（"发送成功但无输出"）。
        content = raw_content or reasoning or ""
        return {
            "content": content,
            "tool_calls": choice.get("tool_calls"),
        }


def get_llm_client():
    """Factory: return Mock or Real LLM client based on config.

    决策顺序：
      1. 配置了 LLM_API_KEY → 真实模型；
      2. 未配置 Key 且 ALLOW_MOCK_LLM=true → Mock（开发/自测）；
      3. 未配置 Key 且 ALLOW_MOCK_LLM=false → 拒绝（实验模式禁止 Mock，
         启动期已拦截，此处再兜底一次，避免运行时意外回退到 Mock）。
    """
    if settings.use_mock_llm:
        if not settings.ALLOW_MOCK_LLM:
            raise RuntimeError(
                "ALLOW_MOCK_LLM=false（实验模式禁止 Mock LLM），但 LLM_API_KEY 为空；"
                "请配置真实 LLM_API_KEY，勿用 Mock 收实验数据。"
            )
        return MockLLMClient()
    return RealLLMClient()

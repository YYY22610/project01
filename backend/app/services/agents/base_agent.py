"""Base agent — core LLM chat loop with Function Calling."""
import json
import re
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.llm_client import get_llm_client
from app.services.agents.tools.agent_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_tool_status_label,
)
from app.models.chat_message import ChatMessage


class BaseAgent:
    """Base AI agent with LLM chat loop and tool calling."""

    def __init__(self, agent_id: str, system_prompt: str, tools: list[str] | None = None):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.llm = get_llm_client()

        # Filter tool definitions based on agent's tool list
        self.tool_defs = [
            t for t in TOOL_DEFINITIONS if t["name"] in self.tools
        ] if self.tools else TOOL_DEFINITIONS

    async def chat(
        self,
        user_id: str,
        message: str,
        db: AsyncSession,
        cancel_check: "callable[[], bool] | None" = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Chat with the agent. Yields SSE events as dict chunks.
        Flow: user message → LLM → (tool_call → execute → LLM)* → final response

        :param cancel_check: 返回 True 表示参与者已请求中断本轮，命中则立即终止
                              （用于干预能力：参与者随时中断助理当前操作）。
        """
        async def _is_cancelled() -> bool:
            # cancel_check 在 router 中传入的是 async 协程（查询取消标志），
            # 必须 await 才能得到真实布尔值，否则拿到的是 coroutine（恒为 truthy）。
            if not cancel_check:
                return False
            return bool(await cancel_check())

        # 1. Save user message
        user_msg = ChatMessage(
            user_id=user_id,
            agent_id=self.agent_id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        await db.flush()

        # 2. Build message history
        messages = [{"role": "system", "content": self.system_prompt}]

        # Load recent history (last 10 messages)
        from sqlalchemy import select
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id, ChatMessage.agent_id == self.agent_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history = list(reversed(result.scalars().all()))
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content or ""})

        # 3. Call LLM
        llm_response = await self.llm.chat(messages, self.tool_defs)

        # 4. Handle tool calls
        tool_calls = llm_response.get("tool_calls")
        generated_doc_url: str | None = None
        generated_doc_name: str | None = None
        if tool_calls:
            # 干预检查点①：首轮 LLM 返回后、执行任何工具前
            if await _is_cancelled():
                yield {"type": "cancelled", "data": {
                    "message": "操作已被你中断，可重新下达指令。"
                }}
                return

            # 收集所有工具执行结果，统一构造 function-calling 历史消息
            tool_results = []
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])

                # 干预检查点②：每个工具执行前
                if await _is_cancelled():
                    yield {"type": "cancelled", "data": {
                        "message": "操作已被你中断，可重新下达指令。"
                    }}
                    return

                yield {"type": "tool_call", "data": {
                    "tool": func_name,
                    "status": get_tool_status_label(func_name, "calling"),
                    "arguments": func_args,
                }}

                # Execute tool
                tool_result = await execute_tool(func_name, func_args, user_id=user_id)

                # 若本轮生成了 Word 文档，记录下载链接以便后续追加到回复中
                if func_name == "generate_docx" and tool_result.get("download_url"):
                    generated_doc_url = tool_result["download_url"]
                    generated_doc_name = tool_result.get("file_name", "行程文档.docx")

                yield {"type": "tool_result", "data": {
                    "tool": func_name,
                    "status": get_tool_status_label(func_name, "done"),
                    "result": tool_result,
                }}

                tool_results.append({"tool_call": tc, "result": tool_result})

            # Add tool calls and results to messages with proper OpenAI function-calling format.
            # Each tool result must reference the tool_call_id, otherwise the model cannot
            # associate results with calls and will return empty content (e.g. moa_b showing
            # "预算计算完成" but no natural-language reply).
            messages.append({
                "role": "assistant",
                "content": llm_response.get("content") or "",
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
            for item in tool_results:
                tc = item["tool_call"]
                tool_result = item["result"]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

            # 干预检查点③：二次 LLM 调用（生成最终答复）前
            if await _is_cancelled():
                yield {"type": "cancelled", "data": {
                    "message": "操作已被你中断，可重新下达指令。"
                }}
                return

            # Second LLM call with tool results
            llm_response2 = await self.llm.chat(messages, None)
            final_content = llm_response2.get("content") or "操作完成。"
        else:
            final_content = llm_response.get("content") or ""

        # 若本轮生成了 Word 文档，在最终回复末尾追加可点击的下载链接，
        # 确保用户能真正看到并下载该文档，而不是只看到一个文件名。
        # 去重：按 download_url 判断 LLM 是否已在回复里给出过链接，避免重复两行。
        if generated_doc_url and generated_doc_name and generated_doc_url not in (final_content or ""):
            suffix = (
                f"\n\n---\n\n"
                f"📄 **行程文档已生成**：[点击下载 `{generated_doc_name}`]({generated_doc_url})"
            )
            final_content += suffix

        # 5. Stream content while preserving newlines/Markdown structure.
        # Split into "words" and "whitespace" tokens so \n\n paragraph breaks are not lost.
        # Emit each token exactly as-is — whitespace tokens already contain the needed spaces/newlines.
        tokens = re.findall(r"\S+|\s+", final_content)
        for token in tokens:
            yield {"type": "content", "data": token}

        # 6. Save assistant message
        assistant_msg = ChatMessage(
            user_id=user_id,
            agent_id=self.agent_id,
            role="assistant",
            content=final_content,
            tool_calls={"tool_calls": tool_calls} if tool_calls else None,
        )
        db.add(assistant_msg)
        await db.commit()

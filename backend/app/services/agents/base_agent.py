"""Base agent — core LLM chat loop with Function Calling."""
import json
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.llm_client import get_llm_client
from app.services.agents.tools.agent_tools import TOOL_DEFINITIONS, execute_tool
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
        self, user_id: str, message: str, db: AsyncSession
    ) -> AsyncGenerator[dict, None]:
        """
        Chat with the agent. Yields SSE events as dict chunks.
        Flow: user message → LLM → (tool_call → execute → LLM)* → final response
        """
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
        if tool_calls:
            # Yield tool_call event
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])

                yield {"type": "tool_call", "data": {
                    "tool": func_name,
                    "arguments": func_args,
                }}

                # Execute tool
                tool_result = await execute_tool(func_name, func_args)

                yield {"type": "tool_result", "data": {
                    "tool": func_name,
                    "result": tool_result,
                }}

                # Add tool result to messages and call LLM again
                messages.append({"role": "assistant", "content": llm_response.get("content", "")})
                messages.append({"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)})

            # Second LLM call with tool results
            llm_response2 = await self.llm.chat(messages, None)
            final_content = llm_response2.get("content", "操作完成。")
        else:
            final_content = llm_response.get("content", "")

        # 5. Stream content (simulated word-by-word for Mock)
        words = final_content.split()
        for i, word in enumerate(words):
            if i == 0:
                yield {"type": "content", "data": word}
            else:
                yield {"type": "content", "data": " " + word}

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

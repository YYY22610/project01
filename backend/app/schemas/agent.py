"""Pydantic schemas for agent chat and SSE."""
from pydantic import BaseModel
from typing import Optional, Any


class ChatRequest(BaseModel):
    agent_id: str = "soa"  # soa / moa_a / moa_b
    message: str


class CancelRequest(BaseModel):
    agent_id: str = "soa"  # 要中断的助理 ID


class GroupDiscussRequest(BaseModel):
    """MOA 组多角色群辩讨论请求。"""
    message: str
    dest: str = "杭州"
    days: int = 3
    budget: int = 2000
    travelers: str = "1 人"


class ChatMessageResponse(BaseModel):
    id: str
    agent_id: str
    role: str
    content: Optional[str] = None
    tool_calls: Optional[dict] = None
    created_at: str


class SSEEvent(BaseModel):
    event: str  # status / content / tool_call / error / done
    data: Any

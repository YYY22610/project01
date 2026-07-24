"""Pydantic schemas for agent chat and SSE."""
from pydantic import BaseModel
from typing import Optional, Any


class ChatRequest(BaseModel):
    agent_id: str = "soa"  # soa / moa_a / moa_b / moa_c
    message: str


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

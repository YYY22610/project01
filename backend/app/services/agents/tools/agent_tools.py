"""Agent tool functions — callable by AI agents via Function Calling."""
import json
import os
from datetime import datetime
from typing import AsyncGenerator

from app.services.document_service import generate_docx as _generate_docx
from app.services.email_service import send_email as _send_email
from app.config import settings

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads", "documents")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Tool definitions for LLM Function Calling
TOOL_DEFINITIONS = [
    {
        "name": "search_attractions",
        "description": "搜索旅游景点信息",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "generate_docx",
        "description": "生成行程规划Word文档",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "文档标题"},
                "content": {"type": "string", "description": "文档内容(支持Markdown格式)"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "calculate_budget",
        "description": "计算旅行预算",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "旅行天数"},
                "daily_budget": {"type": "number", "description": "每日预算(元)"}
            },
            "required": ["days", "daily_budget"]
        }
    },
    {
        "name": "set_reminder",
        "description": "设置旅行提醒",
        "parameters": {
            "type": "object",
            "properties": {
                "reminder_datetime": {"type": "string", "description": "提醒时间(ISO格式)"},
                "content": {"type": "string", "description": "提醒内容"}
            },
            "required": ["reminder_datetime", "content"]
        }
    },
    {
        "name": "send_email",
        "description": "发送行程邮件",
        "parameters": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string", "description": "收件人邮箱"},
                "subject": {"type": "string", "description": "邮件主题"},
                "content": {"type": "string", "description": "邮件内容"}
            },
            "required": ["to_email", "subject", "content"]
        }
    },
]


async def search_attractions(query: str) -> dict:
    """Search for attractions (uses mock data for now)."""
    from app.routers.search import MOCK_RESULTS
    filtered = [
        {"title": r.title, "url": r.url, "snippet": r.snippet}
        for r in MOCK_RESULTS
        if any(kw in r.title or kw in r.snippet for kw in query.split() if len(kw) > 1)
    ] or [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in MOCK_RESULTS[:5]]
    return {"results": filtered, "total": len(filtered)}


async def generate_docx_tool(title: str, content: str) -> dict:
    """Generate a .docx file."""
    file_name = f"agent_generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    _generate_docx(file_path, title, content)
    return {"file_path": file_path, "file_name": file_name, "status": "generated"}


async def calculate_budget_tool(days: int, daily_budget: float) -> dict:
    """Calculate travel budget."""
    total = days * daily_budget
    breakdown = {
        "days": days,
        "daily_budget": daily_budget,
        "total": total,
        "suggestion": "预算充足" if total <= 1000 else "预算可能超出，建议调整"
    }
    return breakdown


async def set_reminder_tool(reminder_datetime: str, content: str) -> dict:
    """Set a reminder (mock for now — actual reminder stored in DB by agent)."""
    return {
        "status": "set",
        "reminder_datetime": reminder_datetime,
        "content": content
    }


async def send_email_tool(to_email: str, subject: str, content: str) -> dict:
    """Send an email."""
    result = _send_email(to_email, subject, content)
    return result


# Tool execution dispatcher
TOOL_EXECUTORS = {
    "search_attractions": search_attractions,
    "generate_docx": generate_docx_tool,
    "calculate_budget": calculate_budget_tool,
    "set_reminder": set_reminder_tool,
    "send_email": send_email_tool,
}


async def execute_tool(tool_name: str, arguments: dict) -> dict:
    """Execute a tool by name with the given arguments."""
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return await executor(**arguments)
    except Exception as e:
        return {"error": str(e)}

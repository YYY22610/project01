"""Agent tool functions — callable by AI agents via Function Calling."""
import inspect
import json
import os
from datetime import datetime
from typing import AsyncGenerator

from app.services.document_service import generate_docx as _generate_docx
from app.services.email_service import send_email as _send_email
from app.config import settings

# 必须与 app/routers/document.py 的 UPLOAD_DIR 保持一致（backend/uploads/documents），
# 否则 AI 生成的文件无法被 /api/document/download 找到而报 404。
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "documents")
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
    """Generate a .docx file and return a download URL."""
    file_name = f"agent_generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    _generate_docx(file_path, title, content)
    return {
        "file_path": file_path,
        "file_name": file_name,
        "status": "generated",
        "download_url": f"/api/document/download/{file_name}",
    }


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


async def set_reminder_tool(reminder_datetime: str, content: str, user_id: str | None = None) -> dict:
    """设置行程提醒：记录到数据库，到期后由后台调度器自动向用户注册邮箱发送提醒邮件。"""
    try:
        from app.services.reminder_service import create_reminder
        reminder = await create_reminder(user_id, reminder_datetime, content)
        return {
            "status": "set",
            "reminder_id": str(reminder.id),
            "reminder_datetime": reminder.reminder_datetime.isoformat(),
            "content": content,
            "note": "已保存，将在该时间自动发送提醒邮件到您的注册邮箱",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


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


async def execute_tool(tool_name: str, arguments: dict, user_id: str | None = None) -> dict:
    """Execute a tool by name with the given arguments.

    user_id 透传给签名中声明了该参数的工具（如 set_reminder 需要归属用户）。
    其余工具忽略该参数，避免 unexpected keyword argument 报错。
    """
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        kwargs = dict(arguments)
        sig = inspect.signature(executor)
        if "user_id" in sig.parameters and user_id is not None:
            kwargs["user_id"] = user_id
        return await executor(**kwargs)
    except Exception as e:
        return {"error": str(e)}


# 工具调用时向用户展示的中文状态文案（用于前端实时状态日志）
# calling = 正在调用时显示；done = 调用完成后显示
TOOL_STATUS_LABELS = {
    "search_attractions": {
        "calling": "正在调用搜索引擎，检索景点信息…",
        "done": "已检索到景点信息",
    },
    "generate_docx": {
        "calling": "正在生成行程规划 Word 文档…",
        "done": "Word 文档已生成",
    },
    "calculate_budget": {
        "calling": "正在计算旅行预算…",
        "done": "预算计算完成",
    },
    "set_reminder": {
        "calling": "正在设置行程提醒…",
        "done": "行程提醒已设置",
    },
    "send_email": {
        "calling": "正在发送行程邮件…",
        "done": "邮件已发送",
    },
}


def get_tool_status_label(tool_name: str, phase: str) -> str:
    """返回工具在调用中(calling)或完成(done)阶段的中文状态文案。"""
    labels = TOOL_STATUS_LABELS.get(tool_name)
    if not labels:
        return "正在执行操作…" if phase == "calling" else "操作完成"
    return labels.get(phase, "正在执行操作…" if phase == "calling" else "操作完成")

"""Pydantic schemas for task-related operations."""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskConfigResponse(BaseModel):
    task_days: int
    task_budget: int
    target_email: str
    destination: str
    sub_tasks: list[str]


class DemoCompleteRequest(BaseModel):
    watch_seconds: Optional[int] = None


class TaskStartResponse(BaseModel):
    task_id: str
    started_at: datetime
    deadline: datetime


class TaskSubmitRequest(BaseModel):
    task1_search: bool = False
    task2_document: bool = False
    task3_reminder: bool = False
    task4_email: bool = False
    docx_file_path: Optional[str] = None
    reminder_datetime: Optional[datetime] = None
    email_status: Optional[str] = None
    email_recipient: Optional[str] = None


class TaskSubmitResponse(BaseModel):
    task_id: str
    submitted_at: datetime
    duration_ms: int
    all_completed: bool


class SearchRequest(BaseModel):
    query: str
    page: int = 1


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "search_engine"  # search_engine | mock | ai


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int


class DocumentGenerateRequest(BaseModel):
    title: str = "杭州三日游行程规划"
    content: str
    format: str = "text"  # 'text' | 'html'


class DocumentResponse(BaseModel):
    file_path: str
    file_name: str


class ReminderSetRequest(BaseModel):
    reminder_datetime: datetime
    content: str = ""


class ReminderResponse(BaseModel):
    id: str
    reminder_datetime: datetime
    content: str
    is_set: bool


class EmailSendResponse(BaseModel):
    status: str  # sent / failed
    message_id: Optional[str] = None

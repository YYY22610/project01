"""Behavior log model — all user actions tracked for analysis."""
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, Integer, func, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActionType(str, enum.Enum):
    """16 types of user actions tracked."""
    PAGE_VIEW = "page_view"
    SEARCH_QUERY = "search_query"
    SEARCH_RESULT_CLICK = "search_result_click"
    DOCUMENT_EDIT = "document_edit"
    DOCUMENT_SAVE = "document_save"
    DOCUMENT_DOWNLOAD = "document_download"
    REMINDER_SET = "reminder_set"
    REMINDER_CANCEL = "reminder_cancel"
    EMAIL_SEND = "email_send"
    AGENT_MESSAGE = "agent_message"
    AGENT_TOOL_CALL = "agent_tool_call"
    CHECKLIST_TOGGLE = "checklist_toggle"
    TASK_START = "task_start"
    TASK_SUBMIT = "task_submit"
    DEMO_VIEW = "demo_view"
    QUESTIONNAIRE_SUBMIT = "questionnaire_submit"


class BehaviorLog(Base):
    __tablename__ = "behavior_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    group: Mapped[str | None] = mapped_column(String(10), name="group", nullable=True, index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    action_type: Mapped[ActionType] = mapped_column(SAEnum(ActionType), nullable=False, index=True)
    action_target: Mapped[str | None] = mapped_column(String(500), nullable=True)

    input_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    page_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # --- Enriched fields (design "七" completeness) ---
    # Performance / outcome
    request_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Session metadata
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screen_resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    experiment_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Task / decision process
    phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    manual_edit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_plan_submit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Information retrieval behavior
    results_viewed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_view_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicked_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # AI interaction behavior
    user_action_on_ai: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_suggestion_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_suggestion_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ai_interaction_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationship
    user = relationship("User", back_populates="behavior_logs")

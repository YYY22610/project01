"""Task submission model — tracks completion of 4 sub-tasks."""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # 4 sub-tasks
    task1_search: Mapped[bool] = mapped_column(Boolean, default=False)
    task2_document: Mapped[bool] = mapped_column(Boolean, default=False)
    task3_reminder: Mapped[bool] = mapped_column(Boolean, default=False)
    task4_email: Mapped[bool] = mapped_column(Boolean, default=False)

    # Artifacts
    docx_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reminder_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # sent/failed/pending
    email_recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="task_submissions")

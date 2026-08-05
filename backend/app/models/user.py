"""User model — participants + group assignment + experiment state machine."""
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExperimentGroup(str, enum.Enum):
    H = "H"           # 纯人工组
    SOA = "SOA"       # 单AI助理组
    MOA = "MOA"       # 多AI助理组


class UserStatus(str, enum.Enum):
    REGISTERED = "registered"        # 已注册，未签署同意书
    CONSENTED = "consented"          # 已签同意书
    DEMO_COMPLETED = "demo_completed"  # 已看演示
    TASK_IN_PROGRESS = "task_in_progress"  # 任务进行中
    TASK_COMPLETED = "task_completed"      # 任务已完成
    QUESTIONNAIRE_COMPLETED = "questionnaire_completed"  # 问卷已完成


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Group assignment (single-blind: frontend never sees this directly)
    # "group" is a SQL reserved word in PostgreSQL, must quote the column name
    group: Mapped[ExperimentGroup | None] = mapped_column(
        SAEnum(ExperimentGroup, name="experiment_group"), name="group", nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus), default=UserStatus.REGISTERED
    )

    # Demographics
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    education: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tech_frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_experience: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Demo
    demo_watch_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Session tracking
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    behavior_logs = relationship("BehaviorLog", back_populates="user", cascade="all, delete-orphan")
    task_submissions = relationship("TaskSubmission", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    questionnaire_responses = relationship("QuestionnaireResponse", back_populates="user", cascade="all, delete-orphan")
    admin_scores = relationship("AdminScore", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")

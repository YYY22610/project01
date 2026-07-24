"""Questionnaire item and response models."""
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuestionConstruct(str, enum.Enum):
    """6 constructs measured by the questionnaire (aligned with research model)."""
    TRUST = "trust"                    # 感知信任
    AUTONOMY = "autonomy"              # 感知自主性
    SATISFACTION = "satisfaction"      # 满意度
    TASK_LOAD = "task_load"            # 任务负荷 (NASA-TLX)
    FUTURE_USE = "future_use"          # 未来使用意愿
    MANIPULATION_CHECK = "manipulation_check"  # 操纵检验


class QuestionType(str, enum.Enum):
    likert = "likert"  # Likert量表
    choice = "choice"  # 单选
    text = "text"      # 文本


class QuestionnaireItem(Base):
    __tablename__ = "questionnaire_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    construct: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType), default=QuestionType.likert)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scale_level: Mapped[int] = mapped_column(Integer, default=5)  # 5-point or 7-point Likert
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    # 适用性分组：逗号分隔的组列表（如 "SOA,MOA"）；NULL / "ALL" 表示适用于所有组
    # 用于单盲设计下按实验组展示不同问卷（H 组改写为"工具/方法"评价，SOA/MOA 保留 AI 助理相关表述）
    applicable_groups: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    responses = relationship("QuestionnaireResponse", back_populates="item")


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("questionnaire_items.id"), nullable=False)
    response_value: Mapped[str] = mapped_column(Text, nullable=False)  # Can be int (Likert) or text

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="questionnaire_responses")
    item = relationship("QuestionnaireItem", back_populates="responses")

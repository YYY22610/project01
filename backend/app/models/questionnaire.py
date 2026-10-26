"""Questionnaire item and response models."""
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuestionPhase(str, enum.Enum):
    """Questionnaire stage. Replaces the old hardcoded pre-survey in Consent.tsx.

    PRE  — 前置问卷，知情同意页作答（POST /api/auth/consent）
    POST — 后置问卷，任务完成后作答（POST /api/questionnaire/submit）
    """
    PRE = "pre"
    POST = "post"


class QuestionConstruct(str, enum.Enum):
    """Constructs measured by the 2026-10-14 questionnaire.

    Naming note: values are snake_case slugs stored in questionnaire_items.construct
    (widened to VARCHAR(64) in migrate_questionnaire_v2.sql — the old VARCHAR(20)
    could not hold e.g. "performance_expectancy"). Chinese labels live in
    frontend/src/constants/questionnaire.ts (CONSTRUCT_LABELS) and in
    admin.py QUESTIONNAIRE_CONSTRUCT_LABELS (export column headers); keep in sync.

    The enum is intentionally *not* used as the column type (construct is a plain
    String) so that admin-created items never fail on an unknown slug.
    """
    # —— 前置问卷：人口统计与 AI 使用背景 ——
    DEMOGRAPHIC = "demographic"
    AI_EXPERIENCE = "ai_experience"
    AGENT_AWARENESS = "agent_awareness"
    # —— 前置问卷：核心构念 ——
    SOCIAL_INFLUENCE = "social_influence"      # 社会影响
    ANTHROPOMORPHISM = "anthropomorphism"      # 感知拟人化
    # —— 后置问卷：核心构念 ——
    HEDONIC_MOTIVATION = "hedonic_motivation"          # 享乐动机
    PERFORMANCE_EXPECTANCY = "performance_expectancy"  # 绩效期望
    EFFORT_EXPECTANCY = "effort_expectancy"            # 努力期望
    PERCEIVED_RISK = "perceived_risk"                  # 感知风险
    AFFECTIVE_EXPERIENCE = "affective_experience"      # 情绪体验（双极量表）
    ACCEPTANCE_INTENTION = "acceptance_intention"      # 接受意愿
    RESISTANCE_INTENTION = "resistance_intention"      # 拒绝意愿
    # —— 通用 ——
    MANIPULATION_CHECK = "manipulation_check"  # 操纵检验
    OPEN_FEEDBACK = "open_feedback"            # 开放题


class QuestionType(str, enum.Enum):
    likert = "likert"        # Likert 量表（含双极，锚点存在 options 里）
    multiple = "multiple"    # 多选题
    choice = "choice"        # 单选
    text = "text"            # 开放填空


class QuestionnaireItem(Base):
    __tablename__ = "questionnaire_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    construct: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(SAEnum(QuestionType), default=QuestionType.likert)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scale_level: Mapped[int] = mapped_column(Integer, default=5)  # 5-point or 7-point Likert
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    # 适用性分组：逗号分隔的组列表（如 "H,MOA"）；NULL / "ALL" 表示适用于所有组
    # 2026-10-14 版问卷全部统一措辞（靠指导语处理未使用助理的被试），故一律写 "ALL"；
    # 字段保留是为了管理后台仍可按组过滤，以及未来恢复分组措辞时无需再迁移。
    applicable_groups: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 前置 / 后置问卷。存量数据默认 post（与改造前语义一致）。
    phase: Mapped[str] = mapped_column(
        String(10), default=QuestionPhase.POST, server_default="post", index=True
    )
    # 反向计分题：聚合求均值时按 (scale_level + 1 - x) 翻转，单题原始分不变。
    is_reverse: Mapped[bool] = mapped_column(default=False, server_default="false")
    # 题组指导语：渲染为题干上方的提示段落，不参与作答。
    section_note: Mapped[str | None] = mapped_column(Text, nullable=True)

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

"""MOA 组群聊会话持久化：每用户一行上下文快照，刷新恢复 + 用户隔离。"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MoaGroupSession(Base):
    """每用户一条群聊上下文（消息/方案/阶段），JSONB 快照，按 user_id 天然隔离。

    context:      前端保存的完整快照（权威，PUT 覆盖）
    server_stage: 后端在 SSE 关键节点（await_user/await_confirm/done）自动写的阶段标记，
                  供「前端未保存时」兜底提示，不覆盖 context。
    """

    __tablename__ = "moa_group_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    # 上下文快照：{messages, plan, stage, stageLabel, started, savedAt}
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 后端阶段标记：{stage, label, ts}
    server_stage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

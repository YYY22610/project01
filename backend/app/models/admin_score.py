"""Admin score model — researcher scoring of task submissions.

Scoring follows an 8-factor, 100-point scheme derived from GB/T 18972-2017
(旅游资源分类、调查与评价): 7 weighted value factors (each scored 0-10) plus
an eco/environmental adjustment (-5~+3). The weighted sum of the 7 factors is
0-100; the eco adjustment shifts it within [-5, +3] and the final total is
clamped to the 0-100 range.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# 8 因子权重（GB/T 18972-2017 派生），正权重合计 100
FACTOR_WEIGHTS = {
    "scenic": 30,     # 观赏游憩价值
    "historic": 25,   # 历史文化价值
    "rarity": 15,     # 珍稀奇特程度
    "scale": 10,      # 规模与体量
    "integrity": 5,   # 完整性
    "fame": 10,       # 知名度 / 影响力
    "season": 5,      # 适游期 / 使用范围
}

# 环保附加值取值范围
ECO_MIN, ECO_MAX = -5, 3

FACTOR_FIELDS = (
    "scenic_score", "historic_score", "rarity_score", "scale_score",
    "integrity_score", "fame_score", "season_score",
)


def compute_total(scenic, historic, rarity, scale, integrity, fame, season, eco) -> int | None:
    """Compute the 0-100 total from 8 factor scores.

    Returns None if any of the 7 value factors is missing.
    """
    values = [scenic, historic, rarity, scale, integrity, fame, season]
    if any(v is None for v in values):
        return None
    weighted = sum((v or 0) * FACTOR_WEIGHTS[k] / 10 for v, k in zip(values, FACTOR_WEIGHTS))
    eco_val = eco if eco is not None else 0
    total = weighted + eco_val
    return max(0, min(100, int(round(total))))


class AdminScore(Base):
    __tablename__ = "admin_scores"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # 8-factor scoring (each value factor 0-10; eco adjustment -5..+3)
    scenic_score: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 观赏游憩价值 (30)
    historic_score: Mapped[int | None] = mapped_column(Integer, nullable=True)     # 历史文化价值 (25)
    rarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 珍稀奇特程度 (15)
    scale_score: Mapped[int | None] = mapped_column(Integer, nullable=True)        # 规模与体量 (10)
    integrity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 完整性 (5)
    fame_score: Mapped[int | None] = mapped_column(Integer, nullable=True)         # 知名度/影响力 (10)
    season_score: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 适游期 (5)
    eco_score: Mapped[int | None] = mapped_column(Integer, nullable=True)          # 环保附加值 (-5~+3)

    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)        # 汇总 0-100 (clamp)

    # 兼容旧字段（保留，历史数据可追溯）
    rationality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    scored_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="admin_scores")

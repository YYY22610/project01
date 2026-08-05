"""Pydantic schemas for behavior logs and admin operations."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class BehaviorLogCreate(BaseModel):
    action_type: str
    action_target: Optional[str] = None
    input_content: Optional[str] = None
    ai_response: Optional[str] = None
    agent_id: Optional[str] = None
    page_path: Optional[str] = None
    extra_data: Optional[dict] = None
    # Enriched fields
    request_latency_ms: Optional[int] = None
    is_success: Optional[bool] = None
    error_detail: Optional[str] = None
    user_agent: Optional[str] = None
    screen_resolution: Optional[str] = None
    experiment_version: Optional[str] = None
    session_start_time: Optional[datetime] = None
    phase: Optional[str] = None
    manual_edit_count: Optional[int] = None
    final_plan_submit_time: Optional[datetime] = None
    results_viewed: Optional[int] = None
    result_view_duration_ms: Optional[int] = None
    clicked_item_id: Optional[str] = None
    user_action_on_ai: Optional[str] = None
    ai_suggestion_id: Optional[str] = None
    ai_suggestion_type: Optional[str] = None
    ai_interaction_rounds: Optional[int] = None


class BehaviorLogBatchCreate(BaseModel):
    logs: list[BehaviorLogCreate]


class BehaviorLogResponse(BaseModel):
    id: str
    user_id: str
    group: Optional[str]
    timestamp: datetime
    action_type: str
    action_target: Optional[str]
    input_content: Optional[str]
    ai_response: Optional[str]
    agent_id: Optional[str]
    page_path: Optional[str]
    extra_data: Optional[dict]
    # Enriched fields
    request_latency_ms: Optional[int] = None
    is_success: Optional[bool] = None
    error_detail: Optional[str] = None
    user_agent: Optional[str] = None
    screen_resolution: Optional[str] = None
    experiment_version: Optional[str] = None
    session_start_time: Optional[datetime] = None
    phase: Optional[str] = None
    manual_edit_count: Optional[int] = None
    final_plan_submit_time: Optional[datetime] = None
    results_viewed: Optional[int] = None
    result_view_duration_ms: Optional[int] = None
    clicked_item_id: Optional[str] = None
    user_action_on_ai: Optional[str] = None
    ai_suggestion_id: Optional[str] = None
    ai_suggestion_type: Optional[str] = None
    ai_interaction_rounds: Optional[int] = None


class AdminScoreRequest(BaseModel):
    """8-factor, 100-point scoring scheme derived from GB/T 18972-2017.

    Seven value factors are each scored 0-10; an eco/environmental adjustment
    ranges -5..+3. The weighted sum of the 7 factors (weights sum to 100) plus
    the eco adjustment yields the 0-100 total (clamped).
    """
    scenic_score: Optional[int] = Field(default=None, ge=0, le=10)
    historic_score: Optional[int] = Field(default=None, ge=0, le=10)
    rarity_score: Optional[int] = Field(default=None, ge=0, le=10)
    scale_score: Optional[int] = Field(default=None, ge=0, le=10)
    integrity_score: Optional[int] = Field(default=None, ge=0, le=10)
    fame_score: Optional[int] = Field(default=None, ge=0, le=10)
    season_score: Optional[int] = Field(default=None, ge=0, le=10)
    eco_score: Optional[int] = Field(default=None, ge=-5, le=3)
    # 综合完成质量评分（研究员主观评价，1-10 分制，需求5.2）
    quality_score: Optional[int] = Field(default=None, ge=0, le=10)
    # 提醒正确性（研究员人工判定，需求5.1.2 选C）
    reminder_correct: Optional[bool] = None
    notes: Optional[str] = None


class SystemConfigUpdate(BaseModel):
    key: str
    value: str


class OpenClawStatus(BaseModel):
    """OpenClaw (AI agent service) runtime monitoring."""
    status: str = "unknown"          # ok | degraded | down | paused
    paused: bool = False
    total_calls: int = 0
    success_rate: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    recent_failures: int = 0


class DashboardStats(BaseModel):
    total_participants: int = 0
    group_distribution: dict = Field(default_factory=dict)
    experiment_status: str = "stopped"
    completion_rate: float = 0.0
    avg_duration_ms: Optional[float] = None
    api_status: dict = Field(default_factory=dict)
    openclaw_status: OpenClawStatus = Field(default_factory=OpenClawStatus)
    recent_registrations: list = Field(default_factory=list)
    abnormal_count: int = 0
    target_sample: int = 100

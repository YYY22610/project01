"""Behavior log router: batch insert logs asynchronously."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.behavior_log import BehaviorLog, ActionType
from app.schemas.common import BehaviorLogBatchCreate, BehaviorLogResponse

router = APIRouter()

# 各字符串列的长度上限（与 behavior_log.py 模型保持一致），超长时截断，
# 避免单条日志因 StringDataRightTruncation 导致整批 500（前端每 5s 上报，必须容错）。
_STR_LIMITS = {
    "group": 10,
    "action_target": 500,
    "agent_id": 50,
    "page_path": 200,
    "session_id": 100,
    "error_detail": None,  # Text，不限
    "user_agent": 255,
    "screen_resolution": 20,
    "experiment_version": 20,
    "phase": 30,
    "clicked_item_id": 100,
    "user_action_on_ai": 20,
    "ai_suggestion_id": 50,
    "ai_suggestion_type": 30,
}


def _safe(v, limit):
    if v is None:
        return None
    if isinstance(v, str) and limit and len(v) > limit:
        return v[:limit]
    return v


@router.post("/batch")
async def batch_create_logs(
    req: BehaviorLogBatchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch insert behavior logs (called by frontend every 5 seconds).

    单条日志写入失败（如字段超长、约束冲突）时仅跳过该条，不中断整批、不返回 500，
    保证前端行为日志上报始终成功。
    """
    created = 0
    failed = 0
    for log_data in req.logs:
        try:
            action_type = ActionType(log_data.action_type)
        except (ValueError, TypeError):
            failed += 1
            continue  # Skip unknown action types

        try:
            log = BehaviorLog(
                user_id=user.id,
                group=_safe(user.group.value if user.group else None, _STR_LIMITS["group"]),
                action_type=action_type,
                action_target=_safe(log_data.action_target, _STR_LIMITS["action_target"]),
                input_content=_safe(log_data.input_content, None),
                ai_response=_safe(log_data.ai_response, None),
                agent_id=_safe(log_data.agent_id, _STR_LIMITS["agent_id"]),
                page_path=_safe(log_data.page_path, _STR_LIMITS["page_path"]),
                session_id=_safe(user.session_id, _STR_LIMITS["session_id"]),
                extra_data=log_data.extra_data,
                request_latency_ms=log_data.request_latency_ms,
                is_success=log_data.is_success,
                error_detail=_safe(log_data.error_detail, None),
                user_agent=_safe(log_data.user_agent, _STR_LIMITS["user_agent"]),
                screen_resolution=_safe(log_data.screen_resolution, _STR_LIMITS["screen_resolution"]),
                experiment_version=_safe(log_data.experiment_version, _STR_LIMITS["experiment_version"]),
                session_start_time=log_data.session_start_time,
                phase=_safe(log_data.phase, _STR_LIMITS["phase"]),
                manual_edit_count=log_data.manual_edit_count,
                final_plan_submit_time=log_data.final_plan_submit_time,
                results_viewed=log_data.results_viewed,
                result_view_duration_ms=log_data.result_view_duration_ms,
                clicked_item_id=_safe(log_data.clicked_item_id, _STR_LIMITS["clicked_item_id"]),
                user_action_on_ai=_safe(log_data.user_action_on_ai, _STR_LIMITS["user_action_on_ai"]),
                ai_suggestion_id=_safe(log_data.ai_suggestion_id, _STR_LIMITS["ai_suggestion_id"]),
                ai_suggestion_type=_safe(log_data.ai_suggestion_type, _STR_LIMITS["ai_suggestion_type"]),
                ai_interaction_rounds=log_data.ai_interaction_rounds,
            )
            db.add(log)
            created += 1
        except Exception:
            # 任何单条构造/约束异常都只跳过本条，不影响其它日志与整体响应
            failed += 1
            await db.rollback()
            continue

    await db.commit()
    return {"created": created, "failed": failed, "status": "ok"}


@router.get("")
async def list_logs(
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's behavior logs (for admin view)."""
    from sqlalchemy import func, select

    count_result = await db.execute(
        select(func.count(BehaviorLog.id)).where(BehaviorLog.user_id == user.id)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(BehaviorLog)
        .where(BehaviorLog.user_id == user.id)
        .order_by(BehaviorLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [
            {
                "id": str(log.id),
                "action_type": log.action_type.value,
                "action_target": log.action_target,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "page_path": log.page_path,
                "input_content": log.input_content,
                "agent_id": log.agent_id,
                "request_latency_ms": log.request_latency_ms,
                "is_success": log.is_success,
                "phase": log.phase,
                "user_action_on_ai": log.user_action_on_ai,
                "results_viewed": log.results_viewed,
                "extra_data": log.extra_data,
            }
            for log in logs
        ],
    }

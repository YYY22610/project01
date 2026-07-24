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


@router.post("/batch")
async def batch_create_logs(
    req: BehaviorLogBatchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch insert behavior logs (called by frontend every 5 seconds)."""
    created = 0
    for log_data in req.logs:
        try:
            action_type = ActionType(log_data.action_type)
        except ValueError:
            continue  # Skip unknown action types

        log = BehaviorLog(
            user_id=user.id,
            group=user.group.value if user.group else None,
            action_type=action_type,
            action_target=log_data.action_target,
            input_content=log_data.input_content,
            ai_response=log_data.ai_response,
            agent_id=log_data.agent_id,
            page_path=log_data.page_path,
            session_id=user.session_id,
            extra_data=log_data.extra_data,
            request_latency_ms=log_data.request_latency_ms,
            is_success=log_data.is_success,
            error_detail=log_data.error_detail,
            user_agent=log_data.user_agent,
            screen_resolution=log_data.screen_resolution,
            experiment_version=log_data.experiment_version,
            session_start_time=log_data.session_start_time,
            phase=log_data.phase,
            manual_edit_count=log_data.manual_edit_count,
            final_plan_submit_time=log_data.final_plan_submit_time,
            results_viewed=log_data.results_viewed,
            result_view_duration_ms=log_data.result_view_duration_ms,
            clicked_item_id=log_data.clicked_item_id,
            user_action_on_ai=log_data.user_action_on_ai,
            ai_suggestion_id=log_data.ai_suggestion_id,
            ai_suggestion_type=log_data.ai_suggestion_type,
            ai_interaction_rounds=log_data.ai_interaction_rounds,
        )
        db.add(log)
        created += 1

    await db.commit()
    return {"created": created, "status": "ok"}


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

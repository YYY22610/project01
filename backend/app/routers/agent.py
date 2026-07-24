"""Agent router: SSE streaming chat with AI agents."""
import json
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, ExperimentGroup
from app.models.behavior_log import BehaviorLog, ActionType
from app.models.system_config import SystemConfig
from app.schemas.agent import ChatRequest

router = APIRouter()


@router.post("/chat")
async def agent_chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Chat with an AI agent via SSE streaming.
    Only available for SOA and MOA group users.
    """
    if user.group not in (ExperimentGroup.SOA, ExperimentGroup.MOA):
        raise HTTPException(status_code=403, detail="当前用户组不支持AI助理功能")

    # Pause switch (experiment interruption) — OpenClaw monitoring
    paused_cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "agent_service_paused")
    )).scalar_one_or_none()
    if paused_cfg and paused_cfg.value == "true":
        raise HTTPException(status_code=403, detail="AI助理服务已暂停，请稍后重试或联系管理员")

    # Validate agent_id based on group
    valid_agents = {"soa"} if user.group == ExperimentGroup.SOA else {"moa_a", "moa_b", "moa_c"}
    if req.agent_id not in valid_agents:
        raise HTTPException(status_code=400, detail=f"无效的助理ID，可选: {valid_agents}")

    from app.services.agents.agent_factory import get_agent

    agent = get_agent(req.agent_id)

    start = time.monotonic()
    success = True
    err_detail = None

    async def event_stream():
        nonlocal success, err_detail
        try:
            # Push status event
            yield f"event: status\ndata: {json.dumps({'status': 'thinking', 'agent_id': req.agent_id})}\n\n"

            async for chunk in agent.chat(str(user.id), req.message, db):
                event_type = chunk.get("type", "content")
                data = chunk.get("data", "")
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
        except Exception as e:
            success = False
            err_detail = str(e)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Record the agent interaction for OpenClaw monitoring + research logs
            latency_ms = int((time.monotonic() - start) * 1000)
            log = BehaviorLog(
                user_id=user.id,
                group=user.group.value if user.group else None,
                action_type=ActionType.AGENT_MESSAGE,
                agent_id=req.agent_id,
                is_success=success,
                error_detail=err_detail,
                request_latency_ms=latency_ms,
                session_id=user.session_id,
                extra_data={"error": err_detail} if err_detail else None,
            )
            db.add(log)
            await db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

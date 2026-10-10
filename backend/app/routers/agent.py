"""Agent router: SSE streaming chat with AI agents."""
import json
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.database import async_session_factory
from app.deps import get_current_user
from app.models.user import User, ExperimentGroup
from app.models.behavior_log import BehaviorLog, ActionType
from app.models.system_config import SystemConfig
from app.schemas.agent import ChatRequest, CancelRequest, GroupDiscussRequest
from app.services.agents.agent_cancel import cancel_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat")
async def agent_chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
):
    """
    Chat with an AI agent via SSE streaming.
    Available for SOA (single assistant) and MOA (multi-agent) group users.
    """
    if user.group not in (ExperimentGroup.SOA, ExperimentGroup.MOA):
        raise HTTPException(status_code=403, detail="当前用户组不支持AI助理功能")

    # Pause switch (experiment interruption) — OpenClaw monitoring（短会话）
    async with async_session_factory() as db:
        paused_cfg = (await db.execute(
            select(SystemConfig).where(SystemConfig.key == "agent_service_paused")
        )).scalar_one_or_none()
    if paused_cfg and paused_cfg.value == "true":
        raise HTTPException(status_code=403, detail="AI助理服务已暂停，请稍后重试或联系管理员")

    # Validate agent_id based on group (SOA -> soa; MOA -> moa_a/moa_b)
    valid_agents = {"soa"} if user.group == ExperimentGroup.SOA else {"moa_a", "moa_b"}
    if req.agent_id not in valid_agents:
        raise HTTPException(status_code=400, detail=f"无效的助理ID，可选: {valid_agents}")

    from app.services.agents.agent_factory import get_agent

    agent = get_agent(req.agent_id)

    # 干预能力：本轮开始时清空该 (用户, 助理) 的取消标志
    await cancel_manager.reset_cancel(str(user.id), req.agent_id)

    start = time.monotonic()
    success = True
    err_detail = None
    was_cancelled = False

    async def event_stream():
        nonlocal success, err_detail, was_cancelled
        # 累计 AI 逐步响应文本，用于行为日志（需求5.1.4：捕获与生成式AI的交互）
        ai_parts: list[str] = []
        try:
            # Push status event
            yield f"event: status\ndata: {json.dumps({'status': 'thinking', 'agent_id': req.agent_id, 'message': '正在思考如何帮你完成行程规划任务…'})}\n\n"

            # 构造取消检查闭包：供 base_agent 在工具执行等关键节点查询
            async def _cancel_check():
                return await cancel_manager.is_cancelled(str(user.id), req.agent_id)

            async for chunk in agent.chat(str(user.id), req.message, cancel_check=_cancel_check):
                event_type = chunk.get("type", "content")
                data = chunk.get("data", "")
                # 捕获 AI 逐步响应：content 为文本，tool_call/tool_result 记录为 JSON
                if event_type == "content" and isinstance(data, str):
                    ai_parts.append(data)
                elif event_type in ("tool_call", "tool_result") and isinstance(data, (dict, list)):
                    ai_parts.append(json.dumps(data, ensure_ascii=False))
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                # 参与者中断了本轮操作：不再推送 done，结束流
                if event_type == "cancelled":
                    was_cancelled = True
                    return

            if not was_cancelled:
                yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
        except Exception as e:
            success = False
            err_detail = str(e)  # 完整错误仅记录到服务端日志与行为日志，不泄露给客户端
            logger.exception("Agent stream error: user=%s agent=%s", user.id, req.agent_id)
            yield f"event: error\ndata: {json.dumps({'error': 'AI 服务暂时不可用，请稍后重试'})}\n\n"
        finally:
            # Record the agent interaction for OpenClaw monitoring + research logs
            latency_ms = int((time.monotonic() - start) * 1000)
            log = BehaviorLog(
                user_id=user.id,
                group=user.group.value if user.group else None,
                action_type=ActionType.AGENT_MESSAGE,
                agent_id=req.agent_id,
                input_content=req.message,  # 参与者的指令输入原文
                ai_response="".join(ai_parts) if ai_parts else None,  # AI 逐步响应
                is_success=success and not was_cancelled,
                error_detail=err_detail,
                request_latency_ms=latency_ms,
                session_id=user.session_id,
                extra_data={
                    **({"error": err_detail} if err_detail else {}),
                    "cancelled": was_cancelled,
                },
            )
            # 行为日志写库：流内不持长生命周期会话，此处临时开短会话用完即关
            async with async_session_factory() as db:
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


@router.post("/cancel")
async def agent_cancel(
    req: CancelRequest,
    user: User = Depends(get_current_user),
):
    """
    干预接口：参与者随时中断指定助理的当前操作。
    仅对已授权的助理（自身所属实验组的助理）生效。
    """
    valid_agents = {"soa"} if user.group == ExperimentGroup.SOA else {"moa_a", "moa_b"}
    if req.agent_id not in valid_agents:
        raise HTTPException(status_code=400, detail=f"无效的助理ID，可选: {valid_agents}")

    await cancel_manager.request_cancel(str(user.id), req.agent_id)
    return {"status": "cancelled", "agent_id": req.agent_id}


@router.post("/group-discuss")
async def group_discuss(
    req: GroupDiscussRequest,
    user: User = Depends(get_current_user),
):
    """
    MOA 组多角色群辩讨论（模式 B）：4 位职能角色 + 主持人同屏辩论，
    由主持人整合成最终方案。结果以 SSE 事件流返回：
      stage / role_start / content / role_end / done / error
    仅 MOA 组可用。
    """
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")

    from app.services.group_discussion import run_group_discussion

    async def event_stream():
        try:
            async for chunk in run_group_discussion(
                requirement=req.message,
                dest=req.dest,
                days=req.days,
                budget=req.budget,
                travelers=req.travelers,
            ):
                ctype = chunk.get("type", "content")
                data = chunk.get("data", "")
                yield f"event: {ctype}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Group discuss error: user=%s", user.id)
            yield f"event: error\ndata: {json.dumps({'error': '智囊团讨论暂时不可用，请稍后重试'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

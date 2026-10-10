"""MOA 组多轮群辩路由（移植自 AutoGen travel-planner）。

端点：
  POST /api/moa/group-discuss  启动群辩（SSE 流式），MOA 组专属
  POST /api/moa/group-resume   群聊暂停等待用户输入时，回填用户回答/确认意见，恢复群聊
  POST /api/moa/group-cancel   中断当前用户所在的群聊会话

与现有 /api/agent/* 的区别：本路由支持「主持人反问用户」「确认门多轮修订」所需的
跨请求暂停/恢复——通过每用户一个 MOASession 持有 asyncio.Future 实现。
"""
import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.deps import get_current_user
from app.models.user import User, ExperimentGroup
from app.models.behavior_log import BehaviorLog, ActionType
from app.models.system_config import SystemConfig
from app.models.moa_group_session import MoaGroupSession
from app.services.autogen_group_discussion import run_autogen_discussion

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# 每用户会话：持有暂停等待用户输入的 Future
# ---------------------------------------------------------------------------
class MOASession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.active = False
        self.pending = False
        self.pending_prompt: str = ""
        self.future: Optional[asyncio.Future] = None
        self.cancelled = False


SESSIONS: dict[str, MOASession] = {}


def get_session(user_id: str) -> MOASession:
    s = SESSIONS.get(user_id)
    if s is None:
        s = MOASession(user_id)
        SESSIONS[user_id] = s
    return s


def make_user_input(session: MOASession):
    """构造 user_input 回调：标记 pending、创建 Future 并等待其结果（由 resume 接口回填）。"""

    async def user_input(prompt: str) -> str:
        session.pending = True
        session.pending_prompt = prompt
        session.future = asyncio.get_running_loop().create_future()
        try:
            return await session.future
        finally:
            session.pending = False
            session.future = None

    return user_input


async def _is_paused(db: AsyncSession) -> bool:
    cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "agent_service_paused")
    )).scalar_one_or_none()
    return bool(cfg and cfg.value == "true")


async def _save_group_state(
    db: AsyncSession,
    user_id,
    context: Optional[dict] = None,
    server_stage: Optional[dict] = None,
) -> None:
    """upsert 当前用户的群聊持久化记录（按 user_id 隔离）。

    context 由前端保存完整快照（权威）；server_stage 由后端在 SSE 关键节点自动写，
    两者互不覆盖。
    """
    row = (await db.execute(
        select(MoaGroupSession).where(MoaGroupSession.user_id == user_id)
    )).scalar_one_or_none()
    if row is None:
        row = MoaGroupSession(user_id=user_id)
        db.add(row)
    if context is not None:
        row.context = context
    if server_stage is not None:
        row.server_stage = server_stage
    await db.commit()


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------
class GroupResumeRequest(BaseModel):
    message: str


class GroupDiscussRequest(BaseModel):
    message: str
    dest: str = "杭州"
    days: int = 3
    budget: int = 2000
    travelers: str = "1 人"


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------
@router.post("/group-discuss")
async def group_discuss(
    req: GroupDiscussRequest,
    user: User = Depends(get_current_user),
):
    """MOA 组多角色群辩（含用户反问 + 确认门）。SSE 流式返回。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")

    # 暂停开关检查（短会话，用完即关）
    async with async_session_factory() as db:
        paused = await _is_paused(db)
    if paused:
        raise HTTPException(status_code=403, detail="AI 助理服务已暂停，请稍后重试或联系管理员")

    session = get_session(str(user.id))
    if session.active:
        raise HTTPException(status_code=409, detail="当前已有进行中的群聊，请先完成或取消")

    session.active = True
    session.cancelled = False
    ui = make_user_input(session)

    # 注意：session.cancelled 是普通属性，should_stop 必须是同步函数。
    # 若写成 async def，_stop() 调用时返回的是未 await 的协程对象（永远为真），
    # 会导致群聊在每个阶段前的 _stop() 检查都被误判为「已暂停」而直接报错退出。
    def should_stop() -> bool:
        return session.cancelled

    start = time.monotonic()
    success = True
    err_detail = None

    async def event_stream():
        nonlocal success, err_detail
        ai_parts: list[str] = []
        try:
            async for chunk in run_autogen_discussion(
                requirement=req.message,
                dest=req.dest,
                days=req.days,
                budget=req.budget,
                travelers=req.travelers,
                user_input=ui,
                should_stop=should_stop,
            ):
                ctype = chunk.get("type", "content")
                data = chunk.get("data", "")
                # 累计文本内容供行为日志
                if ctype == "content" and isinstance(data, dict):
                    ai_parts.append(data.get("delta", ""))
                elif ctype in ("await_user", "await_confirm"):
                    ai_parts.append("[交互暂停-等待用户输入]")
                # 服务端兜底：关键节点自动记录阶段标记（不覆盖前端 context，防丢失）
                if ctype in ("await_user", "await_confirm", "done"):
                    stage_map = {"await_user": "ask_user", "await_confirm": "await_confirm", "done": "done"}
                    try:
                        label = ""
                        if isinstance(data, dict):
                            label = data.get("label") or data.get("prompt") or ""
                        async with async_session_factory() as db:
                            await _save_group_state(db, user.id, server_stage={
                                "stage": stage_map[ctype],
                                "label": str(label)[:80] if label else "",
                                "ts": time.time(),
                            })
                    except Exception:
                        logger.exception("MOA 群聊阶段标记保存失败")
                yield f"event: {ctype}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except Exception as e:
            success = False
            err_detail = str(e)
            logger.exception("MOA group discuss error: user=%s", user.id)
            yield f"event: error\ndata: {json.dumps({'error': '智囊团讨论暂时不可用，请稍后重试'})}\n\n"
        finally:
            session.active = False
            latency_ms = int((time.monotonic() - start) * 1000)
            log = BehaviorLog(
                user_id=user.id,
                group=user.group.value if user.group else None,
                action_type=ActionType.AGENT_MESSAGE,
                agent_id="moa_group",
                input_content=req.message,
                ai_response="".join(ai_parts) if ai_parts else None,
                is_success=success,
                error_detail=err_detail,
                extra_data={"cancelled": session.cancelled},
            )
            try:
                async with async_session_factory() as db:
                    db.add(log)
                    await db.commit()
            except Exception:
                logger.exception("写入 MOA 行为日志失败")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/group-resume")
async def group_resume(
    req: GroupResumeRequest,
    user: User = Depends(get_current_user),
):
    """群聊暂停等待用户输入时，由前端回填用户回答/确认意见，恢复群聊。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")

    session = get_session(str(user.id))
    if not session.pending or session.future is None:
        raise HTTPException(status_code=409, detail="当前没有等待用户输入的群聊")
    session.future.set_result(req.message)
    return {"status": "resumed"}


@router.post("/group-cancel")
async def group_cancel(
    user: User = Depends(get_current_user),
):
    """中断当前用户所在的群聊会话。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")

    session = get_session(str(user.id))
    session.cancelled = True
    # 若正处于等待用户输入，直接以空结果唤醒，让编排器走到 should_stop 退出
    if session.pending and session.future is not None and not session.future.done():
        session.future.set_result("")
    return {"status": "cancelled"}


class GroupStateRequest(BaseModel):
    """前端保存的完整群聊上下文快照（消息/方案/阶段）。"""
    context: dict


@router.get("/group-state")
async def get_group_state(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """恢复当前用户的群聊上下文（刷新后保留现场）。仅能取到自己的，用户间天然隔离。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")
    row = (await db.execute(
        select(MoaGroupSession).where(MoaGroupSession.user_id == user.id)
    )).scalar_one_or_none()
    return {"context": row.context if row else None, "server_stage": row.server_stage if row else None}


@router.put("/group-state")
async def put_group_state(
    req: GroupStateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存当前用户的群聊上下文（前端在状态变化时调用）。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")
    await _save_group_state(db, user.id, context=req.context)
    return {"status": "saved"}


@router.delete("/group-state")
async def delete_group_state(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清除当前用户的群聊上下文（重置/新开一场时调用）。"""
    if user.group != ExperimentGroup.MOA:
        raise HTTPException(status_code=403, detail="当前用户组不支持智囊团讨论功能")
    row = (await db.execute(
        select(MoaGroupSession).where(MoaGroupSession.user_id == user.id)
    )).scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()
    return {"status": "cleared"}

"""Task router: task config, start task, submit task."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserStatus
from app.models.task_submission import TaskSubmission
from app.models.questionnaire import QuestionnaireResponse
from app.models.system_config import SystemConfig
from app.schemas.task import TaskConfigResponse, TaskStartResponse, TaskSubmitRequest, TaskSubmitResponse, DemoCompleteRequest
from app.services.state_machine import transition_status

router = APIRouter()

# 参与者可提交的 docx 目录（与 document.py 生成目录一致）
_DOCS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "documents")
)


def _validate_docx_path(path: str | None) -> str | None:
    """防任意路径写入：docx_file_path 只能是生成目录内的 .docx 文件。

    参与者提交的路径会被管理员下载接口直接读取，
    若不校验，可传 /etc/passwd、/app/config.py 等任意服务端路径导致任意文件泄露。
    """
    if not path:
        return None
    p = os.path.abspath(path)
    if not p.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="无效的文档路径")
    try:
        inside = os.path.commonpath([p, _DOCS_DIR]) == _DOCS_DIR
    except ValueError:  # 不同盘符等异常路径
        inside = False
    if not inside:
        raise HTTPException(status_code=400, detail="无效的文档路径")
    return p


async def _get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else default


@router.post("/reset")
async def reset_flow(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """重置实验流程：管理员修改分组后，参与者重新登录时需从头再来。

    将状态重置回 consented（重新走演示→任务→问卷），并清空任务提交记录
    与问卷回答，保证新分组下的实验数据干净。聊天记录由前端按会话隔离，
    重新登录即全新会话，无需后端处理。
    """
    user.status = UserStatus.CONSENTED
    user.task_start_time = None
    user.task_end_time = None
    await db.execute(delete(TaskSubmission).where(TaskSubmission.user_id == user.id))
    await db.execute(delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user.id))
    await db.commit()
    return {"status": "ok", "message": "实验流程已重置"}


@router.get("/config", response_model=TaskConfigResponse)
async def get_task_config(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get task configuration — reads from system_config table."""
    task_days = int(await _get_config_value(db, "task_days", "3"))
    task_budget = int(await _get_config_value(db, "task_budget", "2000"))
    target_email = await _get_config_value(db, "target_email", "experiment@example.com")
    destination = await _get_config_value(db, "destination", "杭州")
    travelers = await _get_config_value(db, "task_travelers", "1 人")

    return TaskConfigResponse(
        task_days=task_days,
        task_budget=task_budget,
        target_email=target_email,
        destination=destination,
        travelers=travelers,
        sub_tasks=[
            f"搜索{destination}景点信息",
            f"生成{task_days}日游行程Word文档",
            "设置旅行提醒",
            f"将行程发送至 {target_email}",
        ],
    )


@router.post("/demo-complete")
async def complete_demo(
    req: DemoCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark demo as completed — transitions user from consented to demo_completed.

    Accepts the demo watching duration (seconds) for experimental logging.
    """
    if user.status == UserStatus.DEMO_COMPLETED:
        return {"status": "ok", "message": "演示已完成"}
    if user.status != UserStatus.CONSENTED:
        raise HTTPException(status_code=400, detail="当前状态无法完成演示环节")
    if req.watch_seconds is not None:
        user.demo_watch_seconds = req.watch_seconds
    await transition_status(db, user, UserStatus.DEMO_COMPLETED)
    await db.commit()
    return {"status": "ok", "message": "演示完成"}


@router.post("/start", response_model=TaskStartResponse)
async def start_task(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Start the task — transitions user to task_in_progress."""
    if user.status != UserStatus.DEMO_COMPLETED:
        raise HTTPException(status_code=400, detail="请先完成演示环节")

    user = await transition_status(db, user, UserStatus.TASK_IN_PROGRESS)
    user.task_start_time = datetime.now(timezone.utc)

    # Create or update submission record
    result = await db.execute(select(TaskSubmission).where(TaskSubmission.user_id == user.id))
    submission = result.scalar_one_or_none()
    if not submission:
        submission = TaskSubmission(user_id=user.id)
        db.add(submission)

    await db.commit()
    return TaskStartResponse(
        task_id=str(submission.id),
        started_at=user.task_start_time,
        deadline=user.task_start_time,  # No hard deadline in this experiment
    )


@router.post("/submit", response_model=TaskSubmitResponse)
async def submit_task(
    req: TaskSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit task — transitions user to task_completed."""
    if user.status != UserStatus.TASK_IN_PROGRESS:
        raise HTTPException(status_code=400, detail="任务未开始或已完成")

    user = await transition_status(db, user, UserStatus.TASK_COMPLETED)
    user.task_end_time = datetime.now(timezone.utc)

    result = await db.execute(select(TaskSubmission).where(TaskSubmission.user_id == user.id))
    submission = result.scalar_one_or_none()
    if not submission:
        submission = TaskSubmission(user_id=user.id)
        db.add(submission)

    submission.task1_search = req.task1_search
    submission.task2_document = req.task2_document
    submission.task3_reminder = req.task3_reminder
    submission.task4_email = req.task4_email
    submission.docx_file_path = _validate_docx_path(req.docx_file_path)
    submission.reminder_datetime = req.reminder_datetime
    submission.email_status = req.email_status
    submission.email_recipient = req.email_recipient
    submission.submitted_at = datetime.now(timezone.utc)

    if user.task_start_time:
        duration = (user.task_end_time - user.task_start_time).total_seconds() * 1000
        submission.duration_ms = int(duration)

    all_completed = all([req.task1_search, req.task2_document, req.task3_reminder, req.task4_email])
    await db.commit()

    return TaskSubmitResponse(
        task_id=str(submission.id),
        submitted_at=submission.submitted_at,
        duration_ms=submission.duration_ms or 0,
        all_completed=all_completed,
    )


@router.get("/status")
async def get_task_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current task status and progress."""
    result = await db.execute(select(TaskSubmission).where(TaskSubmission.user_id == user.id))
    submission = result.scalar_one_or_none()

    return {
        "status": user.status.value,
        "task_start_time": user.task_start_time.isoformat() if user.task_start_time else None,
        "task_end_time": user.task_end_time.isoformat() if user.task_end_time else None,
        "submission": {
            "task1_search": submission.task1_search if submission else False,
            "task2_document": submission.task2_document if submission else False,
            "task3_reminder": submission.task3_reminder if submission else False,
            "task4_email": submission.task4_email if submission else False,
            "docx_file_path": submission.docx_file_path if submission else None,
            "email_status": submission.email_status if submission else None,
        } if submission else None,
    }

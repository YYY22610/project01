"""Task router: task config, start task, submit task."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserStatus
from app.models.task_submission import TaskSubmission
from app.models.system_config import SystemConfig
from app.schemas.task import TaskConfigResponse, TaskStartResponse, TaskSubmitRequest, TaskSubmitResponse, DemoCompleteRequest
from app.services.state_machine import transition_status

router = APIRouter()


async def _get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else default


@router.get("/config", response_model=TaskConfigResponse)
async def get_task_config(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get task configuration — reads from system_config table."""
    task_days = int(await _get_config_value(db, "task_days", "3"))
    task_budget = int(await _get_config_value(db, "task_budget", "1000"))
    target_email = await _get_config_value(db, "target_email", "experiment@example.com")
    destination = await _get_config_value(db, "destination", "杭州")

    return TaskConfigResponse(
        task_days=task_days,
        task_budget=task_budget,
        target_email=target_email,
        destination=destination,
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
    submission.docx_file_path = req.docx_file_path
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

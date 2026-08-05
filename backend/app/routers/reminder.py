"""Reminder router: set and list reminders."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.reminder import Reminder
from app.models.task_submission import TaskSubmission
from app.schemas.task import ReminderSetRequest, ReminderResponse

router = APIRouter()


@router.post("", response_model=ReminderResponse)
async def set_reminder(
    req: ReminderSetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a travel reminder."""
    now = datetime.now(timezone.utc)
    dt = req.reminder_datetime
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt < now:
        raise HTTPException(status_code=400, detail="提醒时间不能早于当前时间")

    reminder = Reminder(
        user_id=user.id,
        reminder_datetime=req.reminder_datetime,
        content=req.content,
        is_set=True,
    )
    db.add(reminder)

    # Update task submission
    result = await db.execute(select(TaskSubmission).where(TaskSubmission.user_id == user.id))
    submission = result.scalar_one_or_none()
    if submission:
        submission.task3_reminder = True
        submission.reminder_datetime = req.reminder_datetime
    else:
        submission = TaskSubmission(
            user_id=user.id,
            task3_reminder=True,
            reminder_datetime=req.reminder_datetime,
        )
        db.add(submission)

    await db.commit()
    return ReminderResponse(
        id=str(reminder.id),
        reminder_datetime=reminder.reminder_datetime,
        content=reminder.content,
        is_set=reminder.is_set,
    )


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List user's reminders."""
    result = await db.execute(
        select(Reminder).where(Reminder.user_id == user.id).order_by(Reminder.reminder_datetime)
    )
    reminders = result.scalars().all()
    return [
        ReminderResponse(
            id=str(r.id),
            reminder_datetime=r.reminder_datetime,
            content=r.content or "",
            is_set=r.is_set,
        )
        for r in reminders
    ]

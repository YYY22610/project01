"""Reminder service — persist reminders and send due reminder emails.

提醒流程：
  1. 用户通过 AI(set_reminder 工具) 或 REST(/api/reminder) 设置提醒，记录到 reminders 表。
  2. 后台调度器每 30 秒调用 send_due_reminders()，扫描 reminder_datetime <= now
     且 sent_at IS NULL 且 is_set = True 的提醒。
  3. 向该用户注册邮箱发送提醒邮件，发送成功后写 sent_at 并置 is_set = False，避免重复发送。
"""
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import async_session_factory
from app.models.reminder import Reminder
from app.models.user import User
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

# 失败提醒的最大重试次数；超过后判定为永久失败并停止重试
MAX_REMINDER_ATTEMPTS = 5

# 这些 SMTP 错误属于「永久失败」，收件人地址无效，重试多少次都没用
_PERMANENT_FAIL_HINTS = ("550", "non-existent account", "does not exist", "no such user", "user unknown")


def _is_permanent_failure(err_text: str) -> bool:
    low = (err_text or "").lower()
    return any(hint.lower() in low for hint in _PERMANENT_FAIL_HINTS)


def parse_reminder_datetime(value: Any) -> datetime:
    """把 reminder_datetime 解析为带时区的 datetime。

    - 已是 datetime：补上时区（naive 视为 UTC）。
    - ISO 字符串：支持尾部 Z 或 +offset；naive 视为 UTC。
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def create_reminder(user_id: str, reminder_datetime: Any, content: str | None) -> Reminder:
    """写入一条提醒记录到数据库。"""
    rdt = parse_reminder_datetime(reminder_datetime)
    if rdt < datetime.now(timezone.utc):
        raise ValueError("提醒时间不能早于当前时间")
    async with async_session_factory() as db:
        reminder = Reminder(
            user_id=user_id,
            reminder_datetime=rdt,
            content=content,
            is_set=True,
            sent_at=None,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        logger.info(f"已创建提醒 user={user_id} at={rdt.isoformat()}")
        return reminder


async def send_due_reminders() -> int:
    """扫描并发送所有到期的提醒邮件。

    返回本次成功送入发送流程的提醒数量（发送失败的不计入，下次重试）。
    """
    now = datetime.now(timezone.utc)
    sent_count = 0

    async with async_session_factory() as db:
        result = await db.execute(
            select(Reminder).where(
                Reminder.reminder_datetime <= now,
                Reminder.sent_at.is_(None),
                Reminder.is_set == True,  # noqa: E712
            )
        )
        due = result.scalars().all()
        if not due:
            return 0

        for reminder in due:
            user = await db.get(User, reminder.user_id)
            email_addr = user.email if user else None
            if not email_addr:
                logger.warning(f"提醒 {reminder.id} 找不到用户邮箱，跳过（标记已处理）")
                reminder.sent_at = datetime.now(timezone.utc)
                reminder.is_set = False
                db.add(reminder)
                continue

            subject = "杭州旅行规划 · 行程提醒"
            body = (
                f"您好，{user.email}：\n\n"
                f"您设置的行程提醒时间已到。\n\n"
                f"提醒内容：\n{reminder.content or '（无具体内容）'}\n\n"
                f"—— 人机协作决策实验平台"
            )
            try:
                res = send_email(email_addr, subject, body)
                status = res.get("status")
                if status in ("sent", "mock_sent"):
                    reminder.sent_at = datetime.now(timezone.utc)
                    reminder.is_set = False
                    db.add(reminder)
                    sent_count += 1
                    logger.info(f"提醒邮件已发送 user={email_addr} reminder={reminder.id} backend={status}")
                else:
                    err = str(res.get("error") or "unknown")
                    reminder.failed_attempts = (reminder.failed_attempts or 0) + 1
                    reminder.last_error = err[:500]
                    db.add(reminder)
                    permanent = _is_permanent_failure(err)
                    if permanent or reminder.failed_attempts >= MAX_REMINDER_ATTEMPTS:
                        # 永久失败或达到重试上限：停止重试（disarm），保留 sent_at=NULL 表示未送达
                        reminder.is_set = False
                        logger.warning(
                            f"提醒 {reminder.id} 标记为永久失败（停止重试）"
                            f" user={email_addr} permanent={permanent}"
                            f" attempts={reminder.failed_attempts} error={err[:200]}"
                        )
                    else:
                        logger.error(
                            f"提醒邮件发送失败（将重试） user={email_addr} reminder={reminder.id}"
                            f" attempts={reminder.failed_attempts}/{MAX_REMINDER_ATTEMPTS} res={res}"
                        )
            except Exception:
                reminder.failed_attempts = (reminder.failed_attempts or 0) + 1
                reminder.last_error = "exception"
                db.add(reminder)
                if reminder.failed_attempts >= MAX_REMINDER_ATTEMPTS:
                    reminder.is_set = False
                    logger.warning(
                        f"提醒 {reminder.id} 发送异常达到上限，标记为永久失败（停止重试）"
                        f" user={email_addr} attempts={reminder.failed_attempts}"
                    )
                else:
                    logger.exception(f"提醒邮件发送异常 user={email_addr} reminder={reminder.id}")

        await db.commit()

    return sent_count

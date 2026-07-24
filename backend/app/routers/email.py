"""Email router: send emails with optional attachments (uploaded files + docx)."""
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.task_submission import TaskSubmission
from app.schemas.task import EmailSendResponse
from app.services.email_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)

# 上传附件存放目录（与后端根目录相对）
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "email_attachments",
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/send", response_model=EmailSendResponse)
async def send_email_endpoint(
    to_email: str = Form(..., description="收件人邮箱"),
    subject: str = Form("杭州三日游行程规划"),
    content: str = Form(""),
    attachment_path: str | None = Form(None, description="服务端已有附件路径，如生成的 docx"),
    files: list[UploadFile] | None = File(None, description="前端上传的附件文件"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送邮件：收件人可自定义，并支持上传附件。"""
    attachment_paths: list[str] = []
    if attachment_path:
        attachment_paths.append(attachment_path)

    if files:
        for f in files:
            if not f.filename:
                continue
            # 防路径穿越：仅保留文件名与扩展名
            safe_name = os.path.basename(f.filename)
            ext = os.path.splitext(safe_name)[1]
            stored_name = f"{uuid.uuid4().hex}{ext}"
            dest = os.path.join(UPLOAD_DIR, stored_name)
            try:
                data = await f.read()
                with open(dest, "wb") as fh:
                    fh.write(data)
                attachment_paths.append(dest)
            except Exception as e:
                logger.error(f"保存附件失败 {safe_name}: {e}")

    try:
        result = send_email(
            to_email=to_email,
            subject=subject,
            content=content or "请查收附件中的行程规划。",
            attachment_paths=attachment_paths or None,
        )
    except Exception as e:
        logger.error(f"Email service error: {e}")
        raise HTTPException(status_code=502, detail="邮件发送服务异常，请稍后重试")

    # 真实的发送失败不得记为任务完成
    if result.get("status") == "failed":
        raise HTTPException(status_code=502, detail="邮件发送失败，请稍后重试")

    # 更新任务提交记录（mock_sent / sent 均为有效完成）
    sub_result = await db.execute(
        select(TaskSubmission).where(TaskSubmission.user_id == user.id)
    )
    submission = sub_result.scalar_one_or_none()
    if submission:
        submission.task4_email = True
        submission.email_status = result["status"]
        submission.email_recipient = to_email
    else:
        submission = TaskSubmission(
            user_id=user.id,
            task4_email=True,
            email_status=result["status"],
            email_recipient=to_email,
        )
        db.add(submission)

    await db.commit()
    return EmailSendResponse(
        status=result["status"],
        message_id=result.get("message_id"),
    )

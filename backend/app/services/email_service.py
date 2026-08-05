"""Email service — send via SMTP (preferred) or Resend API, with mock fallback.

发送优先级（可通过 EMAIL_BACKEND 强制指定 smtp/resend/mock）：
  1. SMTP  —— 国内可达，QQ/163/Gmail/腾讯企业邮/阿里云均支持
  2. Resend —— 需国外信用卡 + 验证域名
  3. mock  —— 未配置任何真实后端时，仅记录「模拟发送」不真正发信
"""
import logging
import base64
import os
import smtplib
import ssl
import email.policy
from email import encoders
from email.headerregistry import Address
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _is_html(text: str) -> bool:
    return bool(text) and ("<html" in text.lower() or "<body" in text.lower()
                           or "<div" in text.lower() or "<p" in text.lower()
                           or "<table" in text.lower() or "<br" in text.lower())


def _plain_from_html(html: str) -> str:
    import re
    txt = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    txt = re.sub(r"</p>", "\n", txt, flags=re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", "", txt)
    return txt.strip()


def _build_message(
    to_email: str,
    subject: str,
    content: str,
    attachment_paths: list[str] | None,
) -> MIMEMultipart:
    # 使用 default 策略：自动对中文主题/发件人名做 RFC 2047 编码，避免 as_string() ascii 报错
    msg = MIMEMultipart("mixed", policy=email.policy.default)
    msg["Subject"] = subject
    msg["From"] = Address("人机协作决策实验平台", addr_spec=settings.SENDER_EMAIL)
    msg["To"] = Address(to_email, addr_spec=to_email) if "@" in to_email else to_email

    # 正文部分：优先 HTML，并附纯文本兜底
    alt = MIMEMultipart("alternative", policy=email.policy.default)
    html = content if _is_html(content) else None
    plain = _plain_from_html(content) if html else (content or "请查收附件中的行程规划。")
    alt.attach(MIMEText(plain, "plain", "utf-8", policy=email.policy.default))
    if html:
        alt.attach(MIMEText(html, "html", "utf-8", policy=email.policy.default))
    msg.attach(alt)

    # 附件
    for path in (attachment_paths or []):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            filename = os.path.basename(path)
            part = MIMEBase("application", "octet-stream", policy=email.policy.default)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=("utf-8", "", filename),
            )
            msg.attach(part)
        except Exception as e:
            logger.error(f"读取附件失败 {path}: {e}")

    return msg


def _send_smtp(
    to_email: str,
    subject: str,
    content: str,
    attachment_paths: list[str] | None,
) -> dict:
    msg = _build_message(to_email, subject, content, attachment_paths)
    try:
        context = ssl.create_default_context()
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=30
            ) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, [to_email], msg.as_string())
        logger.info(f"SMTP 邮件已发送至 {to_email}")
        return {"status": "sent", "message_id": None}
    except Exception as e:
        logger.error(f"SMTP 发送失败: {e}")
        return {"status": "failed", "message_id": None, "error": str(e)}


def _send_resend(
    to_email: str,
    subject: str,
    content: str,
    attachment_paths: list[str] | None,
) -> dict:
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "from": settings.SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": content if not _is_html(content) else _plain_from_html(content),
        }
        if _is_html(content):
            payload["html"] = content

        if attachment_paths:
            attachments = []
            for path in attachment_paths:
                try:
                    with open(path, "rb") as fh:
                        data = fh.read()
                    attachments.append(
                        {
                            "filename": os.path.basename(path),
                            "content": base64.b64encode(data).decode("utf-8"),
                        }
                    )
                except Exception as e:
                    logger.error(f"读取附件失败 {path}: {e}")
            if attachments:
                payload["attachments"] = attachments

        with httpx.Client() as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return {"status": "sent", "message_id": data.get("id")}
    except Exception as e:
        logger.error(f"Resend 发送失败: {e}")
        return {"status": "failed", "message_id": None, "error": str(e)}


def send_email(
    to_email: str,
    subject: str,
    content: str,
    attachment_paths: list[str] | None = None,
) -> dict:
    """发送邮件。返回 {"status": "sent"|"failed"|"mock_sent", "message_id": ...}。"""
    backend = (settings.EMAIL_BACKEND or "").lower()

    # 未显式指定时自动选择：有 SMTP 配置优先 SMTP，其次 Resend
    if not backend:
        if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
            backend = "smtp"
        elif settings.RESEND_API_KEY:
            backend = "resend"
        else:
            backend = "mock"

    if backend == "smtp":
        if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
            logger.warning("SMTP 后端已选但缺少 SMTP 配置，回退 mock")
            return {"status": "mock_sent", "message_id": None}
        return _send_smtp(to_email, subject, content, attachment_paths)

    if backend == "resend":
        if not settings.RESEND_API_KEY:
            logger.warning("Resend 后端已选但缺少 API key，回退 mock")
            return {"status": "mock_sent", "message_id": None}
        return _send_resend(to_email, subject, content, attachment_paths)

    # mock
    logger.warning("未配置任何真实邮件后端 — 邮件将 mock 发送（不真正发出）")
    return {"status": "mock_sent", "message_id": None}

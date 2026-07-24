"""Email service — send via Resend API or mock."""
import logging
import base64
import os

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    content: str,
    attachment_paths: list[str] | None = None,
) -> dict:
    """Send email via Resend API. Falls back to mock if no API key."""
    if not settings.RESEND_API_KEY:
        logger.warning("No RESEND_API_KEY configured — email will be mock-sent")
        return {"status": "mock_sent", "message_id": None}

    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "from": settings.SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": content,
        }

        if attachment_paths:
            attachments = []
            for path in attachment_paths:
                try:
                    with open(path, "rb") as fh:
                        data = fh.read()
                    filename = os.path.basename(path)
                    attachments.append(
                        {
                            "filename": filename,
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
        logger.error(f"Email send failed: {e}")
        return {"status": "failed", "message_id": None}

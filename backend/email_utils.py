import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_magic_link_email(recipient: str, magic_link_url: str) -> None:
    subject = "Your Audiovook login link"
    body = f"Click the secure link below to access Audiovook:\n\n{magic_link_url}\n\nThe link expires in {settings.magic_link_expiration_minutes} minutes."
    _send_email(recipient, subject, body)


def _send_email(recipient: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.info(
            "Skipping email send because SMTP configuration is missing. Intended to send to %s with subject %s and body %s",
            recipient,
            subject,
            body,
        )
        return

    message = EmailMessage()
    message["From"] = settings.email_from_address
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    smtp: Optional[smtplib.SMTP] = None
    try:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    finally:
        if smtp:
            smtp.quit()

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from .settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_magic_link_email(recipient: str, magic_link_url: str) -> None:
    subject, text_body, html_body = _build_magic_link_email(magic_link_url)
    _send_email(recipient, subject, text_body, html_body)


def _send_email(
    recipient: str, subject: str, text_body: str, html_body: Optional[str] = None
) -> None:
    if not settings.smtp_host:
        logger.info(
            "Skipping email send because SMTP configuration is missing. Intended to send to %s with subject %s and body %s",
            recipient,
            subject,
            text_body,
        )
        return

    message = EmailMessage()
    message["From"] = settings.email_from_address
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

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


def _build_magic_link_email(magic_link_url: str) -> tuple[str, str, str]:
    expiration_minutes = settings.magic_link_expiration_minutes
    subject = "Audiovook · Enllaç màgic / Magic login link"
    text_body = (
        "CAT:\n"
        "Benvingut a Audiovook! Pots iniciar sessió amb aquest enllaç segur:\n"
        f"{magic_link_url}\n"
        f"Caduca d'aquí a {expiration_minutes} minuts.\n\n"
        "ENG:\n"
        "Welcome to Audiovook! Sign in with this secure link:\n"
        f"{magic_link_url}\n"
        f"It expires in {expiration_minutes} minutes."
    )
    html_body = f"""
    <html>
      <body style=\"font-family:Arial,sans-serif;background:#f5f5f7;padding:24px;color:#222;\">
        <section style=\"background:#ffffff;border-radius:12px;padding:24px;border:1px solid #d5d5dc;\">
          <h1 style=\"margin-top:0;color:#0d0e37;\">Audiovook · Enllaç màgic</h1>
          <p style=\"font-size:15px;line-height:1.5;\">
            Hola! Fes clic al botó per iniciar sessió sense contrasenya. L'enllaç caduca d'aquí a {expiration_minutes} minuts.
          </p>
          <p style=\"text-align:center;margin:32px 0;\">
            <a href=\"{magic_link_url}\" style=\"background:#0d0e37;color:#fff;padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:bold;\">
              Obrir Audiovook
            </a>
          </p>
          <p style=\"font-size:14px;line-height:1.5;color:#444;\">
            Si el botó no funciona, copia i enganxa aquest enllaç al navegador:<br>
            <a href=\"{magic_link_url}\" style=\"color:#0d0e37;word-break:break-all;\">{magic_link_url}</a>
          </p>
          <hr style=\"margin:32px 0;border:none;border-top:1px solid #eee;\">
          <h2 style=\"margin-bottom:8px;color:#0d0e37;\">Magic link (English)</h2>
          <p style=\"font-size:15px;line-height:1.5;\">
            Click the button below to sign in. The link expires in {expiration_minutes} minutes.
          </p>
          <p style=\"text-align:center;margin:32px 0;\">
            <a href=\"{magic_link_url}\" style=\"background:#f7836a;color:#0d0e37;padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:bold;\">
              Open Audiovook
            </a>
          </p>
          <p style=\"font-size:14px;line-height:1.5;color:#444;\">
            If the button does not work, copy and paste this link into your browser:<br>
            <a href=\"{magic_link_url}\" style=\"color:#0d0e37;word-break:break-all;\">{magic_link_url}</a>
          </p>
        </section>
      </body>
    </html>
    """
    return subject, text_body, html_body

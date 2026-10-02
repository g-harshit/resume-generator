"""Sending email. Plain SMTP, synchronously with a timeout.

With no SMTP configured (development), the email is written to the API log instead,
so a password-reset link can still be followed locally.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger(__name__)

# The last few emails "sent" without SMTP, newest last — for tests and local use.
outbox: list[EmailMessage] = []


class MailError(Exception):
    pass


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = settings.smtp_from or f"{settings.app_name} <no-reply@localhost>"
    msg["Subject"] = subject
    msg.set_content(body)

    if not settings.smtp_host:
        outbox.append(msg)
        del outbox[:-20]
        log.warning("SMTP not configured; email to %s not sent:\n%s\n%s", to, subject, body)
        return

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        log.exception("Sending email to %s failed", to)
        raise MailError("The email couldn't be sent. Please try again later.") from exc

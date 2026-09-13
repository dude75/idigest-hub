"""Опциональный SMTP для сброса пароля."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.crypto import try_decrypt_str
from app.models import InstanceSettings

log = logging.getLogger("app")


def smtp_configured(settings: InstanceSettings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from and settings.public_base_url)


def send_mail(db: Session, to_email: str, subject: str, body: str) -> None:
    settings = db.get(InstanceSettings, 1)
    if settings is None or not smtp_configured(settings):
        raise RuntimeError("smtp not configured")
    password = try_decrypt_str(settings.smtp_password_encrypted, db) or ""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    host = settings.smtp_host or "localhost"
    port = settings.smtp_port or 587
    if settings.smtp_tls:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, password)
            smtp.send_message(msg)
    log.info("mail sent to=%s subject=%s", to_email, subject)

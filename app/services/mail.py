"""Опциональный SMTP для сброса пароля."""

from __future__ import annotations

import logging
import smtplib
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr

from sqlalchemy.orm import Session

from app.crypto import try_decrypt_str
from app.models import InstanceSettings

log = logging.getLogger("app")
SMTP_TIMEOUT_SEC = 20.0
SMTP_SSL_PORT = 465


@dataclass(frozen=True)
class SmtpParams:
    host: str
    port: int
    user: str | None
    password: str
    from_addr: str
    tls: bool


def smtp_configured(settings: InstanceSettings) -> bool:
    return bool(settings.smtp_host and settings.smtp_from and settings.public_base_url)


def smtp_password_configured(settings: InstanceSettings) -> bool:
    return bool((settings.smtp_password_encrypted or "").strip())


def resolve_smtp_password(
    settings: InstanceSettings,
    db: Session,
    *,
    password: str | None = None,
) -> str:
    if password and password.strip():
        return password.strip()
    return try_decrypt_str(settings.smtp_password_encrypted, db) or ""


def _merged_text(override: str | None, saved: str | None) -> str | None:
    if override is not None:
        stripped = override.strip()
        if stripped:
            return stripped
    if saved is None:
        return None
    stripped = saved.strip()
    return stripped or None


def _email_addr(value: str) -> str:
    _name, addr = parseaddr(value)
    return addr.strip() or value.strip()


def _envelope_from(params: SmtpParams) -> str:
    if params.user:
        return params.user
    return _email_addr(params.from_addr)


def resolve_smtp_params(
    settings: InstanceSettings,
    db: Session,
    *,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    from_addr: str | None = None,
    tls: bool | None = None,
) -> SmtpParams:
    resolved_host = _merged_text(host, settings.smtp_host) or ""
    resolved_from = _merged_text(from_addr, settings.smtp_from) or ""
    if not resolved_host or not resolved_from:
        raise ValueError("smtp not configured")
    resolved_user = _merged_text(user, settings.smtp_user)
    resolved_password = resolve_smtp_password(settings, db, password=password)
    resolved_port = port if port is not None else (settings.smtp_port or 587)
    resolved_tls = settings.smtp_tls if tls is None else tls
    if resolved_port == SMTP_SSL_PORT:
        resolved_tls = True
    return SmtpParams(
        host=resolved_host,
        port=resolved_port,
        user=resolved_user,
        password=resolved_password,
        from_addr=resolved_from,
        tls=resolved_tls,
    )


@contextmanager
def _with_smtp(params: SmtpParams):
    use_ssl = params.port == SMTP_SSL_PORT
    smtp: smtplib.SMTP
    if use_ssl:
        smtp = smtplib.SMTP_SSL(params.host, params.port, timeout=SMTP_TIMEOUT_SEC)
    else:
        smtp = smtplib.SMTP(params.host, params.port, timeout=SMTP_TIMEOUT_SEC)
    try:
        smtp.ehlo()
        if params.tls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
        if params.user:
            smtp.login(params.user, params.password)
        yield smtp
    finally:
        try:
            smtp.quit()
        except smtplib.SMTPException:
            smtp.close()


def check_smtp_connection(params: SmtpParams) -> None:
    with _with_smtp(params) as smtp:
        smtp.noop()


def send_smtp_message(params: SmtpParams, to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = params.from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    envelope_from = _envelope_from(params)
    with _with_smtp(params) as smtp:
        smtp.send_message(msg, from_addr=envelope_from, to_addrs=[to_email])
    log.info("mail sent to=%s subject=%s", to_email, subject)


def send_mail(db: Session, to_email: str, subject: str, body: str) -> None:
    settings = db.get(InstanceSettings, 1)
    if settings is None or not smtp_configured(settings):
        raise RuntimeError("smtp not configured")
    params = resolve_smtp_params(settings, db)
    send_smtp_message(params, to_email, subject, body)

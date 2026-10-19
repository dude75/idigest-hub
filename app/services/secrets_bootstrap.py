"""Fail-closed validation for operator secrets in `.env`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiToken, InstanceSettings
from app.session_store import get_session_store


class SecretsConfigError(RuntimeError):
    """SESSION_SECRET missing but the instance already relies on hashed tokens."""


def session_secret_configured() -> bool:
    return bool((get_settings().SESSION_SECRET or "").strip())


def validate_secrets_config(db: Session) -> None:
    """Fail closed when SESSION_SECRET cannot protect existing session/API token hashes."""
    if session_secret_configured():
        return

    inst = db.get(InstanceSettings, 1)
    if inst is not None and inst.bootstrap_done:
        raise SecretsConfigError(
            "SESSION_SECRET is empty but the instance is already configured. "
            "Set SESSION_SECRET in .env and restart."
        )

    if get_session_store().count_active(db):
        raise SecretsConfigError(
            "SESSION_SECRET is empty but active sessions exist in the database. "
            "Set SESSION_SECRET in .env and restart."
        )

    if db.scalar(select(func.count()).select_from(ApiToken).where(ApiToken.revoked_at.is_(None))):
        raise SecretsConfigError(
            "SESSION_SECRET is empty but active API tokens exist in the database. "
            "Set SESSION_SECRET in .env and restart."
        )

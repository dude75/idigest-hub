"""Resolve and cache Telegram bot @username for UI."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from app.crypto import decrypt_str
from app.models import InstanceSettings
from app.services.telegram_api import TelegramApiError, get_me

log = logging.getLogger("app")


def bot_token(settings: InstanceSettings, db) -> str | None:
    if not settings.telegram_enabled:
        return None
    raw = settings.telegram_bot_token_encrypted
    if not (raw or "").strip():
        return None
    return decrypt_str(raw, db)


def telegram_bot_public(settings: InstanceSettings) -> tuple[str | None, str | None]:
    """Return (username without @, https://t.me/... URL)."""
    raw = (settings.telegram_bot_username or "").strip().lstrip("@")
    if not raw:
        return None, None
    return raw, f"https://t.me/{raw}"


async def fetch_bot_username(settings: InstanceSettings, db: Session) -> str | None:
    token = bot_token(settings, db)
    if not token:
        settings.telegram_bot_username = None
        return None
    try:
        me = await get_me(token, settings=settings, db=db)
    except Exception as exc:
        log.warning("telegram getMe failed: %s", exc)
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None
    username = me.get("username")
    if isinstance(username, str) and username.strip():
        settings.telegram_bot_username = username.strip().lstrip("@")
        return settings.telegram_bot_username
    settings.telegram_bot_username = None
    return None


def refresh_bot_username_sync(db: Session, settings: InstanceSettings) -> str | None:
    try:
        return asyncio.run(fetch_bot_username(settings, db))
    except RuntimeError:
        # nested event loop (e.g. inside async worker) — skip refresh
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None
    except Exception as exc:
        log.warning("telegram username refresh failed: %s", exc)
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None

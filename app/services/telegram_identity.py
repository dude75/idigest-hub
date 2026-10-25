"""Resolve and cache Telegram bot @username for UI."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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


def _telegram_bot_id_from_me(me: dict[str, Any]) -> int | None:
    raw = me.get("id")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def apply_telegram_bot_me(db: Session, settings: InstanceSettings, me: dict[str, Any]) -> bool:
    """Apply getMe fields. Returns True if telegram_bot_id changed."""
    from app.services.telegram_links import clear_all_telegram_links

    new_id = _telegram_bot_id_from_me(me)
    old_id = settings.telegram_bot_id
    id_changed = new_id is not None and old_id is not None and old_id != new_id
    if id_changed:
        clear_all_telegram_links(db)
        log.info("telegram bot id changed %s -> %s; cleared user links", old_id, new_id)
    if new_id is not None:
        settings.telegram_bot_id = new_id
    username = me.get("username")
    if isinstance(username, str) and username.strip():
        settings.telegram_bot_username = username.strip().lstrip("@")
    else:
        settings.telegram_bot_username = None
    return id_changed


def ensure_telegram_bot_identity(db: Session, settings: InstanceSettings) -> None:
    """Load bot @username and numeric id from Telegram when not cached."""
    if not bot_token(settings, db):
        return
    if (settings.telegram_bot_username or "").strip() and settings.telegram_bot_id is not None:
        return
    refresh_bot_username_sync(db, settings)


def telegram_bot_public_resolved(db: Session, settings: InstanceSettings) -> tuple[str | None, str | None]:
    """Cached username for UI; refresh from Telegram when identity incomplete."""
    ensure_telegram_bot_identity(db, settings)
    return telegram_bot_public(settings)


async def fetch_bot_username(settings: InstanceSettings, db: Session) -> str | None:
    token = bot_token(settings, db)
    if not token:
        settings.telegram_bot_username = None
        settings.telegram_bot_id = None
        return None
    try:
        me = await get_me(token, settings=settings, db=db)
    except Exception as exc:
        log.warning("telegram getMe failed: %s", exc)
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None
    apply_telegram_bot_me(db, settings, me)
    return (settings.telegram_bot_username or "").strip().lstrip("@") or None


def refresh_bot_username_sync(db: Session, settings: InstanceSettings) -> str | None:
    try:
        return asyncio.run(fetch_bot_username(settings, db))
    except RuntimeError:
        # nested event loop (e.g. inside async worker) — skip refresh
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None
    except Exception as exc:
        log.warning("telegram username refresh failed: %s", exc)
        return (settings.telegram_bot_username or "").strip().lstrip("@") or None

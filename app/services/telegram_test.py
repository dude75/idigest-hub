"""Telegram Bot API connection test for instance admin."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.crypto import decrypt_str
from app.models import InstanceSettings
from app.services.telegram_api import TelegramApiError, get_me


def resolve_telegram_test_token(settings: InstanceSettings, db: Session, override: str | None) -> str | None:
    raw = (override or "").strip()
    if raw:
        return raw
    encrypted = (settings.telegram_bot_token_encrypted or "").strip()
    if not encrypted:
        return None
    return decrypt_str(encrypted, db)


async def test_telegram_connection(
    db: Session,
    settings: InstanceSettings,
    *,
    token: str,
    use_proxy: bool | None = None,
) -> dict[str, str | None]:
    prev_proxy = settings.telegram_use_proxy
    if use_proxy is not None:
        settings.telegram_use_proxy = use_proxy
    try:
        me = await get_me(token, settings=settings, db=db)
    finally:
        settings.telegram_use_proxy = prev_proxy
    username_raw = me.get("username")
    username = None
    if isinstance(username_raw, str) and username_raw.strip():
        username = username_raw.strip().lstrip("@")
    first_name = me.get("first_name")
    first = first_name.strip() if isinstance(first_name, str) and first_name.strip() else None
    bot_url = f"https://t.me/{username}" if username else None
    return {"username": username, "first_name": first, "bot_url": bot_url}


def test_telegram_connection_sync(
    db: Session,
    settings: InstanceSettings,
    *,
    token: str,
    use_proxy: bool | None = None,
) -> dict[str, str | None]:
    return asyncio.run(test_telegram_connection(db, settings, token=token, use_proxy=use_proxy))


__all__ = ["TelegramApiError", "resolve_telegram_test_token", "test_telegram_connection_sync"]

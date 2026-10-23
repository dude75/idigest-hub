"""Telegram bot lifecycle: webhook registration or long polling."""

from __future__ import annotations

import asyncio
import logging

from app.deps import get_instance_settings
from app.services.auth_helpers import public_base_url
from app.services.telegram_api import TelegramApiError, delete_webhook, get_updates, set_my_commands, set_webhook
from app.services.telegram_commands import BOT_MENU_COMMANDS
from app.services.telegram_bot import handle_update
from app.services.telegram_identity import bot_token

log = logging.getLogger("app")

_offset: int | None = None


async def configure_telegram_transport(stop_event: asyncio.Event) -> str:
    """Returns mode: 'webhook', 'poll', or 'off'."""
    from app.db import SessionLocal, get_engine

    get_engine()
    if SessionLocal is None:
        return "off"
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        token = bot_token(settings, db)
        if not token:
            return "off"
        from app.services.telegram_identity import fetch_bot_username

        await fetch_bot_username(settings, db)
        try:
            await set_my_commands(token, settings=settings, db=db, commands=BOT_MENU_COMMANDS)
        except TelegramApiError as exc:
            log.warning("telegram setMyCommands: %s", exc)
        db.commit()
        base = public_base_url(db)
        secret = (settings.telegram_webhook_secret or "").strip()
        if base and secret:
            webhook_url = f"{base.rstrip('/')}/api/v1/integrations/telegram/webhook"
            try:
                await set_webhook(token, settings=settings, db=db, webhook_url=webhook_url, secret_token=secret)
                log.info("telegram webhook registered")
                return "webhook"
            except TelegramApiError as exc:
                log.warning("telegram setWebhook failed, falling back to long poll: %s", exc)
        try:
            await delete_webhook(token, settings=settings, db=db)
        except TelegramApiError as exc:
            log.warning("telegram deleteWebhook: %s", exc)
        return "poll"


async def telegram_poll_loop(stop_event: asyncio.Event) -> None:
    from app.db import SessionLocal, get_engine

    get_engine()
    if SessionLocal is None:
        return
    global _offset
    while not stop_event.is_set():
        with SessionLocal() as db:
            settings = get_instance_settings(db)
            token = bot_token(settings, db)
            if not token:
                await asyncio.wait_for(stop_event.wait(), timeout=30.0)
                continue
        try:
            updates = await get_updates(
                token,
                settings=settings,
                db=db,
                offset=_offset,
                timeout=50,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("telegram getUpdates: %s", exc)
            await asyncio.sleep(3.0)
            continue
        for update in updates:
            if not isinstance(update, dict):
                continue
            uid = update.get("update_id")
            if isinstance(uid, int):
                _offset = uid + 1
            with SessionLocal() as db:
                settings = get_instance_settings(db)
                token = bot_token(settings, db)
                if not token:
                    break
                try:
                    await handle_update(db, update, token=token, settings=settings, bot_username=None)
                except Exception:
                    log.exception("telegram handle_update failed")
                    db.rollback()


async def telegram_runtime(stop_event: asyncio.Event) -> None:
    mode = await configure_telegram_transport(stop_event)
    if mode == "off":
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                from app.db import SessionLocal, get_engine

                get_engine()
                if SessionLocal is None:
                    continue
                with SessionLocal() as db:
                    settings = get_instance_settings(db)
                    if bot_token(settings, db):
                        mode = await configure_telegram_transport(stop_event)
                        if mode == "poll":
                            break
                        if mode == "webhook":
                            return
        return
    if mode == "webhook":
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=300.0)
            except asyncio.TimeoutError:
                pass
        return
    await telegram_poll_loop(stop_event)


async def verify_bot_token(settings, db) -> dict:
    from app.services.telegram_api import get_me

    token = bot_token(settings, db)
    if not token:
        raise ValueError("telegram not configured")
    return await get_me(token, settings=settings, db=db)

"""Telegram bot lifecycle: webhook registration or long polling."""

from __future__ import annotations

import asyncio
import logging

from app.deps import get_instance_settings
from app.services.auth_helpers import public_base_url
from app.services.telegram_api import (
    TelegramApiError,
    delete_webhook,
    get_updates,
    get_webhook_info,
    set_my_commands,
    set_webhook,
)
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

        username = await fetch_bot_username(settings, db)
        try:
            await set_my_commands(token, settings=settings, db=db, commands=BOT_MENU_COMMANDS)
        except TelegramApiError as exc:
            log.warning("telegram setMyCommands: %s", exc)
        db.commit()
        base = public_base_url(db)
        secret = (settings.telegram_webhook_secret or "").strip()
        use_proxy = bool(settings.outbound_proxy_enabled and settings.telegram_use_proxy)
        bot_label = f"@{username}" if username else "bot"
        if base and secret:
            webhook_url = f"{base.rstrip('/')}/api/v1/integrations/telegram/webhook"
            try:
                await set_webhook(token, settings=settings, db=db, webhook_url=webhook_url, secret_token=secret)
                try:
                    info = await get_webhook_info(token, settings=settings, db=db)
                    pending = info.get("pending_update_count")
                    last_err = (info.get("last_error_message") or "").strip()
                    if last_err:
                        log.warning(
                            "telegram webhook registered for %s (%s, proxy=%s) pending=%s last_error=%s",
                            webhook_url,
                            bot_label,
                            use_proxy,
                            pending,
                            last_err,
                        )
                    else:
                        log.info(
                            "telegram webhook registered for %s (%s, proxy=%s, pending=%s)",
                            webhook_url,
                            bot_label,
                            use_proxy,
                            pending,
                        )
                except TelegramApiError as exc:
                    log.info(
                        "telegram webhook registered for %s (%s, proxy=%s); getWebhookInfo: %s",
                        webhook_url,
                        bot_label,
                        use_proxy,
                        exc,
                    )
                return "webhook"
            except TelegramApiError as exc:
                log.warning("telegram setWebhook failed, falling back to long poll: %s", exc)
        try:
            await delete_webhook(token, settings=settings, db=db)
        except TelegramApiError as exc:
            log.warning("telegram deleteWebhook: %s", exc)
        log.info("telegram long polling active (%s, proxy=%s)", bot_label, use_proxy)
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


async def _telegram_webhook_wait(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300.0)
        except asyncio.TimeoutError:
            pass


def schedule_telegram_reconfigure() -> None:
    """Re-register webhook / long poll after instance settings change (best-effort)."""
    from app.services.telegram_bot import run_on_hub_loop

    async def _run() -> None:
        try:
            await configure_telegram_transport(asyncio.Event())
        except Exception:
            log.exception("telegram reconfigure failed")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        if not run_on_hub_loop(_run()):
            log.debug("telegram reconfigure skipped: hub event loop not ready")


async def telegram_runtime(stop_event: asyncio.Event) -> None:
    mode = await configure_telegram_transport(stop_event)
    if mode == "off":
        use_poll = False
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
                            use_poll = True
                            break
                        if mode == "webhook":
                            await _telegram_webhook_wait(stop_event)
                            return
        if not use_poll:
            return
    if mode == "webhook":
        await _telegram_webhook_wait(stop_event)
        return
    await telegram_poll_loop(stop_event)


async def verify_bot_token(settings, db) -> dict:
    from app.services.telegram_api import get_me

    token = bot_token(settings, db)
    if not token:
        raise ValueError("telegram not configured")
    return await get_me(token, settings=settings, db=db)

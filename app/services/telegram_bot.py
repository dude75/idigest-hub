"""Telegram update handlers."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALLOWED_AUDIO_SUFFIXES, MAX_UPLOAD_BYTES_CAP
from app.deps import get_instance_settings
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import Audio, Task, User, new_id
from app.routers.tasks import ImportBody, enqueue_import_task
from app.services.billing import upload_limit
from app.services.dispatcher import schedule_locked_tick_asyncio
from app.services.storage import PayloadTooLarge, get_storage
from app.services.telegram_api import TelegramApiError, download_file_bytes, get_file_path, send_message
from app.services.telegram_context import auth_context_for_user
from app.services.telegram_links import consume_link_code, link_for_telegram_user
from app.services.upload_validation import InvalidAudioContent
from app.timeutil import utcnow

log = logging.getLogger("app")

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _locale(user: User | None, fallback: str = "en") -> str:
    if user is None:
        return fallback
    return user.locale or fallback


async def handle_update(db: Session, update: dict, *, token: str, settings, bot_username: str | None) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    telegram_user_id = from_user.get("id")
    if chat_id is None or telegram_user_id is None:
        return
    chat_id_s = str(chat_id)
    tg_user_s = str(telegram_user_id)
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            try:
                user = consume_link_code(db, code=parts[1], telegram_user_id=tg_user_s, chat_id=chat_id_s)
                db.commit()
                loc = _locale(user)
                await send_message(
                    token,
                    settings=settings,
                    db=db,
                    chat_id=chat_id_s,
                    text=t(loc, "telegram.link_ok"),
                )
                return
            except ValueError as exc:
                db.rollback()
                reason = str(exc)
                loc = "en"
                if reason == "telegram_taken":
                    msg = t(loc, "telegram.link_taken")
                else:
                    msg = t(loc, "telegram.link_invalid")
                await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=msg)
                return
        link = link_for_telegram_user(db, tg_user_s)
        loc = _locale(db.get(User, link.user_id) if link else None)
        if link is None:
            await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t(loc, "telegram.welcome_unlinked"))
        else:
            await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t(loc, "telegram.welcome_linked"))
        return

    link = link_for_telegram_user(db, tg_user_s)
    if link is None:
        await send_message(
            token,
            settings=settings,
            db=db,
            chat_id=chat_id_s,
            text=t("en", "telegram.need_link"),
        )
        return

    user = db.get(User, link.user_id)
    if user is None or user.disabled_at is not None:
        await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t("en", "telegram.need_link"))
        return

    loc = _locale(user)

    if text.startswith("/link"):
        await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t(loc, "telegram.link_help"))
        return

    if text.startswith("/help"):
        await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t(loc, "telegram.help"))
        return

    if text.startswith("/status"):
        await _cmd_status(db, token, settings, chat_id_s, user, loc)
        return

    url_match = _URL_RE.search(text) if text else None
    if url_match:
        await _handle_url(db, token, settings, chat_id_s, user, loc, url_match.group(0).rstrip(").,]"))
        return

    if message.get("voice") or message.get("audio") or message.get("document"):
        await _handle_file(db, token, settings, chat_id_s, user, loc, message)
        return

    if text:
        await send_message(token, settings=settings, db=db, chat_id=chat_id_s, text=t(loc, "telegram.unknown"))


async def _cmd_status(db: Session, token: str, settings, chat_id: str, user: User, loc: str) -> None:
    rows = db.scalars(
        select(Task)
        .where(Task.user_id == user.id, Task.status.in_(("queued", "running")))
        .order_by(Task.created_at.desc())
        .limit(5)
    ).all()
    if not rows:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.status_empty"))
        return
    lines = [t(loc, "telegram.status_header")]
    for row in rows:
        meta = row.meta_json or {}
        stage = meta.get("stage") or row.status
        lines.append(f"• {row.type} `{row.id[:8]}…` — {stage}")
    await send_message(token, settings=settings, db=db, chat_id=chat_id, text="\n".join(lines))


async def _handle_url(db: Session, token: str, settings, chat_id: str, user: User, loc: str, url: str) -> None:
    if not settings.import_enabled:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.import_disabled"))
        return
    try:
        ctx = auth_context_for_user(db, user)
        ctx.require_org()
    except Exception:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.no_org"))
        return
    try:
        task = enqueue_import_task(db, ctx, ImportBody(url=url, transcribe=False))
        meta = dict(task.meta_json or {})
        meta["notify_telegram"] = True
        meta["telegram_chat_id"] = chat_id
        task.meta_json = meta
        db.commit()
        schedule_locked_tick_asyncio(task.id, refresh_health=False)
        await send_message(
            token,
            settings=settings,
            db=db,
            chat_id=chat_id,
            text=t(loc, "telegram.import_queued", task_id=task.id),
        )
    except ApiError as exc:
        db.rollback()
        key = f"telegram.err_{exc.code.value}"
        text = t(loc, key)
        if text == key:
            text = t(loc, "telegram.import_failed")
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=text)
    except Exception:
        db.rollback()
        log.exception("telegram import failed")
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.import_failed"))


async def _handle_file(db: Session, token: str, settings, chat_id: str, user: User, loc: str, message: dict) -> None:
    file_obj = message.get("voice") or message.get("audio") or message.get("document")
    if not isinstance(file_obj, dict):
        return
    file_id = file_obj.get("file_id")
    file_name = file_obj.get("file_name") or ("voice.ogg" if message.get("voice") else "audio.bin")
    if not file_id:
        return
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.invalid_file"))
        return
    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.no_org"))
        return
    try:
        path = await get_file_path(token, settings=settings, db=db, file_id=str(file_id))
        data = await download_file_bytes(token, settings=settings, db=db, file_path=path)
        limit = min(upload_limit(org.tariff), MAX_UPLOAD_BYTES_CAP)
        if len(data) > limit:
            await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.file_too_large"))
            return
        audio_id = new_id()
        storage = get_storage()
        storage_path = storage.save_bytes(audio_id, suffix, data, max_bytes=limit)
        row = Audio(
            id=audio_id,
            org_id=org.id,
            owner_user_id=user.id,
            storage_path=storage_path,
            original_filename=file_name,
            created_at=utcnow(),
        )
        db.add(row)
        db.flush()
        from app.services.source_tags import tag_audio_file_upload

        tag_audio_file_upload(db, user_id=user.id, audio_id=audio_id, from_microphone=bool(message.get("voice")))
        db.commit()
        await send_message(
            token,
            settings=settings,
            db=db,
            chat_id=chat_id,
            text=t(loc, "telegram.upload_ok", audio_id=audio_id),
        )
    except (PayloadTooLarge, InvalidAudioContent):
        db.rollback()
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.invalid_file"))
    except TelegramApiError as exc:
        db.rollback()
        log.warning("telegram file download: %s", exc)
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.download_failed"))
    except Exception:
        db.rollback()
        log.exception("telegram upload failed")
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.upload_failed"))


def telegram_notify_meta(source: dict | None) -> dict:
    if not source or not source.get("notify_telegram"):
        return {}
    chat_id = source.get("telegram_chat_id")
    if not chat_id:
        return {}
    return {"notify_telegram": True, "telegram_chat_id": str(chat_id)}


def _telegram_chat_id(db: Session, task: Task, meta: dict) -> str | None:
    raw = meta.get("telegram_chat_id")
    if raw:
        return str(raw)
    if meta.get("notify_telegram"):
        from app.services.telegram_links import link_for_user

        link = link_for_user(db, task.user_id)
        if link is not None:
            return link.chat_id
    return None


def _task_terminal_message(db: Session, task: Task, loc: str) -> str:
    meta = task.meta_json or {}
    if task.status != "success":
        code = task.error_code or "error"
        return t(loc, "telegram.task_error", task_id=task.id, code=code)
    if task.type == "import":
        title = (meta.get("title") or meta.get("platform") or "").strip()
        audio_id = task.audio_id or ""
        if title:
            return t(loc, "telegram.task_import_success", title=title, audio_id=audio_id)
        return t(loc, "telegram.task_import_success_short", audio_id=audio_id)
    if task.type == "capture":
        room = (meta.get("meeting_room") or meta.get("meeting_host") or "").strip()
        audio_id = task.audio_id or ""
        return t(loc, "telegram.task_capture_success", room=room or "—", audio_id=audio_id)
    if task.type == "transcribe":
        tid = task.produced_transcript_id or ""
        return t(loc, "telegram.task_transcribe_success", transcript_id=tid)
    if task.type == "summarize":
        sid = task.produced_summary_id or ""
        return t(loc, "telegram.task_summarize_success", summary_id=sid)
    return t(loc, "telegram.task_success", task_id=task.id, task_type=task.type)


def notify_task_terminal(db: Session, task: Task) -> None:
    """Best-effort push when a telegram-originated task finishes."""
    meta = task.meta_json or {}
    if not meta.get("notify_telegram"):
        return
    chat_id = _telegram_chat_id(db, task, meta)
    if not chat_id:
        return
    settings = get_instance_settings(db)
    if not settings.telegram_enabled or not (settings.telegram_bot_token_encrypted or "").strip():
        return
    from app.crypto import decrypt_str

    token = decrypt_str(settings.telegram_bot_token_encrypted, db)
    if not token:
        return
    user = db.get(User, task.user_id)
    loc = _locale(user)
    text = _task_terminal_message(db, task, loc)
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _send() -> None:
        try:
            await send_message(token, settings=settings, db=db, chat_id=str(chat_id), text=text)
        except Exception:
            log.warning("telegram notify failed task=%s", task.id, exc_info=True)

    loop.create_task(_send())

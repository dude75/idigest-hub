"""Telegram update handlers."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALLOWED_AUDIO_SUFFIXES, MAX_UPLOAD_BYTES_CAP
from app.deps import get_instance_settings
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import Audio, Skill, Summary, Task, Transcript, User, new_id
from app.routers.tasks import ImportBody, TranscribeBody, enqueue_import_task, enqueue_transcribe_task
from app.services.billing import upload_limit
from app.services.dispatcher import schedule_locked_tick_asyncio
from app.services.storage import PayloadTooLarge, get_storage
from app.services.telegram_api import (
    TelegramApiError,
    answer_callback_query,
    download_file_bytes,
    get_file_path,
    send_message,
)
from app.services.telegram_context import auth_context_for_user
from app.services.telegram_links import consume_link_code, link_for_telegram_user
from app.services.upload_validation import InvalidAudioContent
from app.timeutil import utcnow

log = logging.getLogger("app")

_hub_event_loop: AbstractEventLoop | None = None

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def register_hub_event_loop(loop: AbstractEventLoop) -> None:
    """Main asyncio loop (uvicorn lifespan) — used to deliver task notifications from worker threads."""
    global _hub_event_loop
    _hub_event_loop = loop


def run_on_hub_loop(coro) -> bool:
    """Schedule a coroutine on the hub loop from a sync context (e.g. settings PATCH)."""
    loop = _hub_event_loop
    if loop is None or loop.is_closed():
        return False
    asyncio.run_coroutine_threadsafe(coro, loop)
    return True
_SKILL_CALLBACK_PREFIX = "ss:"
_VIEW_SUMMARY_CALLBACK_PREFIX = "vs:"
_TRANSCRIBE_AUDIO_CALLBACK_PREFIX = "ta:"
_SUMMARY_TRANSCRIPT_CALLBACK_PREFIX = "tr:"
_TELEGRAM_PICK_LIST_LIMIT = 10
_pending_summary_transcript: dict[str, str] = {}


def _parse_command(text: str) -> tuple[str, list[str]]:
    if not text.startswith("/"):
        return "", []
    parts = text.split()
    if not parts:
        return "", []
    command = parts[0].split("@", 1)[0].lower()
    return command, parts[1:]


def _attach_telegram_notify(task: Task, chat_id: str) -> None:
    meta = dict(task.meta_json or {})
    meta["notify_telegram"] = True
    meta["telegram_chat_id"] = chat_id
    task.meta_json = meta


def _locale(user: User | None, fallback: str = "en") -> str:
    if user is None:
        return fallback
    return user.locale or fallback


def _short_id(value: str) -> str:
    return value[:8] if len(value) >= 8 else value


def _audio_display_name(db: Session, audio_id: str | None) -> str:
    if not audio_id:
        return "—"
    row = db.get(Audio, audio_id)
    if row is None:
        return _short_id(audio_id)
    name = (row.original_filename or "").strip()
    if name:
        return Path(name).name
    return _short_id(audio_id)


def _transcript_display_name(db: Session, transcript_id: str | None) -> str:
    if not transcript_id:
        return "—"
    row = db.get(Transcript, transcript_id)
    if row is None:
        return _short_id(transcript_id)
    title = (row.title or "").strip()
    if title:
        return title
    if row.source_audio_id:
        return _audio_display_name(db, row.source_audio_id)
    return _short_id(transcript_id)


def _summary_display_name(db: Session, summary_id: str | None) -> str:
    if not summary_id:
        return "—"
    row = db.get(Summary, summary_id)
    if row is None:
        return _short_id(summary_id)
    title = (row.title or "").strip()
    if title:
        return title
    if row.source_transcript_id:
        return _transcript_display_name(db, row.source_transcript_id)
    return _short_id(summary_id)


def _skill_display_name(db: Session, skill_id: str) -> str:
    row = db.get(Skill, skill_id)
    if row is not None and (row.name or "").strip():
        return row.name.strip()
    return _short_id(skill_id)


def _skill_labels(db: Session, skill_ids: list[str]) -> str:
    if not skill_ids:
        return "—"
    names = [_skill_display_name(db, sid) for sid in skill_ids[:4]]
    if len(skill_ids) > 4:
        names.append("…")
    return ", ".join(names)


def _import_source_label(meta: dict) -> str:
    title = (meta.get("title") or "").strip()
    if title:
        return title
    url = (meta.get("url") or "").strip()
    if url:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc
        return url[:60] + ("…" if len(url) > 60 else "")
    platform = (meta.get("platform") or "").strip()
    if platform:
        return platform
    return "—"


async def handle_update(db: Session, update: dict, *, token: str, settings, bot_username: str | None) -> None:
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        await _handle_callback_query(db, callback, token=token, settings=settings)
        return

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

    command, args = _parse_command(text)
    if command == "/transcribe":
        await _cmd_transcribe(db, token, settings, chat_id_s, user, loc, args)
        return
    if command == "/summary":
        await _cmd_summary(db, token, settings, chat_id_s, user, loc, args)
        return
    if command == "/viewsummary":
        await _cmd_viewsummary(db, token, settings, chat_id_s, user, loc)
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


def _resolve_audio(db: Session, ctx, org, ref: str | None) -> Audio | None:
    from app.services.access import can_use_audio

    if ref:
        exact = db.get(Audio, ref)
        if exact is not None and exact.org_id == org.id and can_use_audio(ctx, db, exact):
            return exact
        prefix = ref.strip().lower()
        if len(prefix) >= 4:
            rows = db.scalars(
                select(Audio).where(Audio.org_id == org.id, Audio.id.startswith(prefix)).limit(20)
            ).all()
            matches = [row for row in rows if can_use_audio(ctx, db, row)]
            if len(matches) == 1:
                return matches[0]
        return None
    rows = db.scalars(
        select(Audio).where(Audio.org_id == org.id).order_by(Audio.created_at.desc()).limit(40)
    ).all()
    for row in rows:
        if can_use_audio(ctx, db, row):
            return row
    return None


def _resolve_transcript(db: Session, ctx, org, ref: str | None) -> Transcript | None:
    from app.services.access import can_use_transcript

    if ref:
        exact = db.get(Transcript, ref)
        if exact is not None and exact.org_id == org.id and can_use_transcript(ctx, db, exact):
            return exact
        prefix = ref.strip().lower()
        if len(prefix) >= 4:
            rows = db.scalars(
                select(Transcript)
                .where(Transcript.org_id == org.id, Transcript.id.startswith(prefix))
                .limit(20)
            ).all()
            matches = [row for row in rows if can_use_transcript(ctx, db, row)]
            if len(matches) == 1:
                return matches[0]
        return None
    rows = db.scalars(
        select(Transcript).where(Transcript.org_id == org.id).order_by(Transcript.created_at.desc()).limit(40)
    ).all()
    for row in rows:
        if can_use_transcript(ctx, db, row):
            return row
    return None


def _visible_skill_map(db: Session, ctx):
    from app.routers.skills import _visible_skills

    return {skill.id: skill for skill, _ in _visible_skills(db, ctx, scope=None)}


def _resolve_skill_ids(db: Session, ctx, tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    visible = _visible_skill_map(db, ctx)
    by_name: dict[str, list[str]] = {}
    for sid, skill in visible.items():
        key = (skill.name or "").strip().casefold()
        if key:
            by_name.setdefault(key, []).append(sid)
    resolved: list[str] = []
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if token in visible:
            resolved.append(token)
            continue
        prefix = token.lower()
        id_matches = [sid for sid in visible if sid.lower().startswith(prefix)]
        if len(id_matches) == 1:
            resolved.append(id_matches[0])
            continue
        name_matches = by_name.get(token.casefold(), [])
        if len(name_matches) == 1:
            resolved.append(name_matches[0])
            continue
        raise ValueError("ambiguous_skill")
    return list(dict.fromkeys(resolved))


def _filter_usable_skill_ids(db: Session, ctx, org, skill_ids: list[str]) -> list[str]:
    from app.routers.tasks import _validate_summarize_skills

    kept: list[str] = []
    for sid in skill_ids:
        try:
            _validate_summarize_skills(ctx, db, org, [sid])
        except ApiError:
            continue
        kept.append(sid)
    return list(dict.fromkeys(kept))


def _sorted_visible_skills(db: Session, ctx) -> list[Skill]:
    return sorted(_visible_skill_map(db, ctx).values(), key=lambda s: (s.name or "").lower())


def _telegram_text_chunks(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def _summary_button_label(db: Session, summary: Summary) -> str:
    title = _summary_display_name(db, summary.id)
    raw_skills = summary.skill_ids_json or []
    skill_ids = [str(sid) for sid in raw_skills if sid]
    if skill_ids:
        label = f"{title} ({_skill_labels(db, skill_ids)})"
    else:
        label = title
    if len(label) > 60:
        return label[:57] + "…"
    return label


def _pick_list_button_label(label: str) -> str:
    if len(label) > 60:
        return label[:57] + "…"
    return label


def _view_summary_inline_keyboard(summaries: list[Summary], db: Session) -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []
    for summary in summaries:
        rows.append(
            [
                {
                    "text": _summary_button_label(db, summary),
                    "callback_data": f"{_VIEW_SUMMARY_CALLBACK_PREFIX}{summary.id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def _audio_inline_keyboard(audios: list[Audio], db: Session) -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []
    for audio in audios:
        rows.append(
            [
                {
                    "text": _pick_list_button_label(_audio_display_name(db, audio.id)),
                    "callback_data": f"{_TRANSCRIBE_AUDIO_CALLBACK_PREFIX}{audio.id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def _transcript_inline_keyboard(transcripts: list[Transcript], db: Session) -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []
    for transcript in transcripts:
        rows.append(
            [
                {
                    "text": _pick_list_button_label(_transcript_display_name(db, transcript.id)),
                    "callback_data": f"{_SUMMARY_TRANSCRIPT_CALLBACK_PREFIX}{transcript.id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def _skill_inline_keyboard(skills: list[Skill]) -> dict[str, list[list[dict[str, str]]]]:
    rows: list[list[dict[str, str]]] = []
    for skill in skills[:20]:
        name = (skill.name or skill.id).strip()
        if len(name) > 60:
            name = name[:57] + "…"
        rows.append([{"text": name, "callback_data": f"{_SKILL_CALLBACK_PREFIX}{skill.id}"}])
    return {"inline_keyboard": rows}


async def _offer_summary_skill_pick(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    ctx,
    loc: str,
    transcript: Transcript,
) -> None:
    skills = _sorted_visible_skills(db, ctx)
    if not skills:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.skills_empty"))
        return
    _pending_summary_transcript[chat_id] = transcript.id
    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(loc, "telegram.summary_pick_skill"),
        reply_markup=_skill_inline_keyboard(skills),
    )


async def _enqueue_summary(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    ctx,
    loc: str,
    transcript: Transcript,
    skill_ids: list[str],
) -> None:
    from app.services.mcp_library import create_summary_payload

    payload = create_summary_payload(
        db,
        ctx,
        transcript_id=transcript.id,
        skill_ids=skill_ids,
    )
    task = db.get(Task, payload["task_id"])
    if task is not None:
        _attach_telegram_notify(task, chat_id)
    db.commit()
    task_id = payload["task_id"]
    schedule_locked_tick_asyncio(task_id, refresh_health=False)
    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(
            loc,
            "telegram.summary_queued",
            name=_transcript_display_name(db, transcript.id),
            skill=_skill_labels(db, skill_ids),
        ),
    )


async def _handle_callback_query(db: Session, callback: dict, *, token: str, settings) -> None:
    callback_id = callback.get("id")
    data = str(callback.get("data") or "")
    from_user = callback.get("from") or {}
    telegram_user_id = from_user.get("id")
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not callback_id or telegram_user_id is None or chat_id is None:
        return
    chat_id_s = str(chat_id)
    tg_user_s = str(telegram_user_id)

    async def _answer(text: str | None = None) -> None:
        try:
            await answer_callback_query(
                token,
                settings=settings,
                db=db,
                callback_query_id=str(callback_id),
                text=text,
            )
        except TelegramApiError as exc:
            log.warning("telegram answerCallbackQuery: %s", exc)

    if data.startswith(_VIEW_SUMMARY_CALLBACK_PREFIX):
        await _handle_view_summary_callback(
            db,
            data[len(_VIEW_SUMMARY_CALLBACK_PREFIX) :],
            token=token,
            settings=settings,
            chat_id_s=chat_id_s,
            tg_user_s=tg_user_s,
            answer=_answer,
        )
        return

    if data.startswith(_TRANSCRIBE_AUDIO_CALLBACK_PREFIX):
        await _handle_transcribe_audio_callback(
            db,
            data[len(_TRANSCRIBE_AUDIO_CALLBACK_PREFIX) :],
            token=token,
            settings=settings,
            chat_id_s=chat_id_s,
            tg_user_s=tg_user_s,
            answer=_answer,
        )
        return

    if data.startswith(_SUMMARY_TRANSCRIPT_CALLBACK_PREFIX):
        await _handle_summary_transcript_callback(
            db,
            data[len(_SUMMARY_TRANSCRIPT_CALLBACK_PREFIX) :],
            token=token,
            settings=settings,
            chat_id_s=chat_id_s,
            tg_user_s=tg_user_s,
            answer=_answer,
        )
        return

    if not data.startswith(_SKILL_CALLBACK_PREFIX):
        await _answer()
        return

    skill_id = data[len(_SKILL_CALLBACK_PREFIX) :]
    transcript_id = _pending_summary_transcript.get(chat_id_s)
    if not transcript_id:
        await _answer(t("en", "telegram.summary_pick_expired"))
        return

    link = link_for_telegram_user(db, tg_user_s)
    if link is None:
        await _answer(t("en", "telegram.need_link"))
        return
    user = db.get(User, link.user_id)
    if user is None or user.disabled_at is not None:
        await _answer(t("en", "telegram.need_link"))
        return
    loc = _locale(user)

    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await _answer(t(loc, "telegram.no_org"))
        return

    transcript = db.get(Transcript, transcript_id)
    if transcript is None or transcript.org_id != org.id:
        _pending_summary_transcript.pop(chat_id_s, None)
        await _answer(t(loc, "telegram.transcript_not_found"))
        return
    from app.services.access import can_use_transcript

    if not can_use_transcript(ctx, db, transcript):
        _pending_summary_transcript.pop(chat_id_s, None)
        await _answer(t(loc, "telegram.transcript_not_found"))
        return

    filtered = _filter_usable_skill_ids(db, ctx, org, [skill_id])
    if not filtered:
        await _answer(t(loc, "telegram.skill_ambiguous"))
        return

    _pending_summary_transcript.pop(chat_id_s, None)
    try:
        await _enqueue_summary(db, token, settings, chat_id_s, ctx, loc, transcript, filtered)
        await _answer(
            t(loc, "telegram.summary_queued_short", skill=_skill_display_name(db, filtered[0])),
        )
    except (ApiError, ValueError, PermissionError) as exc:
        db.rollback()
        code = getattr(getattr(exc, "code", None), "value", None) or "error"
        await _answer(t(loc, "telegram.task_enqueue_failed", code=code))
    except Exception:
        db.rollback()
        log.exception("telegram summary callback failed")
        await _answer(t(loc, "telegram.summary_failed"))


def _list_recent_summaries(db: Session, ctx, limit: int = _TELEGRAM_PICK_LIST_LIMIT) -> list[Summary]:
    from app.services.access import ensure_library_readable
    from app.services.library_helpers import list_filter

    rows = list_filter(ctx, db, Summary, "summary", include_hidden=False, limit=limit)
    out: list[Summary] = []
    for row in rows:
        if ensure_library_readable(ctx, db, row, "summary"):
            out.append(row)
    return out


def _list_recent_audios(db: Session, ctx, limit: int = _TELEGRAM_PICK_LIST_LIMIT) -> list[Audio]:
    from app.services.access import can_use_audio
    from app.services.library_helpers import list_filter

    rows = list_filter(ctx, db, Audio, "audio", include_hidden=False, limit=limit)
    out: list[Audio] = []
    for row in rows:
        if can_use_audio(ctx, db, row):
            out.append(row)
    return out


def _list_recent_transcripts(db: Session, ctx, limit: int = _TELEGRAM_PICK_LIST_LIMIT) -> list[Transcript]:
    from app.services.access import can_use_transcript
    from app.services.library_helpers import list_filter

    rows = list_filter(ctx, db, Transcript, "transcript", include_hidden=False, limit=limit)
    out: list[Transcript] = []
    for row in rows:
        if can_use_transcript(ctx, db, row):
            out.append(row)
    return out


async def _send_summary_content(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    summary: Summary,
    loc: str,
) -> None:
    from app.crypto import decrypt_str

    body = decrypt_str(summary.body_encrypted, db)
    header = t(loc, "telegram.viewsummary_body_header", name=_summary_display_name(db, summary.id))
    full = f"{header}\n\n{body}".strip() if body.strip() else header
    for chunk in _telegram_text_chunks(full):
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=chunk)


async def _cmd_viewsummary(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    user: User,
    loc: str,
) -> None:
    try:
        ctx = auth_context_for_user(db, user)
        ctx.require_org()
    except Exception:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.no_org"))
        return

    summaries = _list_recent_summaries(db, ctx)
    if not summaries:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.viewsummary_empty"))
        return

    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(loc, "telegram.viewsummary_intro"),
        reply_markup=_view_summary_inline_keyboard(summaries, db),
    )


async def _handle_view_summary_callback(
    db: Session,
    summary_id: str,
    *,
    token: str,
    settings,
    chat_id_s: str,
    tg_user_s: str,
    answer,
) -> None:
    from app.services.access import ensure_library_readable

    link = link_for_telegram_user(db, tg_user_s)
    if link is None:
        await answer(t("en", "telegram.need_link"))
        return
    user = db.get(User, link.user_id)
    if user is None or user.disabled_at is not None:
        await answer(t("en", "telegram.need_link"))
        return
    loc = _locale(user)

    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await answer(t(loc, "telegram.no_org"))
        return

    summary = db.get(Summary, summary_id)
    if summary is None or summary.org_id != org.id or not ensure_library_readable(ctx, db, summary, "summary"):
        await answer(t(loc, "telegram.viewsummary_not_found"))
        return

    try:
        await _send_summary_content(db, token, settings, chat_id_s, summary, loc)
        await answer()
    except TelegramApiError as exc:
        log.warning("telegram viewsummary send: %s", exc)
        await answer(t(loc, "telegram.viewsummary_send_failed"))
    except Exception:
        log.exception("telegram viewsummary failed")
        await answer(t(loc, "telegram.viewsummary_send_failed"))


async def _enqueue_transcribe(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    ctx,
    loc: str,
    audio: Audio,
    skill_ids: list[str],
) -> None:
    task = enqueue_transcribe_task(db, ctx, TranscribeBody(audio_id=audio.id, skill_ids=skill_ids))
    _attach_telegram_notify(task, chat_id)
    db.commit()
    schedule_locked_tick_asyncio(task.id, refresh_health=False)
    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(loc, "telegram.transcribe_queued", name=_audio_display_name(db, audio.id)),
    )


async def _handle_transcribe_audio_callback(
    db: Session,
    audio_id: str,
    *,
    token: str,
    settings,
    chat_id_s: str,
    tg_user_s: str,
    answer,
) -> None:
    from app.services.access import can_use_audio

    link = link_for_telegram_user(db, tg_user_s)
    if link is None:
        await answer(t("en", "telegram.need_link"))
        return
    user = db.get(User, link.user_id)
    if user is None or user.disabled_at is not None:
        await answer(t("en", "telegram.need_link"))
        return
    loc = _locale(user)

    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await answer(t(loc, "telegram.no_org"))
        return

    audio = db.get(Audio, audio_id)
    if audio is None or audio.org_id != org.id or not can_use_audio(ctx, db, audio):
        await answer(t(loc, "telegram.transcribe_not_found"))
        return

    try:
        await _enqueue_transcribe(db, token, settings, chat_id_s, ctx, loc, audio, [])
        await answer()
    except ApiError as exc:
        db.rollback()
        await answer(t(loc, "telegram.task_enqueue_failed", code=exc.code.value))
    except Exception:
        db.rollback()
        log.exception("telegram transcribe callback failed")
        await answer(t(loc, "telegram.transcribe_failed"))


async def _handle_summary_transcript_callback(
    db: Session,
    transcript_id: str,
    *,
    token: str,
    settings,
    chat_id_s: str,
    tg_user_s: str,
    answer,
) -> None:
    from app.services.access import can_use_transcript

    link = link_for_telegram_user(db, tg_user_s)
    if link is None:
        await answer(t("en", "telegram.need_link"))
        return
    user = db.get(User, link.user_id)
    if user is None or user.disabled_at is not None:
        await answer(t("en", "telegram.need_link"))
        return
    loc = _locale(user)

    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await answer(t(loc, "telegram.no_org"))
        return

    transcript = db.get(Transcript, transcript_id)
    if transcript is None or transcript.org_id != org.id or not can_use_transcript(ctx, db, transcript):
        await answer(t(loc, "telegram.transcript_not_found"))
        return

    await answer()
    await _offer_summary_skill_pick(db, token, settings, chat_id_s, ctx, loc, transcript)


async def _cmd_transcribe(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    user: User,
    loc: str,
    args: list[str],
) -> None:
    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.no_org"))
        return
    if args:
        maybe = _resolve_audio(db, ctx, org, args[0])
        if maybe is not None:
            skill_tokens = args[1:]
            try:
                skill_ids = _resolve_skill_ids(db, ctx, skill_tokens)
            except ValueError:
                await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.skill_ambiguous"))
                return
            try:
                await _enqueue_transcribe(db, token, settings, chat_id, ctx, loc, maybe, skill_ids)
            except ApiError as exc:
                db.rollback()
                await send_message(
                    token,
                    settings=settings,
                    db=db,
                    chat_id=chat_id,
                    text=t(loc, "telegram.task_enqueue_failed", code=exc.code.value),
                )
            except Exception:
                db.rollback()
                log.exception("telegram transcribe failed")
                await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.transcribe_failed"))
            return
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.audio_not_found"))
        return

    audios = _list_recent_audios(db, ctx)
    if not audios:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.transcribe_empty"))
        return
    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(loc, "telegram.transcribe_intro"),
        reply_markup=_audio_inline_keyboard(audios, db),
    )


async def _cmd_summary(
    db: Session,
    token: str,
    settings,
    chat_id: str,
    user: User,
    loc: str,
    args: list[str],
) -> None:
    try:
        ctx = auth_context_for_user(db, user)
        org, _ = ctx.require_org()
    except Exception:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.no_org"))
        return
    if args:
        maybe = _resolve_transcript(db, ctx, org, args[0])
        if maybe is not None:
            skill_tokens = args[1:]
            try:
                skill_ids = _resolve_skill_ids(db, ctx, skill_tokens)
            except ValueError:
                await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.skill_ambiguous"))
                return
            if not skill_ids:
                await _offer_summary_skill_pick(db, token, settings, chat_id, ctx, loc, maybe)
                return
            try:
                await _enqueue_summary(db, token, settings, chat_id, ctx, loc, maybe, skill_ids)
            except (ApiError, ValueError, PermissionError) as exc:
                db.rollback()
                code = getattr(getattr(exc, "code", None), "value", None) or "error"
                await send_message(
                    token,
                    settings=settings,
                    db=db,
                    chat_id=chat_id,
                    text=t(loc, "telegram.task_enqueue_failed", code=code),
                )
            except Exception:
                db.rollback()
                log.exception("telegram summary failed")
                await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.summary_failed"))
            return
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.transcript_not_found"))
        return

    transcripts = _list_recent_transcripts(db, ctx)
    if not transcripts:
        await send_message(token, settings=settings, db=db, chat_id=chat_id, text=t(loc, "telegram.summary_empty"))
        return
    await send_message(
        token,
        settings=settings,
        db=db,
        chat_id=chat_id,
        text=t(loc, "telegram.summary_intro"),
        reply_markup=_transcript_inline_keyboard(transcripts, db),
    )


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
        if row.type == "import":
            label = _import_source_label(meta)
        elif row.type == "transcribe" and row.audio_id:
            label = _audio_display_name(db, row.audio_id)
        elif row.type == "summarize" and row.transcript_id:
            label = _transcript_display_name(db, row.transcript_id)
        else:
            label = row.type
        lines.append(f"• {row.type}: {label} — {stage}")
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
            text=t(loc, "telegram.import_queued", name=_import_source_label(task.meta_json or {})),
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
            text=t(loc, "telegram.upload_ok", name=_audio_display_name(db, audio_id)),
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
        return t(loc, "telegram.task_error", name=_task_display_name(db, task), code=code)
    if task.type == "import":
        name = (meta.get("title") or meta.get("platform") or "").strip() or _import_source_label(meta)
        if name == "—":
            name = _audio_display_name(db, task.audio_id)
        return t(loc, "telegram.task_import_success", name=name)
    if task.type == "capture":
        room = (meta.get("meeting_room") or meta.get("meeting_host") or "").strip()
        audio_name = _audio_display_name(db, task.audio_id)
        return t(loc, "telegram.task_capture_success", room=room or "—", name=audio_name)
    if task.type == "transcribe":
        return t(
            loc,
            "telegram.task_transcribe_success",
            name=_transcript_display_name(db, task.produced_transcript_id),
        )
    if task.type == "summarize":
        return t(
            loc,
            "telegram.task_summarize_success",
            name=_summary_display_name(db, task.produced_summary_id),
            skill=_skill_labels(db, list(task.skill_ids_json or [])),
        )
    return t(loc, "telegram.task_success", name=_task_display_name(db, task))


def _task_display_name(db: Session, task: Task) -> str:
    meta = task.meta_json or {}
    if task.type == "import":
        return _import_source_label(meta)
    if task.type == "transcribe":
        return _audio_display_name(db, task.audio_id)
    if task.type == "summarize":
        return _transcript_display_name(db, task.transcript_id)
    if task.type == "capture":
        return (meta.get("meeting_room") or meta.get("meeting_host") or "capture").strip()
    return task.type


async def _deliver_terminal_notification(token: str, chat_id: str, text: str, task_id: str) -> None:
    from app.db import SessionLocal, get_engine

    get_engine()
    if SessionLocal is None:
        return
    with SessionLocal() as fresh_db:
        settings = get_instance_settings(fresh_db)
        try:
            await send_message(
                token,
                settings=settings,
                db=fresh_db,
                chat_id=str(chat_id),
                text=text,
            )
        except Exception:
            log.warning("telegram notify failed task=%s", task_id, exc_info=True)


def _schedule_terminal_notification(coro) -> None:
    def _log_delivery_error(fut: asyncio.Future) -> None:
        try:
            fut.result()
        except Exception:
            log.warning("telegram notify delivery failed", exc_info=True)

    hub = _hub_event_loop
    if hub is not None:
        future = asyncio.run_coroutine_threadsafe(coro, hub)
        if future is not None:
            future.add_done_callback(_log_delivery_error)
        return
    try:
        loop = asyncio.get_running_loop()

        def _on_task_done(done: asyncio.Task) -> None:
            if done.cancelled():
                return
            exc = done.exception()
            if exc is not None:
                log.warning("telegram notify delivery failed", exc_info=exc)

        loop.create_task(coro).add_done_callback(_on_task_done)
    except RuntimeError:
        log.warning("telegram notify skipped: hub event loop not available")


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
    _schedule_terminal_notification(
        _deliver_terminal_notification(token, str(chat_id), text, task.id),
    )

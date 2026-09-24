"""Library operations for MCP tools (same rules as HTTP API)."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALLOWED_AUDIO_SUFFIXES, MAX_UPLOAD_BYTES_CAP
from app.crypto import decrypt_str, encrypt_str
from app.deps import AuthContext, get_instance_settings
from app.models import Audio, Skill, Summary, Task, Transcript, new_id
from app.presenters import audio_public, skill_public, summary_public, task_public, transcript_public
from app.routers.library import (
    _audio_derived_info,
    _audio_filenames,
    _list_filter,
    _share_badge,
    _summary_source_context,
    _transcript_derived_info,
    _transcripts_by_id,
)
from app.routers.skills import _can_read_skill, _visible_skills
from app.routers.tasks import (
    ImportBody,
    TranscribeBody,
    _validate_summarize_skills,
    enqueue_import_task,
    enqueue_transcribe_task,
)
from app.services.task_access import can_manage_task, can_see_task, task_list_extra
from app.services.access import can_read_object, can_use_transcript, is_hidden
from app.services.artifacts import hard_delete_audio, hard_delete_summary, hard_delete_transcript
from app.services.audit import write_audit
from app.services.billing import assert_can_accept_task, snapshot_fields, upload_limit
from app.services.oauth_scopes import (
    SCOPE_AUDIO_READ,
    SCOPE_AUDIO_WRITE,
    SCOPE_SKILLS_READ,
    SCOPE_SKILLS_WRITE,
    SCOPE_SUMMARIES_READ,
    SCOPE_SUMMARIES_WRITE,
    SCOPE_TASKS_WRITE,
    SCOPE_TRANSCRIPTS_READ,
    SCOPE_TRANSCRIPTS_WRITE,
)
from app.services.storage import PayloadTooLarge, get_storage
from app.services.upload_validation import InvalidAudioContent
from app.services.summarize_models import (
    aggregate_instance_summarize_models,
    resolve_summarize_models,
    validate_dispatchable_summarize_model,
)
from app.services.transcript_payload import decode_transcript_payload, extract_utterances
from app.timeutil import utcnow

MCP_AUDIO_LIST_LIMIT = 100
MCP_TRANSCRIPT_LIST_LIMIT = 100
MCP_SUMMARY_LIST_LIMIT = 100
_SKILL_CATALOGS = frozenset({"self", "org", "base"})


def _require_oauth_scope(ctx: AuthContext, scope: str) -> None:
    if ctx.via_oauth_token and scope not in ctx.oauth_scopes:
        raise PermissionError(f"{scope} scope required")


def _decode_upload_base64(raw: str) -> bytes:
    payload = raw.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64 content") from exc


def list_audios_payload(
    db: Session,
    ctx: AuthContext,
    *,
    include_hidden: bool = False,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_AUDIO_READ)
    rows = _list_filter(ctx, db, Audio, "audio", include_hidden)
    rows = rows[:MCP_AUDIO_LIST_LIMIT]
    derived = _audio_derived_info(db, ctx, [row.id for row in rows])
    return {
        "items": [
            {
                **audio_public(row, _share_badge(db, "audio", row.id, row.owner_user_id, ctx)),
                **derived.get(
                    row.id,
                    {
                        "has_transcript": False,
                        "has_summary": False,
                        "transcript_id": None,
                        "summary_transcript_id": None,
                    },
                ),
            }
            for row in rows
        ],
        "truncated": len(rows) >= MCP_AUDIO_LIST_LIMIT,
    }


def get_audio_payload(db: Session, ctx: AuthContext, audio_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_AUDIO_READ)
    row = db.get(Audio, audio_id)
    if row is None or not can_read_object(ctx, db, "audio", row.owner_user_id, row.org_id, row.id):
        raise ValueError("not found")
    transcripts = db.scalars(
        select(Transcript).where(Transcript.source_audio_id == row.id).order_by(Transcript.created_at.desc())
    ).all()
    visible_transcripts = [
        item
        for item in transcripts
        if (
            can_read_object(ctx, db, "transcript", item.owner_user_id, item.org_id, item.id)
            or ctx.is_org_admin
        )
        and not is_hidden(db, ctx.user.id, "transcript", item.id)
    ]
    derived = _transcript_derived_info(db, ctx, [item.id for item in visible_transcripts])
    payload = audio_public(row, _share_badge(db, "audio", row.id, row.owner_user_id, ctx))
    payload["transcripts"] = [
        {
            **transcript_public(
                item,
                extra=_share_badge(db, "transcript", item.id, item.owner_user_id, ctx),
                source_filename=row.original_filename,
            ),
            **derived.get(item.id, {"has_summary": False}),
        }
        for item in visible_transcripts
    ]
    payload["can_transcribe"] = get_storage().exists(row.storage_path)
    return payload


def create_audio_upload_payload(
    db: Session,
    ctx: AuthContext,
    *,
    filename: str,
    content_base64: str,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_AUDIO_WRITE)
    org, _ = ctx.require_org()
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise ValueError("invalid file type")
    try:
        data = _decode_upload_base64(content_base64)
    except ValueError:
        raise
    if not data:
        raise ValueError("empty file")
    limit = min(upload_limit(org.tariff), MAX_UPLOAD_BYTES_CAP)
    audio_id = new_id()
    storage = get_storage()
    try:
        storage_path = storage.save_bytes(audio_id, suffix, data, max_bytes=limit)
    except PayloadTooLarge:
        raise ValueError("payload too large") from None
    except InvalidAudioContent:
        raise ValueError("invalid file") from None
    original_filename = filename.strip() or f"original{suffix}"
    row = Audio(
        id=audio_id,
        org_id=org.id,
        owner_user_id=ctx.user.id,
        storage_path=storage_path,
        original_filename=original_filename,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return audio_public(row)


def create_audio_import_payload(
    db: Session,
    ctx: AuthContext,
    *,
    url: str,
    transcribe: bool = False,
    skill_ids: list[str] | None = None,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_TASKS_WRITE)
    task = enqueue_import_task(
        db,
        ctx,
        ImportBody(url=url, transcribe=transcribe, skill_ids=list(skill_ids or [])),
    )
    return task_public(task)


def get_task_payload(
    db: Session,
    ctx: AuthContext,
    *,
    task_id: str,
) -> tuple[dict, bool, bool]:
    """Task JSON plus dispatcher tick hints (schedule tick, refresh_health)."""
    _require_oauth_scope(ctx, SCOPE_TASKS_WRITE)
    task = db.get(Task, task_id)
    if task is None or not can_see_task(ctx, task):
        raise ValueError("not found")
    from app.services.capture_runner import should_schedule_capture_task_tick

    schedule = task.status in {"queued", "running"} and should_schedule_capture_task_tick(task)
    refresh_health = schedule and task.type not in {"import", "capture"}
    payload = task_public(task, task_list_extra(db, [task]).get(task.id))
    return payload, schedule, refresh_health


async def stop_capture_task_payload(
    db: Session,
    ctx: AuthContext,
    *,
    task_id: str,
) -> tuple[dict, bool]:
    _require_oauth_scope(ctx, SCOPE_TASKS_WRITE)
    task = db.get(Task, task_id)
    if task is None or not can_see_task(ctx, task):
        raise ValueError("not found")
    if not can_manage_task(ctx, task):
        raise PermissionError("forbidden")
    if task.type != "capture":
        raise ValueError("capture task required")
    if task.status != "running":
        raise ValueError("task running")
    from app.services.capture_runner import request_hub_capture_stop

    need_tick = await request_hub_capture_stop(db, task)
    db.flush()
    return task_public(task), need_tick


def delete_audio_payload(db: Session, ctx: AuthContext, audio_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_AUDIO_WRITE)
    if not ctx.is_org_admin:
        raise PermissionError("forbidden")
    row = db.get(Audio, audio_id)
    if row is None:
        raise ValueError("not found")
    if ctx.org is None or row.org_id != ctx.org.id:
        raise ValueError("not found")
    write_audit(db, "audio.wipe", ctx, {"audio_id": row.id})
    hard_delete_audio(db, row)
    return {"status": "ok"}


def list_transcripts_payload(
    db: Session,
    ctx: AuthContext,
    *,
    include_hidden: bool = False,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_TRANSCRIPTS_READ)
    rows = _list_filter(ctx, db, Transcript, "transcript", include_hidden)
    rows = rows[:MCP_TRANSCRIPT_LIST_LIMIT]
    filenames = _audio_filenames(db, {row.source_audio_id for row in rows})
    derived = _transcript_derived_info(db, ctx, [row.id for row in rows])
    return {
        "items": [
            {
                **transcript_public(
                    row,
                    extra=_share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
                    source_filename=filenames.get(row.source_audio_id) if row.source_audio_id else None,
                ),
                **derived.get(row.id, {"has_summary": False}),
            }
            for row in rows
        ],
        "truncated": len(rows) >= MCP_TRANSCRIPT_LIST_LIMIT,
    }


def get_transcript_payload(db: Session, ctx: AuthContext, transcript_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_TRANSCRIPTS_READ)
    row = db.get(Transcript, transcript_id)
    if row is None or not can_read_object(ctx, db, "transcript", row.owner_user_id, row.org_id, row.id):
        raise ValueError("not found")
    stored = decode_transcript_payload(decrypt_str(row.utterances_encrypted, db))
    utterances = extract_utterances(stored)
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    summaries = db.scalars(
        select(Summary).where(Summary.source_transcript_id == row.id).order_by(Summary.created_at.desc())
    ).all()
    payload = transcript_public(
        row,
        utterances,
        _share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
        source_filename=source_audio.original_filename if source_audio else None,
    )
    payload["summaries"] = [
        summary_public(
            item,
            extra=_share_badge(db, "summary", item.id, item.owner_user_id, ctx),
            source_transcript=row,
            source_filename=source_audio.original_filename if source_audio else None,
        )
        for item in summaries
        if (
            can_read_object(ctx, db, "summary", item.owner_user_id, item.org_id, item.id)
            or ctx.is_org_admin
        )
        and not is_hidden(db, ctx.user.id, "summary", item.id)
    ]
    return payload


def update_transcript_payload(
    db: Session,
    ctx: AuthContext,
    transcript_id: str,
    *,
    title: str,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_TRANSCRIPTS_WRITE)
    row = db.get(Transcript, transcript_id)
    if row is None:
        raise ValueError("not found")
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        raise PermissionError("forbidden")
    if ctx.org is None or row.org_id != ctx.org.id:
        raise ValueError("not found")
    row.title = title.strip()
    write_audit(db, "transcript.rename", ctx, {"transcript_id": row.id})
    source_audio = db.get(Audio, row.source_audio_id) if row.source_audio_id else None
    db.flush()
    return transcript_public(
        row,
        extra=_share_badge(db, "transcript", row.id, row.owner_user_id, ctx),
        source_filename=source_audio.original_filename if source_audio else None,
    )


def delete_transcript_payload(db: Session, ctx: AuthContext, transcript_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_TRANSCRIPTS_WRITE)
    if not ctx.is_org_admin:
        raise PermissionError("forbidden")
    row = db.get(Transcript, transcript_id)
    if row is None:
        raise ValueError("not found")
    if ctx.org is None or row.org_id != ctx.org.id:
        raise ValueError("not found")
    write_audit(db, "transcript.wipe", ctx, {"transcript_id": row.id})
    hard_delete_transcript(db, row)
    return {"status": "ok"}


def list_summaries_payload(
    db: Session,
    ctx: AuthContext,
    *,
    include_hidden: bool = False,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_SUMMARIES_READ)
    rows = _list_filter(ctx, db, Summary, "summary", include_hidden)
    rows = rows[:MCP_SUMMARY_LIST_LIMIT]
    transcripts = _transcripts_by_id(db, {row.source_transcript_id for row in rows})
    audio_filenames = _audio_filenames(
        db, {tr.source_audio_id for tr in transcripts.values() if tr.source_audio_id}
    )
    items = []
    for row in rows:
        source_transcript, source_filename = _summary_source_context(row, transcripts, audio_filenames)
        items.append(
            summary_public(
                row,
                extra=_share_badge(db, "summary", row.id, row.owner_user_id, ctx),
                source_transcript=source_transcript,
                source_filename=source_filename,
            )
        )
    return {
        "items": items,
        "truncated": len(rows) >= MCP_SUMMARY_LIST_LIMIT,
    }


def get_summary_payload(db: Session, ctx: AuthContext, summary_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_SUMMARIES_READ)
    row = db.get(Summary, summary_id)
    if row is None or not can_read_object(ctx, db, "summary", row.owner_user_id, row.org_id, row.id):
        raise ValueError("not found")
    body = decrypt_str(row.body_encrypted, db)
    source_transcript = db.get(Transcript, row.source_transcript_id) if row.source_transcript_id else None
    source_audio = (
        db.get(Audio, source_transcript.source_audio_id)
        if source_transcript and source_transcript.source_audio_id
        else None
    )
    return summary_public(
        row,
        body,
        _share_badge(db, "summary", row.id, row.owner_user_id, ctx),
        source_transcript=source_transcript,
        source_filename=source_audio.original_filename if source_audio else None,
    )


def create_transcribe_payload(
    db: Session,
    ctx: AuthContext,
    *,
    audio_id: str,
    skill_ids: list[str] | None = None,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_TASKS_WRITE)
    task = enqueue_transcribe_task(
        db,
        ctx,
        TranscribeBody(audio_id=audio_id, skill_ids=list(skill_ids or [])),
    )
    return task_public(task)


def create_summary_payload(
    db: Session,
    ctx: AuthContext,
    *,
    transcript_id: str,
    skill_ids: list[str],
) -> dict:
    _require_oauth_scope(ctx, SCOPE_TASKS_WRITE)
    if ctx.org is None:
        raise PermissionError("organization required")
    org = ctx.org
    transcript = db.get(Transcript, transcript_id)
    if transcript is None or transcript.org_id != org.id or not can_use_transcript(ctx, db, transcript):
        raise ValueError("not found")
    if not skill_ids:
        raise ValueError("skill_ids required")
    _validate_summarize_skills(ctx, db, org, skill_ids)
    settings = get_instance_settings(db)
    available = aggregate_instance_summarize_models(db)
    models = resolve_summarize_models(ctx.user, settings, available=available["summarize_models"])
    summarize_model = models["summarize_model"]
    if summarize_model:
        try:
            validate_dispatchable_summarize_model(db, model=summarize_model)
        except ValueError as exc:
            raise ValueError("summarize model unavailable") from exc
    tariff = assert_can_accept_task(ctx, org, ctx.locale)
    now = utcnow()
    task = Task(
        id=new_id(),
        type="summarize",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        transcript_id=transcript.id,
        skill_ids_json=list(skill_ids),
        queued_at=now,
        created_at=now,
        updated_at=now,
        **snapshot_fields(tariff, None, None, summarize_model=summarize_model),
    )
    db.add(task)
    db.flush()
    return task_public(task)


def update_summary_payload(
    db: Session,
    ctx: AuthContext,
    summary_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_SUMMARIES_WRITE)
    row = db.get(Summary, summary_id)
    if row is None:
        raise ValueError("not found")
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        raise PermissionError("forbidden")
    if ctx.org is None or row.org_id != ctx.org.id:
        raise ValueError("not found")
    if title is None and body is None:
        raise ValueError("title or body required")
    body_text = decrypt_str(row.body_encrypted, db)
    changed = False
    if title is not None:
        row.title = title.strip()
        changed = True
    if body is not None and body != body_text:
        row.body_encrypted = encrypt_str(body, db)
        row.edited = True
        body_text = body
        changed = True
    if changed:
        write_audit(db, "summary.update", ctx, {"summary_id": row.id})
    source_transcript = db.get(Transcript, row.source_transcript_id) if row.source_transcript_id else None
    source_audio = (
        db.get(Audio, source_transcript.source_audio_id)
        if source_transcript and source_transcript.source_audio_id
        else None
    )
    db.flush()
    return summary_public(
        row,
        body_text,
        _share_badge(db, "summary", row.id, row.owner_user_id, ctx),
        source_transcript=source_transcript,
        source_filename=source_audio.original_filename if source_audio else None,
    )


def delete_summary_payload(db: Session, ctx: AuthContext, summary_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_SUMMARIES_WRITE)
    row = db.get(Summary, summary_id)
    if row is None:
        raise ValueError("not found")
    if row.owner_user_id != ctx.user.id and not ctx.is_org_admin:
        raise PermissionError("forbidden")
    if ctx.org is None or row.org_id != ctx.org.id:
        raise ValueError("not found")
    write_audit(db, "summary.delete", ctx, {"summary_id": row.id})
    hard_delete_summary(db, row)
    return {"status": "ok"}


def list_skills_payload(db: Session, ctx: AuthContext, *, scope: str | None = None) -> dict:
    _require_oauth_scope(ctx, SCOPE_SKILLS_READ)
    items = _visible_skills(db, ctx, scope)
    return {"items": [skill_public(skill, extra) for skill, extra in items]}


def get_skill_payload(db: Session, ctx: AuthContext, skill_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_SKILLS_READ)
    skill = db.get(Skill, skill_id)
    if skill is None or not _can_read_skill(db, ctx, skill):
        raise ValueError("not found")
    extra: dict = {}
    if skill.scope == "base":
        extra["catalog"] = "base"
        extra["readonly"] = not ctx.is_instance_admin
    elif skill.scope == "org":
        extra["catalog"] = "org"
        extra["readonly"] = not ctx.is_org_admin
    elif skill.scope == "self":
        extra["catalog"] = "self"
        extra["readonly"] = skill.owner_user_id != ctx.user.id
    else:
        raise ValueError("not found")
    return skill_public(skill, extra)


def create_skill_payload(
    db: Session,
    ctx: AuthContext,
    *,
    name: str,
    body: str,
    catalog: str = "self",
) -> dict:
    _require_oauth_scope(ctx, SCOPE_SKILLS_WRITE)
    if catalog not in _SKILL_CATALOGS:
        raise ValueError("invalid catalog")
    now = utcnow()
    if catalog == "self":
        if ctx.org is None:
            raise PermissionError("organization required")
        org = ctx.org
        skill = Skill(
            id=new_id(),
            scope="self",
            org_id=org.id,
            owner_user_id=ctx.user.id,
            name=name.strip(),
            body=body,
            created_at=now,
            updated_at=now,
        )
    elif catalog == "org":
        if ctx.org is None or not ctx.is_org_admin:
            raise PermissionError("forbidden")
        skill = Skill(
            id=new_id(),
            scope="org",
            org_id=ctx.org.id,
            name=name.strip(),
            body=body,
            created_at=now,
            updated_at=now,
        )
    else:
        if not ctx.is_instance_admin:
            raise PermissionError("forbidden")
        skill = Skill(
            id=new_id(),
            scope="base",
            name=name.strip(),
            body=body,
            created_at=now,
            updated_at=now,
        )
    db.add(skill)
    db.flush()
    return skill_public(skill, {"catalog": catalog, "readonly": False})


def update_skill_payload(
    db: Session,
    ctx: AuthContext,
    skill_id: str,
    *,
    name: str,
    body: str,
) -> dict:
    _require_oauth_scope(ctx, SCOPE_SKILLS_WRITE)
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise ValueError("not found")
    if skill.scope == "self":
        if skill.owner_user_id != ctx.user.id:
            raise ValueError("not found")
    elif skill.scope == "org":
        if ctx.org is None or skill.org_id != ctx.org.id or not ctx.is_org_admin:
            raise PermissionError("forbidden")
    elif skill.scope == "base":
        if not ctx.is_instance_admin:
            raise PermissionError("forbidden")
    else:
        raise ValueError("not found")
    skill.name = name.strip()
    skill.body = body
    skill.updated_at = utcnow()
    db.flush()
    return skill_public(skill)


def delete_skill_payload(db: Session, ctx: AuthContext, skill_id: str) -> dict:
    _require_oauth_scope(ctx, SCOPE_SKILLS_WRITE)
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise ValueError("not found")
    if skill.scope == "self":
        if skill.owner_user_id != ctx.user.id:
            raise ValueError("not found")
    elif skill.scope == "org":
        if ctx.org is None or skill.org_id != ctx.org.id or not ctx.is_org_admin:
            raise PermissionError("forbidden")
    elif skill.scope == "base":
        if not ctx.is_instance_admin:
            raise PermissionError("forbidden")
    else:
        raise ValueError("not found")
    db.delete(skill)
    return {"status": "ok"}

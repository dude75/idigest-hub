"""Library operations for MCP tools (same rules as HTTP API)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import decrypt_str
from app.deps import AuthContext, get_instance_settings
from app.models import Audio, Skill, Summary, Task, Transcript, new_id
from app.presenters import skill_public, summary_public, task_public, transcript_public
from app.routers.library import (
    _audio_filenames,
    _list_filter,
    _share_badge,
    _summary_source_context,
    _transcript_derived_info,
    _transcripts_by_id,
)
from app.routers.skills import _visible_skills
from app.routers.tasks import _validate_summarize_skills
from app.services.access import can_read_object, can_use_transcript, is_hidden
from app.services.artifacts import hard_delete_summary
from app.services.audit import write_audit
from app.services.billing import assert_can_accept_task, snapshot_fields
from app.services.oauth_scopes import (
    SCOPE_SKILLS_READ,
    SCOPE_SKILLS_WRITE,
    SCOPE_SUMMARIES_READ,
    SCOPE_SUMMARIES_WRITE,
    SCOPE_TASKS_WRITE,
    SCOPE_TRANSCRIPTS_READ,
)
from app.services.summarize_models import (
    aggregate_instance_summarize_models,
    resolve_summarize_models,
    validate_dispatchable_summarize_model,
)
from app.services.transcript_payload import decode_transcript_payload, extract_utterances
from app.timeutil import utcnow

MCP_TRANSCRIPT_LIST_LIMIT = 100
MCP_SUMMARY_LIST_LIMIT = 100


def _require_oauth_scope(ctx: AuthContext, scope: str) -> None:
    if ctx.via_oauth_token and scope not in ctx.oauth_scopes:
        raise PermissionError(f"{scope} scope required")


def list_transcriptions_payload(
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


def summarize_transcript_payload(
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

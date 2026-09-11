"""Задачи хаба: transcribe / summarize / poll / cancel (ТЗ §6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, get_instance_settings, require_auth
from app.errors import ErrorCode
from app.models import Audio, Organization, Skill, Task, Transcript, User, new_id
from app.presenters import task_public
from app.services.access import can_use_audio, can_use_transcript
from app.services.billing import assert_can_accept_task, snapshot_fields
from app.rate_limit import enforce_write_limits, get_rate_limits
from app.services.dispatcher import locked_tick
from app.timeutil import utcnow

router = APIRouter()

NON_RETRIABLE_ERROR_CODES = frozenset(
    {
        "canceled",
        "source_deleted",
        "text_too_long",
        "payload_too_large",
        "invalid_file",
        "invalid_url",
    }
)


class TranscribeBody(BaseModel):
    audio_id: str


class SummarizeBody(BaseModel):
    transcript_id: str
    skill_ids: list[str]


class ImportBody(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


def _can_manage_task(ctx: AuthContext, task: Task) -> bool:
    if ctx.org is None or task.org_id != ctx.org.id:
        return False
    if ctx.is_org_admin:
        return True
    return task.user_id == ctx.user.id


def _can_see_task(ctx: AuthContext, task: Task) -> bool:
    if ctx.is_instance_admin:
        return True
    if ctx.org is None or task.org_id != ctx.org.id:
        return False
    if ctx.is_org_admin:
        return True
    return task.user_id == ctx.user.id


def _visible_tasks_filters(ctx: AuthContext) -> list:
    if ctx.is_instance_admin:
        return []
    if ctx.org is None:
        return [Task.user_id == ctx.user.id]
    if ctx.is_org_admin:
        return [Task.org_id == ctx.org.id]
    return [Task.org_id == ctx.org.id, Task.user_id == ctx.user.id]


def _task_list_extra(db: Session, rows: list[Task]) -> dict[str, dict]:
    user_ids = {row.user_id for row in rows}
    org_ids = {row.org_id for row in rows}
    audio_ids = {row.audio_id for row in rows if row.audio_id}
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    orgs = (
        {o.id: o for o in db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()}
        if org_ids
        else {}
    )
    audios = (
        {a.id: a for a in db.scalars(select(Audio).where(Audio.id.in_(audio_ids))).all()}
        if audio_ids
        else {}
    )
    extra: dict[str, dict] = {}
    for row in rows:
        user = users.get(row.user_id)
        org = orgs.get(row.org_id)
        audio = audios.get(row.audio_id) if row.audio_id else None
        extra[row.id] = {
            "owner_email": user.email if user else None,
            "org_name": org.name if org else None,
            "audio_filename": audio.original_filename if audio else None,
        }
    return extra


@router.post("/tasks/transcribe", status_code=202)
async def create_transcribe(
    body: TranscribeBody,
    request: Request,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    audio = db.get(Audio, body.audio_id)
    if audio is None or audio.org_id != org.id or not can_use_audio(ctx, db, audio):
        ctx.raise_error(ErrorCode.not_found)
    from app.services.storage import get_storage

    if not get_storage().exists(audio.storage_path):
        ctx.raise_error(ErrorCode.not_found)
    tariff = assert_can_accept_task(ctx, org, ctx.locale)
    settings = get_instance_settings(db)
    now = utcnow()
    task = Task(
        id=new_id(),
        type="transcribe",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        audio_id=audio.id,
        queued_at=now,
        created_at=now,
        updated_at=now,
        **snapshot_fields(tariff, settings.asr_model, settings.diarization_model),
    )
    db.add(task)
    db.flush()
    await locked_tick(db, task.id)
    db.refresh(task)
    return task_public(task)


@router.post("/tasks/import", status_code=202)
async def create_import(
    body: ImportBody,
    request: Request,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    settings = get_instance_settings(db)
    if not settings.import_enabled:
        ctx.raise_error(ErrorCode.import_disabled)
    from app.services.url_import import UrlImportError, validate_import_url

    try:
        url = validate_import_url(body.url)
    except UrlImportError as exc:
        ctx.raise_error(ErrorCode(exc.code))
    tariff = org.tariff
    now = utcnow()
    task = Task(
        id=new_id(),
        type="import",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        queued_at=now,
        created_at=now,
        updated_at=now,
        meta_json={"url": url, "stage": "queued"},
        **snapshot_fields(tariff, settings.asr_model, settings.diarization_model),
    )
    db.add(task)
    db.flush()
    await locked_tick(db, task.id)
    db.refresh(task)
    return task_public(task)


@router.post("/tasks/summarize", status_code=202)
async def create_summarize(
    body: SummarizeBody,
    request: Request,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    transcript = db.get(Transcript, body.transcript_id)
    if transcript is None or transcript.org_id != org.id or not can_use_transcript(ctx, db, transcript):
        ctx.raise_error(ErrorCode.not_found)
    _validate_summarize_skills(ctx, db, org, body.skill_ids)
    tariff = assert_can_accept_task(ctx, org, ctx.locale)
    now = utcnow()
    task = Task(
        id=new_id(),
        type="summarize",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        transcript_id=transcript.id,
        skill_ids_json=list(body.skill_ids),
        queued_at=now,
        created_at=now,
        updated_at=now,
        **snapshot_fields(tariff, None, None),
    )
    db.add(task)
    db.flush()
    await locked_tick(db, task.id)
    db.refresh(task)
    return task_public(task)


@router.get("/tasks")
def list_tasks(
    org_id: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    query = select(Task).order_by(Task.updated_at.desc())
    filters = _visible_tasks_filters(ctx)
    org_filter = (org_id or "").strip()
    user_filter = (user_id or "").strip()
    if ctx.is_instance_admin:
        if org_filter:
            filters.append(Task.org_id == org_filter)
        if user_filter:
            filters.append(Task.user_id == user_filter)
    elif ctx.is_org_admin and user_filter:
        filters.append(Task.user_id == user_filter)
    if filters:
        query = query.where(*filters)
    rows = list(db.scalars(query).all())
    extras = _task_list_extra(db, rows)
    return {"items": [task_public(row, extras.get(row.id)) for row in rows]}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    task = db.get(Task, task_id)
    if task is None or not _can_see_task(ctx, task):
        ctx.raise_error(ErrorCode.not_found)
    if task.status in {"queued", "running"}:
        await locked_tick(db, task.id)
        db.refresh(task)
    return task_public(task)


def _validate_summarize_skills(ctx: AuthContext, db: Session, org: Organization, skill_ids: list[str]) -> None:
    if not skill_ids:
        ctx.raise_error(ErrorCode.validation_error)
    for sid in skill_ids:
        skill = db.get(Skill, sid)
        if skill is None:
            ctx.raise_error(ErrorCode.not_found)
        if skill.scope == "base":
            continue
        if skill.scope == "org" and skill.org_id == org.id:
            continue
        if skill.scope == "self" and (
            skill.owner_user_id == ctx.user.id
            or __import__("app.services.access", fromlist=["is_shared_with"]).is_shared_with(
                db, "skill", skill.id, ctx.user.id
            )
        ):
            continue
        ctx.raise_error(ErrorCode.forbidden)


def _validate_task_source(ctx: AuthContext, db: Session, org: Organization, task: Task) -> None:
    if task.type == "transcribe":
        if not task.audio_id:
            ctx.raise_error(ErrorCode.not_found)
        audio = db.get(Audio, task.audio_id)
        if audio is None or audio.org_id != org.id or not can_use_audio(ctx, db, audio):
            ctx.raise_error(ErrorCode.not_found)
        from app.services.storage import get_storage

        if not get_storage().exists(audio.storage_path):
            ctx.raise_error(ErrorCode.not_found)
        return
    if task.type == "summarize":
        if not task.transcript_id:
            ctx.raise_error(ErrorCode.not_found)
        transcript = db.get(Transcript, task.transcript_id)
        if transcript is None or transcript.org_id != org.id or not can_use_transcript(ctx, db, transcript):
            ctx.raise_error(ErrorCode.not_found)
        _validate_summarize_skills(ctx, db, org, list(task.skill_ids_json or []))
        return
    if task.type == "import":
        settings = get_instance_settings(db)
        if not settings.import_enabled:
            ctx.raise_error(ErrorCode.import_disabled)
        from app.services.url_import import UrlImportError, validate_import_url

        url = (task.meta_json or {}).get("url")
        if not isinstance(url, str) or not url.strip():
            ctx.raise_error(ErrorCode.not_found)
        try:
            validate_import_url(url)
        except UrlImportError as exc:
            ctx.raise_error(ErrorCode(exc.code))


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_task(
    task_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    task = db.get(Task, task_id)
    if task is None or not _can_see_task(ctx, task):
        ctx.raise_error(ErrorCode.not_found)
    if not _can_manage_task(ctx, task):
        ctx.raise_error(ErrorCode.forbidden)
    if task.status != "error":
        ctx.raise_error(ErrorCode.task_running)
    if task.error_code in NON_RETRIABLE_ERROR_CODES:
        ctx.raise_error(ErrorCode.validation_error)
    org, _ = ctx.require_org()
    assert_can_accept_task(ctx, org, ctx.locale)
    _validate_task_source(ctx, db, org, task)
    now = utcnow()
    meta = dict(task.meta_json or {})
    meta["stage"] = "queued"
    meta.pop("error_detail", None)
    task.status = "queued"
    task.error_code = None
    task.worker_id = None
    task.worker_task_id = None
    task.produced_transcript_id = None
    task.produced_summary_id = None
    task.retry_without_timeout = False
    task.skip_persist = False
    task.skip_reason = None
    task.queued_at = now
    task.updated_at = now
    task.meta_json = meta
    await locked_tick(db, task.id)
    db.refresh(task)
    return task_public(task)


@router.delete("/tasks/{task_id}")
def cancel_task(
    task_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        ctx.raise_error(ErrorCode.not_found)
    if not _can_manage_task(ctx, task):
        ctx.raise_error(ErrorCode.not_found if ctx.org is None or task.org_id != ctx.org.id else ErrorCode.forbidden)
    if task.type == "import":
        if task.status not in {"queued", "running"}:
            ctx.raise_error(ErrorCode.task_running)
        from app.services.import_runner import request_import_cancel

        request_import_cancel(task.id)
        task.status = "error"
        task.error_code = "canceled"
        task.updated_at = utcnow()
        return task_public(task)
    if task.status != "queued" or task.worker_task_id:
        ctx.raise_error(ErrorCode.task_running)
    task.status = "error"
    task.error_code = "canceled"
    task.updated_at = utcnow()
    return task_public(task)

"""Задачи хаба: transcribe / summarize / poll / cancel (ТЗ §6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, get_instance_settings, require_auth
from app.errors import ErrorCode
from app.models import Audio, Organization, Skill, Task, Transcript, new_id
from app.presenters import task_public
from app.services.access import can_use_audio, can_use_transcript
from app.services.billing import assert_can_accept_task, snapshot_fields
from app.rate_limit import enforce_write_limits, get_rate_limits
from app.services.dispatcher import schedule_locked_tick
from app.services.task_access import (
    can_manage_task as _can_manage_task,
    can_see_task as _can_see_task,
    task_list_extra as _task_list_extra,
    visible_tasks_filters as _visible_tasks_filters,
)
from app.timeutil import utcnow

router = APIRouter()

ACTIVE_TASK_STATUSES = ("queued", "running")

NON_RETRIABLE_ERROR_CODES = frozenset(
    {
        "canceled",
        "source_deleted",
        "text_too_long",
        "payload_too_large",
        "invalid_file",
        "invalid_url",
        "proxy_unavailable",
        "capture_disabled",
        "meeting_host_not_configured",
    }
)


class TranscribeBody(BaseModel):
    audio_id: str
    skill_ids: list[str] = Field(default_factory=list)


class SummarizeBody(BaseModel):
    transcript_id: str
    skill_ids: list[str]


class ImportBody(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    transcribe: bool = False
    skill_ids: list[str] = Field(default_factory=list)


class CaptureBody(BaseModel):
    meeting_url: str = Field(min_length=8, max_length=2048)
    pin: str = ""
    transcribe: bool = False
    skill_ids: list[str] = Field(default_factory=list)


def enqueue_capture_task(db: Session, ctx: AuthContext, body: CaptureBody) -> Task:
    org, _ = ctx.require_org()
    settings = get_instance_settings(db)
    if not settings.capture_enabled:
        ctx.raise_error(ErrorCode.capture_disabled)
    from app.services.capture_meeting import CaptureMeetingError, org_capture_bot_display_name, resolve_capture_target
    from app.services.capture_platforms import allowed_connectors
    from app.services.transcribe_models import resolve_transcribe_models

    if body.transcribe:
        assert_can_accept_task(ctx, org, ctx.locale)
        if body.skill_ids:
            _validate_summarize_skills(ctx, db, org, body.skill_ids)
    display_name = org_capture_bot_display_name(org)
    try:
        target = resolve_capture_target(
            db,
            org=org,
            meeting_url=body.meeting_url.strip(),
            pin=body.pin or "",
            settings_allowed=allowed_connectors(settings),
            display_name=display_name,
        )
    except CaptureMeetingError as exc:
        code = exc.code
        if code == "capture_disabled":
            ctx.raise_error(ErrorCode.capture_disabled)
        if code == "invalid_url":
            ctx.raise_error(ErrorCode.invalid_url)
        if code == "meeting_host_not_configured":
            ctx.raise_error(ErrorCode.meeting_host_not_configured)
        ctx.raise_error(ErrorCode.pipeline_error)
    models = resolve_transcribe_models(ctx.user, settings)
    tariff = org.tariff
    now = utcnow()
    meta: dict = {
        "meeting_url": target.meeting_url,
        "meeting_host": target.meeting_host,
        "meeting_room": target.meeting_room,
        "pin": target.pin,
        "connector": target.connector,
        "display_name": display_name,
        "stage": "queued",
    }
    if target.jwt:
        meta["jwt"] = target.jwt
    if body.transcribe:
        meta["pipeline_transcribe"] = True
    task = Task(
        id=new_id(),
        type="capture",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        worker_id=target.worker.id,
        skill_ids_json=list(body.skill_ids) or None if body.transcribe and body.skill_ids else None,
        queued_at=now,
        created_at=now,
        updated_at=now,
        meta_json=meta,
        **snapshot_fields(tariff, models["asr_model"], models["diarization_model"]),
    )
    db.add(task)
    db.flush()
    return task


def enqueue_import_task(db: Session, ctx: AuthContext, body: ImportBody) -> Task:
    org, _ = ctx.require_org()
    settings = get_instance_settings(db)
    from app.services.capture_meeting import import_url_looks_like_meeting, import_url_routes_to_capture
    from app.services.url_import import (
        UrlImportError,
        assert_import_fetch_allowed,
        reject_blocked_import_url,
        reject_literal_blocked_import_url,
    )

    try:
        reject_literal_blocked_import_url(body.url)
    except UrlImportError as exc:
        ctx.raise_error(ErrorCode(exc.code))
    if not settings.import_enabled:
        ctx.raise_error(ErrorCode.import_disabled)
    from app.services.download_proxy_health import download_proxy_ready
    from app.services.import_platforms import allowed_extractors

    if not download_proxy_ready(settings, db):
        ctx.raise_error(ErrorCode.proxy_unavailable)
    if import_url_routes_to_capture(body.url, settings):
        return enqueue_capture_task(
            db,
            ctx,
            CaptureBody(
                meeting_url=body.url.strip(),
                pin="",
                transcribe=body.transcribe,
                skill_ids=body.skill_ids,
            ),
        )
    if import_url_looks_like_meeting(body.url):
        ctx.raise_error(ErrorCode.capture_disabled)
    try:
        reject_blocked_import_url(body.url)
    except UrlImportError as exc:
        ctx.raise_error(ErrorCode(exc.code))
    try:
        url = assert_import_fetch_allowed(body.url, settings_allowed=allowed_extractors(settings))
    except UrlImportError as exc:
        ctx.raise_error(ErrorCode(exc.code))
    if body.transcribe:
        assert_can_accept_task(ctx, org, ctx.locale)
        if body.skill_ids:
            _validate_summarize_skills(ctx, db, org, body.skill_ids)
    from app.services.transcribe_models import resolve_transcribe_models

    models = resolve_transcribe_models(ctx.user, settings)
    tariff = org.tariff
    now = utcnow()
    meta: dict = {"url": url, "stage": "queued"}
    if body.transcribe:
        meta["pipeline_transcribe"] = True
    task = Task(
        id=new_id(),
        type="import",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        skill_ids_json=list(body.skill_ids) or None if body.transcribe and body.skill_ids else None,
        queued_at=now,
        created_at=now,
        updated_at=now,
        meta_json=meta,
        **snapshot_fields(tariff, models["asr_model"], models["diarization_model"]),
    )
    db.add(task)
    db.flush()
    return task


@router.post("/tasks/transcribe", status_code=202)
async def create_transcribe(
    body: TranscribeBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
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
    from app.services.transcribe_models import resolve_transcribe_models

    models = resolve_transcribe_models(ctx.user, settings)
    skill_ids = list(body.skill_ids or [])
    if skill_ids:
        _validate_summarize_skills(ctx, db, org, skill_ids)
    now = utcnow()
    task = Task(
        id=new_id(),
        type="transcribe",
        status="queued",
        org_id=org.id,
        user_id=ctx.user.id,
        audio_id=audio.id,
        skill_ids_json=skill_ids or None,
        queued_at=now,
        created_at=now,
        updated_at=now,
        **snapshot_fields(tariff, models["asr_model"], models["diarization_model"]),
    )
    db.add(task)
    db.flush()
    db.commit()
    schedule_locked_tick(background_tasks, task.id)
    return task_public(task)


@router.post("/tasks/import", status_code=202)
async def create_import(
    body: ImportBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    task = enqueue_import_task(db, ctx, body)
    db.commit()
    schedule_locked_tick(background_tasks, task.id, refresh_health=False)
    return task_public(task)


@router.post("/tasks/capture", status_code=202)
async def create_capture(
    body: CaptureBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    task = enqueue_capture_task(db, ctx, body)
    db.commit()
    schedule_locked_tick(background_tasks, task.id, refresh_health=False)
    return task_public(task)


@router.post("/tasks/summarize", status_code=202)
async def create_summarize(
    body: SummarizeBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org()
    enforce_write_limits(request, ctx.user.id, get_rate_limits(db), ctx.locale)
    transcript = db.get(Transcript, body.transcript_id)
    if transcript is None or transcript.org_id != org.id or not can_use_transcript(ctx, db, transcript):
        ctx.raise_error(ErrorCode.not_found)
    _validate_summarize_skills(ctx, db, org, body.skill_ids)
    from app.deps import get_instance_settings
    from app.services.summarize_models import (
        aggregate_instance_summarize_models,
        resolve_summarize_models,
        validate_dispatchable_summarize_model,
    )

    tariff = assert_can_accept_task(ctx, org, ctx.locale)
    settings = get_instance_settings(db)
    available = aggregate_instance_summarize_models(db)
    models = resolve_summarize_models(ctx.user, settings, available=available["summarize_models"])
    summarize_model = models["summarize_model"]
    if summarize_model:
        try:
            validate_dispatchable_summarize_model(db, model=summarize_model)
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
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
        **snapshot_fields(tariff, None, None, summarize_model=summarize_model),
    )
    db.add(task)
    db.flush()
    db.commit()
    schedule_locked_tick(background_tasks, task.id)
    return task_public(task)


def _list_tasks_filters(ctx: AuthContext, org_id: str | None, user_id: str | None) -> list:
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
    return filters


@router.get("/tasks")
def list_tasks(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
    org_id: str | None = None,
    user_id: str | None = None,
    done_limit: int = Query(10, ge=1, le=100),
    done_offset: int = Query(0, ge=0),
) -> dict:
    filters = _list_tasks_filters(ctx, org_id, user_id)
    base = select(Task)
    if filters:
        base = base.where(*filters)

    active_rows = list(
        db.scalars(
            base.where(Task.status.in_(ACTIVE_TASK_STATUSES)).order_by(Task.updated_at.desc())
        ).all()
    )

    done_count = select(func.count()).select_from(Task).where(~Task.status.in_(ACTIVE_TASK_STATUSES))
    if filters:
        done_count = done_count.where(*filters)
    done_total = int(db.scalar(done_count) or 0)

    done_rows = list(
        db.scalars(
            base.where(~Task.status.in_(ACTIVE_TASK_STATUSES))
            .order_by(Task.updated_at.desc())
            .offset(done_offset)
            .limit(done_limit)
        ).all()
    )

    extras = _task_list_extra(db, active_rows + done_rows)
    if active_rows:
        schedule_locked_tick(background_tasks, None, refresh_health=False, wait=False)
    return {
        "active": [task_public(row, extras.get(row.id)) for row in active_rows],
        "done": [task_public(row, extras.get(row.id)) for row in done_rows],
        "done_total": done_total,
    }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    task = db.get(Task, task_id)
    if task is None or not _can_see_task(ctx, task):
        ctx.raise_error(ErrorCode.not_found)
    if task.status in {"queued", "running"}:
        refresh_health = task.type not in {"import", "capture"}
        schedule_locked_tick(background_tasks, task.id, refresh_health=refresh_health, wait=False)
    return task_public(task, _task_list_extra(db, [task]).get(task.id))


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
        from app.services.download_proxy_health import download_proxy_ready
        from app.services.import_platforms import allowed_extractors
        from app.services.url_import import UrlImportError, assert_import_fetch_allowed

        if not download_proxy_ready(settings, db):
            ctx.raise_error(ErrorCode.proxy_unavailable)
        url = (task.meta_json or {}).get("url")
        if not isinstance(url, str) or not url.strip():
            ctx.raise_error(ErrorCode.not_found)
        try:
            assert_import_fetch_allowed(url, settings_allowed=allowed_extractors(settings))
        except UrlImportError as exc:
            ctx.raise_error(ErrorCode(exc.code))
        return
    if task.type == "capture":
        settings = get_instance_settings(db)
        if not settings.capture_enabled:
            ctx.raise_error(ErrorCode.capture_disabled)
        meta = task.meta_json or {}
        if not isinstance(meta.get("meeting_url"), str):
            ctx.raise_error(ErrorCode.not_found)
        return


@router.post("/tasks/{task_id}/stop", status_code=202)
async def stop_capture_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    task = db.get(Task, task_id)
    if task is None or not _can_see_task(ctx, task):
        ctx.raise_error(ErrorCode.not_found)
    if not _can_manage_task(ctx, task):
        ctx.raise_error(ErrorCode.forbidden)
    if task.type != "capture":
        ctx.raise_error(ErrorCode.validation_error)
    if task.status != "running":
        ctx.raise_error(ErrorCode.task_running)
    from app.services.capture_runner import request_hub_capture_stop

    need_tick = await request_hub_capture_stop(db, task)
    db.commit()
    if need_tick:
        schedule_locked_tick(background_tasks, task.id, refresh_health=False, wait=False)
    return task_public(task)


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
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
    db.flush()
    db.commit()
    schedule_locked_tick(background_tasks, task.id)
    return task_public(task)


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
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
        db.flush()
        db.commit()
        return task_public(task)
    if task.type == "capture":
        if task.status not in {"queued", "running"}:
            ctx.raise_error(ErrorCode.task_running)
        from app.services.capture_runner import forward_capture_cancel, request_capture_cancel

        request_capture_cancel(task.id)
        await forward_capture_cancel(db, task)
        task.status = "error"
        task.error_code = "canceled"
        task.updated_at = utcnow()
        db.flush()
        db.commit()
        schedule_locked_tick(background_tasks, task.id, refresh_health=False, wait=False)
        return task_public(task)
    if task.status != "queued" or task.worker_task_id:
        ctx.raise_error(ErrorCode.task_running)
    task.status = "error"
    task.error_code = "canceled"
    task.updated_at = utcnow()
    return task_public(task)

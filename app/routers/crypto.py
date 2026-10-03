"""Instance admin: envelope encryption (DEK management)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import count_dek_usage, count_deks_needing_rewrap, create_dek, dek_public
from app.db import get_session
from app.deps import AuthContext, get_instance_settings, require_auth
from app.errors import ErrorCode
from app.models import DataEncryptionKey, EncryptionJob, InstanceSettings
from app.schemas.common import OkStatusResponse
from app.schemas.crypto_api import (
    DekListResponse,
    DekPublicResponse,
    EncryptionJobLatestResponse,
    EncryptionJobPublicResponse,
)
from app.services.audit import write_audit
from app.services.crypto_reencrypt import active_job_id, latest_job, request_cancel, start_reencrypt_job
from app.timeutil import isoformat_utc, utcnow

router = APIRouter()


def _admin(ctx: AuthContext) -> None:
    ctx.require_instance_admin()


def _job_public(job) -> dict:
    return {
        "id": job.id,
        "target_dek_id": job.target_dek_id,
        "status": job.status,
        "progress": job.progress_json or {},
        "error": job.error,
        "started_at": isoformat_utc(job.started_at),
        "completed_at": isoformat_utc(job.completed_at),
        "created_at": isoformat_utc(job.created_at),
    }


@router.get("/instance/crypto/deks", response_model=DekListResponse)
def list_deks(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> DekListResponse:
    _admin(ctx)
    settings = get_instance_settings(db)
    rows = list(db.scalars(select(DataEncryptionKey).order_by(DataEncryptionKey.created_at.desc())).all())
    has_retiring = any(row.status == "retiring" for row in rows)
    return DekListResponse(
        active_dek_id=settings.active_dek_id,
        items=[DekPublicResponse.model_validate(dek_public(row, usage_count=count_dek_usage(db, row.id))) for row in rows],
        running_job_id=active_job_id(),
        deks_pending_rewrap=count_deks_needing_rewrap(db),
        hub_secret_prev_configured=bool(get_settings().HUB_SECRET_PREV),
        reencrypt_available=has_retiring and active_job_id() is None,
    )


@router.post("/instance/crypto/deks", response_model=DekPublicResponse)
def add_dek(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> DekPublicResponse:
    _admin(ctx)
    if active_job_id() is not None:
        ctx.raise_error(ErrorCode.conflict)
    settings = get_instance_settings(db)
    now = utcnow()
    for row in db.scalars(select(DataEncryptionKey).where(DataEncryptionKey.status == "active")).all():
        row.status = "retiring"
        row.retired_at = now
    dek = create_dek(db, status="active")
    settings.active_dek_id = dek.id
    write_audit(db, "crypto.dek.create", ctx, {"dek_id": dek.id})
    return DekPublicResponse.model_validate(dek_public(dek, usage_count=count_dek_usage(db, dek.id)))


@router.post("/instance/crypto/reencrypt", response_model=EncryptionJobPublicResponse)
def start_reencrypt(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> EncryptionJobPublicResponse:
    _admin(ctx)
    if active_job_id() is not None:
        ctx.raise_error(ErrorCode.conflict)
    job = start_reencrypt_job(db)
    if job is None:
        ctx.raise_error(ErrorCode.validation_error)
    write_audit(db, "crypto.reencrypt.start", ctx, {"job_id": job.id, "target_dek_id": job.target_dek_id})
    return EncryptionJobPublicResponse.model_validate(_job_public(job))


@router.get("/instance/crypto/reencrypt/latest", response_model=EncryptionJobLatestResponse)
def reencrypt_latest(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> EncryptionJobLatestResponse:
    _admin(ctx)
    job = latest_job(db)
    if job is None:
        return EncryptionJobLatestResponse(job=None)
    return EncryptionJobLatestResponse(job=EncryptionJobPublicResponse.model_validate(_job_public(job)))


@router.get("/instance/crypto/reencrypt/{job_id}", response_model=EncryptionJobPublicResponse)
def reencrypt_status(
    job_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> EncryptionJobPublicResponse:
    _admin(ctx)
    job = db.get(EncryptionJob, job_id)
    if job is None:
        ctx.raise_error(ErrorCode.not_found)
    return EncryptionJobPublicResponse.model_validate(_job_public(job))


@router.post("/instance/crypto/reencrypt/{job_id}/cancel", response_model=OkStatusResponse)
def cancel_reencrypt(
    job_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    _admin(ctx)
    job = db.get(EncryptionJob, job_id)
    if job is None:
        ctx.raise_error(ErrorCode.not_found)
    if job.status not in ("queued", "running"):
        ctx.raise_error(ErrorCode.validation_error)
    request_cancel(job_id)
    write_audit(db, "crypto.reencrypt.cancel", ctx, {"job_id": job_id})
    return OkStatusResponse()

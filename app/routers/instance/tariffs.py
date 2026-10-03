from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crypto import encrypt_str
from app.db import get_session
from app.deps import (
    AuthContext,
    get_instance_settings,
    invalidate_session_ttl_cache,
    load_org_bundle,
    normalize_session_ttl_hours,
    require_auth,
)
from app.errors import ApiError, ErrorCode
from app.models import HiddenItem, Membership, Organization, Task, Tariff, User, WorkerNode, new_id
from app.money import parse_money
from app.presenters import org_public, tariff_public, user_public, worker_public
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.routers.auth import revoke_user_auth, seed_default_tariff
from app.routers.instance._body import (
    AgreementPreviewBody,
    BaseSkillBody,
    CreateOrgBody,
    ImpersonateBody,
    OrgDeleteBody,
    OrgTariffBody,
    OrgUserRoleBody,
    SettingsPatch,
    SmtpTestBody,
    SmtpTestSendBody,
    TariffBody,
    TariffCloneBody,
    TariffDeleteBody,
    WalletBody,
    WorkerBody,
    WorkerDeleteBody,
    WorkerProbeBody,
    WorkerRemediation,
)
from app.routers.instance._router import router
from app.security import hash_password, random_password
from app.services.access import guard_last_org_admin, is_hidden
from app.services.audit import export_audit_csv, list_audit, write_audit
from app.services.billing import signup_balance
from app.services.export import attachment_response, safe_filename
from app.services.instance_helpers import (
    apply_capture_worker_models,
    apply_transcribe_worker_models,
    org_count_for_tariff,
    raise_worker_connect_error,
    require_instance_admin,
    resolve_worker_token,
    workers_list_payload,
)
from app.services.instance_orgs import list_orgs_payload
from app.services.mfa import disable_totp, hub_local_auth_applies, totp_configured
from app.services.stats import org_ledger, parse_org_stats_range, usage_stats
from app.timeutil import utcnow

from app.constants import MAX_UPLOAD_BYTES_CAP

def apply_tariff(tariff: Tariff, body: TariffBody, ctx: AuthContext) -> None:
    if body.max_upload_bytes > MAX_UPLOAD_BYTES_CAP or body.max_upload_bytes <= 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.name = body.name.strip()
    tariff.unlimited = body.unlimited
    tariff.available_on_signup = body.available_on_signup and tariff.archived_at is None
    tariff.price_per_audio_sec = Decimal(body.price_per_audio_sec)
    tariff.price_per_summarize_job = parse_money(body.price_per_summarize_job)
    tariff.price_per_1k_summary_chars = Decimal(body.price_per_1k_summary_chars)
    if body.audio_retention_days < 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.audio_retention_days = body.audio_retention_days
    tariff.api_enabled = body.api_enabled
    tariff.signup_credit = parse_money(body.signup_credit)
    tariff.max_upload_bytes = body.max_upload_bytes
    tariff.tone_analytics_enabled = body.tone_analytics_enabled
    tariff.updated_at = utcnow()


@router.get("/tariffs")
def list_tariffs(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    require_instance_admin(ctx)
    seed_default_tariff(db)
    rows = db.scalars(select(Tariff).order_by(Tariff.created_at)).all()
    return {"items": [tariff_public(row, org_count_for_tariff(db, row.id)) for row in rows]}


@router.post("/tariffs")
def create_tariff(
    body: TariffBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    now = utcnow()
    tariff = Tariff(
        id=new_id(),
        name=body.name.strip(),
        unlimited=False,
        available_on_signup=False,
        max_upload_bytes=MAX_UPLOAD_BYTES_CAP,
        created_at=now,
        updated_at=now,
    )
    apply_tariff(tariff, body, ctx)
    db.add(tariff)
    db.flush()
    write_audit(db, "tariff.create", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, 0)


@router.post("/tariffs/{tariff_id}/clone")
def clone_tariff(
    tariff_id: str,
    body: TariffCloneBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    source = db.get(Tariff, tariff_id)
    if source is None:
        ctx.raise_error(ErrorCode.not_found)
    name = body.name.strip()
    if not name:
        ctx.raise_error(ErrorCode.validation_error)
    now = utcnow()
    tariff = Tariff(
        id=new_id(),
        name=name,
        unlimited=source.unlimited,
        available_on_signup=source.available_on_signup,
        archived_at=None,
        price_per_audio_sec=source.price_per_audio_sec,
        price_per_summarize_job=source.price_per_summarize_job,
        price_per_1k_summary_chars=source.price_per_1k_summary_chars,
        audio_retention_days=source.audio_retention_days,
        api_enabled=source.api_enabled,
        signup_credit=source.signup_credit,
        max_upload_bytes=source.max_upload_bytes,
        tone_analytics_enabled=source.tone_analytics_enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(tariff)
    db.flush()
    write_audit(db, "tariff.clone", ctx, {"tariff_id": tariff.id, "source_tariff_id": source.id})
    return tariff_public(tariff, 0)


@router.patch("/tariffs/{tariff_id}")
def patch_tariff(
    tariff_id: str,
    body: TariffBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    apply_tariff(tariff, body, ctx)
    write_audit(db, "tariff.update", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, org_count_for_tariff(db, tariff.id))


@router.post("/tariffs/{tariff_id}/archive")
def archive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = utcnow()
    tariff.available_on_signup = False
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.archive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, org_count_for_tariff(db, tariff.id))


@router.post("/tariffs/{tariff_id}/unarchive")
def unarchive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = None
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.unarchive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, org_count_for_tariff(db, tariff.id))


@router.get("/tariffs/{tariff_id}/delete-impact")
def tariff_delete_impact(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.services.tariff_impact import compute_tariff_delete_impact

    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    return compute_tariff_delete_impact(db, tariff)


@router.delete("/tariffs/{tariff_id}")
def delete_tariff(
    tariff_id: str,
    body: TariffDeleteBody | None = Body(default=None),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.tariff_impact import apply_tariff_remediation

    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    total = int(db.scalar(select(func.count()).select_from(Tariff)) or 0)
    if total <= 1:
        ctx.raise_error(ErrorCode.last_tariff)
    org_count = org_count_for_tariff(db, tariff.id)
    remediation = body.remediation if body else None
    remediation_result = None
    if org_count > 0:
        if remediation is None:
            ctx.raise_error(ErrorCode.tariff_in_use)
        try:
            remediation_result = apply_tariff_remediation(
                db,
                from_tariff_id=tariff.id,
                replacement_tariff_id=remediation.tariff_id,
            )
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
        if remediation_result["orgs_updated"] != org_count:
            ctx.raise_error(ErrorCode.validation_error)
    db.delete(tariff)
    write_audit(db, "tariff.delete", ctx, {"tariff_id": tariff.id})
    payload: dict = {"status": "ok"}
    if remediation_result is not None:
        payload["remediation"] = remediation_result
    return payload

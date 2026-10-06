from __future__ import annotations

from decimal import Decimal

from fastapi import Body, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ErrorCode
from app.models import Tariff, new_id
from app.money import parse_money
from app.presenters import tariff_public
from app.routers.instance._body import TariffBody, TariffCloneBody, TariffDeleteBody
from app.routers.instance._router import router
from app.schemas.org_api import TariffListResponse, TariffPublic
from app.schemas.tariff_api import TariffDeleteImpactResponse, TariffDeleteResponse
from app.services.audit import write_audit
from app.services.auth_helpers import seed_default_tariff
from app.services.instance_helpers import org_count_for_tariff, require_instance_admin
from app.timeutil import utcnow

def apply_tariff(tariff: Tariff, body: TariffBody, ctx: AuthContext) -> None:
    if body.max_upload_bytes > MAX_UPLOAD_BYTES_CAP or body.max_upload_bytes <= 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.name = body.name.strip()
    tariff.unlimited = body.unlimited
    tariff.available_on_signup = body.available_on_signup and tariff.archived_at is None
    tariff.price_per_audio_sec = Decimal(body.price_per_audio_sec)
    tariff.price_per_1k_summary_chars = Decimal(body.price_per_1k_summary_chars)
    if body.audio_retention_days < 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.audio_retention_days = body.audio_retention_days
    tariff.api_enabled = body.api_enabled
    tariff.signup_credit = parse_money(body.signup_credit)
    tariff.max_upload_bytes = body.max_upload_bytes
    tariff.tone_analytics_enabled = body.tone_analytics_enabled
    tariff.updated_at = utcnow()


@router.get("/tariffs", response_model=TariffListResponse)
def list_tariffs(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> TariffListResponse:
    require_instance_admin(ctx)
    seed_default_tariff(db)
    rows = db.scalars(select(Tariff).order_by(Tariff.created_at)).all()
    return TariffListResponse(
        items=[TariffPublic.model_validate(tariff_public(row, org_count_for_tariff(db, row.id))) for row in rows]
    )


@router.post("/tariffs", response_model=TariffPublic)
def create_tariff(
    body: TariffBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> TariffPublic:
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
    return TariffPublic.model_validate(tariff_public(tariff, 0))


@router.post("/tariffs/{tariff_id}/clone", response_model=TariffPublic)
def clone_tariff(
    tariff_id: str,
    body: TariffCloneBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> TariffPublic:
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
    return TariffPublic.model_validate(tariff_public(tariff, 0))


@router.patch("/tariffs/{tariff_id}", response_model=TariffPublic)
def patch_tariff(
    tariff_id: str,
    body: TariffBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> TariffPublic:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    apply_tariff(tariff, body, ctx)
    write_audit(db, "tariff.update", ctx, {"tariff_id": tariff.id})
    return TariffPublic.model_validate(tariff_public(tariff, org_count_for_tariff(db, tariff.id)))


@router.post("/tariffs/{tariff_id}/archive", response_model=TariffPublic)
def archive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> TariffPublic:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = utcnow()
    tariff.available_on_signup = False
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.archive", ctx, {"tariff_id": tariff.id})
    return TariffPublic.model_validate(tariff_public(tariff, org_count_for_tariff(db, tariff.id)))


@router.post("/tariffs/{tariff_id}/unarchive", response_model=TariffPublic)
def unarchive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> TariffPublic:
    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = None
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.unarchive", ctx, {"tariff_id": tariff.id})
    return TariffPublic.model_validate(tariff_public(tariff, org_count_for_tariff(db, tariff.id)))


@router.get("/tariffs/{tariff_id}/delete-impact", response_model=TariffDeleteImpactResponse)
def tariff_delete_impact(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> TariffDeleteImpactResponse:
    from app.services.tariff_impact import compute_tariff_delete_impact

    require_instance_admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    return TariffDeleteImpactResponse.model_validate(compute_tariff_delete_impact(db, tariff))


@router.delete("/tariffs/{tariff_id}", response_model=TariffDeleteResponse)
def delete_tariff(
    tariff_id: str,
    body: TariffDeleteBody | None = Body(default=None),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> TariffDeleteResponse:
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
    return TariffDeleteResponse.model_validate(payload)

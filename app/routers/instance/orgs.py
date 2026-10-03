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
from app.services.auth_helpers import revoke_user_auth, seed_default_tariff
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
from app.schemas.common import OkStatusResponse
from app.schemas.instance_orgs import (
    InstanceOrgCreateResponse,
    InstanceOrgListResponse,
    OrgLedgerResponse,
)
from app.schemas.me import UserPublic
from app.schemas.org_api import OrgPublicResponse
from app.schemas.org_users import OrgUserResetPasswordResponse
from app.timeutil import utcnow

@router.post("/orgs/{org_id}/wallet", response_model=OrgPublicResponse)
def wallet_delta(
    org_id: str,
    body: WalletBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    try:
        delta = parse_money(body.delta)
    except InvalidOperation:
        ctx.raise_error(ErrorCode.validation_error)
    org.balance = parse_money(Decimal(org.balance) + delta)
    org.updated_at = utcnow()
    write_audit(db, "wallet.delta", ctx, {"org_id": org.id, "delta": str(delta)})
    return OrgPublicResponse.model_validate(org_public(org))
@router.get("/orgs", response_model=InstanceOrgListResponse)
def list_orgs(
    include_hidden: bool = False,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    return InstanceOrgListResponse.model_validate(list_orgs_payload(ctx, db, include_hidden=include_hidden))


@router.post("/orgs", response_model=InstanceOrgCreateResponse)
def create_org(
    body: CreateOrgBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    name = body.name.strip()
    if not name:
        ctx.raise_error(ErrorCode.validation_error)
    tariff = db.get(Tariff, body.tariff_id)
    if tariff is None or tariff.archived_at is not None:
        ctx.raise_error(ErrorCode.not_found)
    email = str(body.admin_email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        ctx.raise_error(ErrorCode.email_taken)
    now = utcnow()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(body.admin_password),
        auth_provider="local",
        locale=body.locale,
        password_changed_at=now,
        must_change_password=True,
        is_instance_admin=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    org = Organization(
        id=new_id(),
        name=name,
        is_personal=body.is_personal,
        tariff_id=tariff.id,
        password_ttl_days=0,
        balance=signup_balance(tariff),
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    db.flush()
    db.add(Membership(id=new_id(), user_id=user.id, org_id=org.id, role="org_admin"))
    write_audit(db, "org.create", ctx, {"org_id": org.id, "admin_user_id": user.id, "tariff_id": tariff.id})
    org.tariff = tariff
    payload = org_public(org)
    payload["members"] = [user_public(user, "org_admin")]
    return InstanceOrgCreateResponse.model_validate(payload)


@router.post("/orgs/{org_id}/delete", response_model=OkStatusResponse)
def delete_org(
    org_id: str,
    body: OrgDeleteBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    if body.confirm_name.strip() != org.name:
        ctx.raise_error(ErrorCode.validation_error)
    from app.services.org_delete import delete_organization

    write_audit(
        db,
        "org.delete",
        ctx,
        {"org_id": org.id, "name": org.name, "is_personal": org.is_personal},
    )
    delete_organization(db, org)
    return OkStatusResponse()


@router.post("/orgs/{org_id}/hide", response_model=OkStatusResponse)
def hide_org(
    org_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "org", org.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="org", object_id=org.id))
    return OkStatusResponse()


@router.post("/orgs/{org_id}/unhide", response_model=OkStatusResponse)
def unhide_org(
    org_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    hidden = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == "org",
            HiddenItem.object_id == org.id,
        )
    )
    if hidden:
        db.delete(hidden)
    return OkStatusResponse()


@router.get("/orgs/{org_id}/ledger", response_model=OrgLedgerResponse)
def org_ledger_ep(
    org_id: str,
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    return OrgLedgerResponse.model_validate(
        org_ledger(
            db,
            org_id,
            start=start,
            end=end,
            user_id=(user_id or "").strip() or None,
            kind=(kind or "").strip() or None,
        )
    )


@router.post("/orgs/{org_id}/users/{user_id}/reset-password", response_model=OrgUserResetPasswordResponse)
def reset_org_admin_password(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None or membership.role != "org_admin":
        ctx.raise_error(ErrorCode.forbidden)
    password = random_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    user.updated_at = utcnow()
    revoke_user_auth(db, user.id)
    write_audit(db, "user.password_reset", ctx, {"user_id": user.id, "org_id": org.id})
    return OrgUserResetPasswordResponse(password=password)


@router.post("/orgs/{org_id}/users/{user_id}/reset-mfa", response_model=UserPublic)
def reset_org_user_mfa(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None:
        ctx.raise_error(ErrorCode.forbidden)
    if not hub_local_auth_applies(user=user, org=org, membership=membership):
        ctx.raise_error(ErrorCode.forbidden)
    if not totp_configured(user):
        ctx.raise_error(ErrorCode.validation_error)
    disable_totp(db, user)
    revoke_user_auth(db, user.id)
    write_audit(db, "user.mfa.reset", ctx, {"user_id": user.id, "org_id": org.id})
    return user_public(user, membership.role)


@router.patch("/orgs/{org_id}/users/{user_id}", response_model=UserPublic)
def patch_org_user_role(
    org_id: str,
    user_id: str,
    body: OrgUserRoleBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None:
        ctx.raise_error(ErrorCode.forbidden)
    if body.role not in {"org_admin", "org_member"}:
        ctx.raise_error(ErrorCode.validation_error)
    if membership.role == "org_admin" and body.role == "org_member":
        guard_last_org_admin(db, org.id, user_id, ctx.locale)
    membership.role = body.role
    write_audit(
        db,
        "user.role",
        ctx,
        {"user_id": user.id, "org_id": org.id, "role": body.role, "by": "instance_admin"},
    )
    settings = get_instance_settings(db)
    return UserPublic.model_validate(user_public(user, membership.role, instance_settings=settings))


@router.patch("/orgs/{org_id}/tariff", response_model=OrgPublicResponse)
def assign_org_tariff(
    org_id: str,
    body: OrgTariffBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    org = db.get(Organization, org_id)
    tariff = db.get(Tariff, body.tariff_id)
    if org is None or tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    org.tariff_id = tariff.id
    org.updated_at = utcnow()
    write_audit(db, "org.tariff", ctx, {"org_id": org.id, "tariff_id": tariff.id})
    db.refresh(org)
    org.tariff = tariff
    return OrgPublicResponse.model_validate(org_public(org))

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
from app.schemas.common import OkStatusResponse
from app.timeutil import utcnow



def actor_is_org_admin(db: Session, ctx: AuthContext) -> tuple[Organization, Membership] | None:
    org, membership = load_org_bundle(db, ctx.actor)
    if org is None or membership is None or membership.role != "org_admin":
        return None
    return org, membership


@router.post("/impersonate", response_model=OkStatusResponse)
def impersonate(
    body: ImpersonateBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    if ctx.session is None or ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    org_scope: str | None = None
    if ctx.is_instance_admin:
        pass
    elif ctx.is_org_admin and ctx.org is not None:
        org_scope = ctx.org.id
    else:
        ctx.raise_error(ErrorCode.forbidden)
    target = db.get(User, body.user_id)
    if target is None or target.is_instance_admin or target.disabled_at is not None:
        ctx.raise_error(ErrorCode.not_found)
    if org_scope is not None:
        if target.id == ctx.actor.id:
            ctx.raise_error(ErrorCode.forbidden)
        membership = db.scalar(
            select(Membership).where(Membership.user_id == target.id, Membership.org_id == org_scope)
        )
        if membership is None:
            ctx.raise_error(ErrorCode.not_found)
    ctx.session.impersonate_user_id = target.id
    write_audit(db, "impersonate.start", ctx, {"user_id": target.id}, on_behalf_of=target.id)
    return OkStatusResponse()


@router.delete("/impersonate", response_model=OkStatusResponse)
def stop_impersonate(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> OkStatusResponse:
    if ctx.session is None:
        ctx.raise_error(ErrorCode.forbidden)
    if not ctx.actor.is_instance_admin and actor_is_org_admin(db, ctx) is None:
        ctx.raise_error(ErrorCode.forbidden)
    write_audit(db, "impersonate.stop", ctx)
    ctx.session.impersonate_user_id = None
    return OkStatusResponse()

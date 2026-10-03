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
from app.schemas.stats import InstanceUsageStatsResponse
from app.timeutil import utcnow

@router.get("/instance/audit")
def audit_log(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    require_instance_admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    user_filter = (user_id or "").strip() or None
    if user_filter and db.get(User, user_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    items, total = list_audit(
        db,
        start=start,
        end=end,
        org_id=org_filter,
        user_id=user_filter,
        action=(action or "").strip() or None,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/instance/audit/export")
def audit_log_export(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    require_instance_admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    user_filter = (user_id or "").strip() or None
    if user_filter and db.get(User, user_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    content = export_audit_csv(
        db,
        start=start,
        end=end,
        org_id=org_filter,
        user_id=user_filter,
        action=(action or "").strip() or None,
    )
    from_part = safe_filename(from_day or "start", fallback="start")
    to_part = safe_filename(to_day or "end", fallback="end")
    filename = f"audit-{from_part}_{to_part}.csv"
    return attachment_response(content, filename, "text/csv; charset=utf-8")


@router.get("/instance/stats", response_model=InstanceUsageStatsResponse)
def stats(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> InstanceUsageStatsResponse:
    require_instance_admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    usage = usage_stats(
        db,
        org_id=org_filter,
        start=start,
        end=end,
        user_id=(user_id or "").strip() or None,
        kind=(kind or "").strip() or None,
    )
    queued = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "queued")) or 0)
    running = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0)
    orgs = int(db.scalar(select(func.count()).select_from(Organization)) or 0)
    users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    from app.deps import get_instance_settings
    from app.services.download_proxy_health import download_proxy_card_status

    settings = get_instance_settings(db)
    return InstanceUsageStatsResponse.model_validate(
        {
            "orgs": orgs,
            "users": users,
            "tasks_queued": queued,
            "tasks_running": running,
            "download_proxy_status": download_proxy_card_status(settings, db),
            **usage,
            "usage_total": usage["total_amount"],
        }
    )

"""Instance admin: воркеры, тарифы, настройки, орги, impersonate, статистика."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.crypto import encrypt_str
from app.db import get_session
from app.deps import AuthContext, get_instance_settings, load_org_bundle, require_auth
from app.errors import ErrorCode
from app.models import HiddenItem, Membership, Organization, Task, Tariff, UsageEvent, User, WorkerNode, new_id
from app.services.access import is_hidden
from app.money import parse_money
from app.presenters import org_public, tariff_public, user_public, worker_public
from app.routers.auth import revoke_user_auth, seed_default_tariff
from app.security import hash_password, random_password
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.services.audit import write_audit
from app.services.stats import org_ledger, parse_org_stats_range, usage_stats
from app.timeutil import utcnow

router = APIRouter()


class WorkerBody(BaseModel):
    type: str
    name: str = ""
    base_url: str
    api_token: str | None = None
    weight: int = 1
    enabled: bool = True


class TariffBody(BaseModel):
    name: str
    unlimited: bool = False
    available_on_signup: bool = False
    price_per_audio_sec: str = "0"
    price_per_summarize_job: str = "0"
    price_per_1k_summary_chars: str = "0"
    audio_retention_days: int = 0
    api_enabled: bool = True
    signup_credit: str = "0"
    max_upload_bytes: int = MAX_UPLOAD_BYTES_CAP


class WalletBody(BaseModel):
    delta: str


class SettingsPatch(BaseModel):
    allow_new_orgs: bool | None = None
    public_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool | None = None
    asr_model: str | None = None
    diarization_model: str | None = Field(default=None)
    rate_limit_enabled: bool | None = None
    rate_limit_login_email: int | None = None
    rate_limit_login_ip: int | None = None
    rate_limit_login_global: int | None = None
    rate_limit_signup_email: int | None = None
    rate_limit_signup_ip: int | None = None
    rate_limit_signup_global: int | None = None
    rate_limit_reset_email: int | None = None
    rate_limit_reset_ip: int | None = None
    rate_limit_reset_global: int | None = None
    rate_limit_reset_confirm_ip: int | None = None
    rate_limit_reset_confirm_global: int | None = None
    rate_limit_setup_ip: int | None = None
    rate_limit_setup_global: int | None = None
    rate_limit_api_user: int | None = None
    rate_limit_api_ip: int | None = None
    rate_limit_api_global: int | None = None
    rate_limit_api_tasks_user: int | None = None
    rate_limit_api_tasks_ip: int | None = None
    import_enabled: bool | None = None
    import_allowed_extractors: list[str] | None = None
    download_proxy_url: str | None = None
    download_proxy_password: str | None = None
    download_proxy_enabled: bool | None = None
    download_cookies_path: str | None = None
    import_audio_bitrate_kbps: int | None = None


class OrgTariffBody(BaseModel):
    tariff_id: str


class ImpersonateBody(BaseModel):
    user_id: str


class BaseSkillBody(BaseModel):
    name: str
    body: str


def _admin(ctx: AuthContext) -> None:
    ctx.require_instance_admin()


def _org_count(db: Session, tariff_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff_id)) or 0)


@router.get("/workers")
def list_workers(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    rows = db.scalars(select(WorkerNode).order_by(WorkerNode.created_at)).all()
    return {"items": [worker_public(row) for row in rows]}


@router.post("/workers")
def create_worker(
    body: WorkerBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    if body.type not in {"transcribe", "summarize"}:
        ctx.raise_error(ErrorCode.validation_error)
    if not body.api_token:
        ctx.raise_error(ErrorCode.validation_error)
    now = utcnow()
    node = WorkerNode(
        id=new_id(),
        type=body.type,
        name=body.name.strip(),
        base_url=body.base_url.rstrip("/"),
        api_token_encrypted=encrypt_str(body.api_token),
        weight=max(body.weight, 1),
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    db.flush()
    return worker_public(node)


@router.patch("/workers/{worker_id}")
def patch_worker(
    worker_id: str,
    body: WorkerBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    if body.type not in {"transcribe", "summarize"}:
        ctx.raise_error(ErrorCode.validation_error)
    node.type = body.type
    node.name = body.name.strip()
    node.base_url = body.base_url.rstrip("/")
    if body.api_token:
        node.api_token_encrypted = encrypt_str(body.api_token)
    node.weight = max(body.weight, 1)
    node.enabled = body.enabled
    node.updated_at = utcnow()
    return worker_public(node)


@router.delete("/workers/{worker_id}")
def delete_worker(
    worker_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    db.delete(node)
    return {"status": "ok"}


@router.get("/tariffs")
def list_tariffs(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    seed_default_tariff(db)
    rows = db.scalars(select(Tariff).order_by(Tariff.created_at)).all()
    return {"items": [tariff_public(row, _org_count(db, row.id)) for row in rows]}


def _apply_tariff(tariff: Tariff, body: TariffBody, ctx: AuthContext) -> None:
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
    tariff.updated_at = utcnow()


@router.post("/tariffs")
def create_tariff(
    body: TariffBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
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
    _apply_tariff(tariff, body, ctx)
    db.add(tariff)
    db.flush()
    write_audit(db, "tariff.create", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, 0)


@router.patch("/tariffs/{tariff_id}")
def patch_tariff(
    tariff_id: str,
    body: TariffBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    _apply_tariff(tariff, body, ctx)
    write_audit(db, "tariff.update", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.post("/tariffs/{tariff_id}/archive")
def archive_tariff(
    tariff_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = utcnow()
    tariff.available_on_signup = False
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.archive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.post("/tariffs/{tariff_id}/unarchive")
def unarchive_tariff(
    tariff_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = None
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.unarchive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.delete("/tariffs/{tariff_id}")
def delete_tariff(
    tariff_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    total = int(db.scalar(select(func.count()).select_from(Tariff)) or 0)
    if total <= 1:
        ctx.raise_error(ErrorCode.last_tariff)
    if _org_count(db, tariff.id) > 0:
        ctx.raise_error(ErrorCode.tariff_in_use)
    db.delete(tariff)
    return {"status": "ok"}


@router.post("/orgs/{org_id}/wallet")
def wallet_delta(
    org_id: str,
    body: WalletBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    delta = parse_money(body.delta)
    org.balance = parse_money(Decimal(org.balance) + delta)
    org.updated_at = utcnow()
    write_audit(db, "wallet.delta", ctx, {"org_id": org.id, "delta": str(delta)})
    return org_public(org)


@router.get("/instance/settings")
def get_settings_ep(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    s = get_instance_settings(db)
    from app.services.import_platforms import DEFAULT_IMPORT_AUDIO_BITRATE_KBPS, admin_platforms

    proxy_url = s.download_proxy_url or ""
    bitrate = s.import_audio_bitrate_kbps
    if bitrate is None:
        bitrate = DEFAULT_IMPORT_AUDIO_BITRATE_KBPS
    return {
        "allow_new_orgs": s.allow_new_orgs,
        "public_base_url": s.public_base_url,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_user": s.smtp_user,
        "smtp_configured": bool(s.smtp_host and s.smtp_from),
        "smtp_from": s.smtp_from,
        "smtp_tls": s.smtp_tls,
        "asr_model": s.asr_model,
        "diarization_model": s.diarization_model,
        "import_enabled": s.import_enabled,
        "import_platforms": admin_platforms(s),
        "download_proxy_url": s.download_proxy_url,
        "download_proxy_configured": bool(proxy_url.strip()),
        "download_proxy_enabled": s.download_proxy_enabled,
        "download_cookies_path": s.download_cookies_path,
        "import_audio_bitrate_kbps": bitrate,
        **rate_limits_public(s),
    }


@router.patch("/instance/settings")
def patch_settings(
    body: SettingsPatch, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    s = get_instance_settings(db)
    data = body.model_dump(exclude_unset=True)
    if "diarization_model" in data:
        value = data["diarization_model"]
        s.diarization_model = value.strip() if isinstance(value, str) and value.strip() else None
        data.pop("diarization_model")
    if "smtp_password" in data:
        password = data.pop("smtp_password")
        if password:
            s.smtp_password_encrypted = encrypt_str(password)
    if "download_proxy_url" in data:
        from app.services.import_platforms import normalize_download_proxy_url

        raw_proxy = data.get("download_proxy_url")
        if raw_proxy is None or not str(raw_proxy).strip():
            s.download_proxy_url = None
            s.download_proxy_enabled = False
        else:
            try:
                s.download_proxy_url = normalize_download_proxy_url(str(raw_proxy))
            except ValueError:
                ctx.raise_error(ErrorCode.validation_error)
        data.pop("download_proxy_url", None)
    if "download_proxy_enabled" in data:
        enabled = bool(data.pop("download_proxy_enabled"))
        if enabled and not (s.download_proxy_url or "").strip():
            ctx.raise_error(ErrorCode.validation_error)
        s.download_proxy_enabled = enabled
    if "download_proxy_password" in data:
        proxy_password = data.pop("download_proxy_password")
        if proxy_password:
            s.download_proxy_password_encrypted = encrypt_str(proxy_password)
    if "import_audio_bitrate_kbps" in data:
        from app.services.import_platforms import normalize_import_audio_bitrate_kbps

        s.import_audio_bitrate_kbps = normalize_import_audio_bitrate_kbps(data.pop("import_audio_bitrate_kbps"))
    if "import_allowed_extractors" in data:
        from app.services.import_platforms import validate_allowed_extractors

        raw = data.pop("import_allowed_extractors")
        try:
            s.import_allowed_extractors_json = validate_allowed_extractors(list(raw or []))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    for key, value in data.items():
        setattr(s, key, value)
    invalidate_rate_limit_cache()
    return get_settings_ep(db, ctx)


def _count_hidden_orgs(ctx: AuthContext, db: Session) -> int:
    rows = db.scalars(select(Organization.id)).all()
    return sum(1 for org_id in rows if is_hidden(db, ctx.user.id, "org", org_id))


@router.get("/orgs")
def list_orgs(
    include_hidden: bool = False,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    rows = db.scalars(select(Organization).options(joinedload(Organization.tariff)).order_by(Organization.created_at)).all()
    items = []
    for org in rows:
        hidden = is_hidden(db, ctx.user.id, "org", org.id)
        if not include_hidden and hidden:
            continue
        payload = org_public(org)
        payload["hidden"] = hidden
        members = db.scalars(select(Membership).where(Membership.org_id == org.id)).all()
        payload["members"] = []
        for membership in members:
            user = db.get(User, membership.user_id)
            if user:
                payload["members"].append(user_public(user, membership.role))
        items.append(payload)
    return {"items": items, "hidden_count": _count_hidden_orgs(ctx, db)}


@router.post("/orgs/{org_id}/hide")
def hide_org(
    org_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "org", org.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="org", object_id=org.id))
    return {"status": "ok"}


@router.post("/orgs/{org_id}/unhide")
def unhide_org(
    org_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
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
    return {"status": "ok"}


@router.get("/orgs/{org_id}/ledger")
def org_ledger_ep(
    org_id: str,
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    return org_ledger(
        db,
        org_id,
        start=start,
        end=end,
        user_id=(user_id or "").strip() or None,
        kind=(kind or "").strip() or None,
    )


@router.post("/orgs/{org_id}/users/{user_id}/reset-password")
def reset_org_admin_password(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
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
    return {"status": "ok", "password": password}


@router.patch("/orgs/{org_id}/tariff")
def assign_org_tariff(
    org_id: str,
    body: OrgTariffBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    tariff = db.get(Tariff, body.tariff_id)
    if org is None or tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    org.tariff_id = tariff.id
    org.updated_at = utcnow()
    write_audit(db, "org.tariff", ctx, {"org_id": org.id, "tariff_id": tariff.id})
    db.refresh(org)
    org.tariff = tariff
    return org_public(org)


def _actor_is_org_admin(db: Session, ctx: AuthContext) -> tuple[Organization, Membership] | None:
    org, membership = load_org_bundle(db, ctx.actor)
    if org is None or membership is None or membership.role != "org_admin":
        return None
    return org, membership


@router.post("/impersonate")
def impersonate(
    body: ImpersonateBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
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
    return {"status": "ok"}


@router.delete("/impersonate")
def stop_impersonate(
    db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    if ctx.session is None:
        ctx.raise_error(ErrorCode.forbidden)
    if not ctx.actor.is_instance_admin and _actor_is_org_admin(db, ctx) is None:
        ctx.raise_error(ErrorCode.forbidden)
    write_audit(db, "impersonate.stop", ctx)
    ctx.session.impersonate_user_id = None
    return {"status": "ok"}


@router.get("/instance/stats")
def stats(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
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
    return {
        "orgs": orgs,
        "users": users,
        "tasks_queued": queued,
        "tasks_running": running,
        **usage,
        "usage_total": usage["total_amount"],
    }


@router.get("/skills/base")
def list_base_skills(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    rows = db.scalars(select(Skill).where(Skill.scope == "base").order_by(Skill.name)).all()
    return {"items": [skill_public(row) for row in rows]}


@router.post("/skills/base")
def create_base_skill(
    body: BaseSkillBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    now = utcnow()
    skill = Skill(
        id=new_id(),
        scope="base",
        name=body.name.strip(),
        body=body.body,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    return skill_public(skill)


@router.patch("/skills/base/{skill_id}")
def patch_base_skill(
    skill_id: str,
    body: BaseSkillBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return skill_public(skill)


@router.delete("/skills/base/{skill_id}")
def delete_base_skill(
    skill_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.models import Skill

    _admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return {"status": "ok"}

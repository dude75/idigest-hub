"""Instance admin: воркеры, тарифы, настройки, орги, impersonate, статистика."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.crypto import encrypt_str
from app.db import get_session
from app.deps import AuthContext, get_instance_settings, load_org_bundle, require_auth
from app.errors import ErrorCode
from app.models import Membership, Organization, Task, Tariff, UsageEvent, User, WorkerNode, new_id
from app.money import parse_money
from app.presenters import org_public, tariff_public, user_public, worker_public
from app.routers.auth import seed_default_tariff
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.services.audit import write_audit
from app.services.stats import completed_job_stats
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
    for key, value in data.items():
        setattr(s, key, value)
    invalidate_rate_limit_cache()
    return get_settings_ep(db, ctx)


@router.get("/orgs")
def list_orgs(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    rows = db.scalars(select(Organization).options(joinedload(Organization.tariff)).order_by(Organization.created_at)).all()
    items = []
    for org in rows:
        payload = org_public(org)
        members = db.scalars(select(Membership).where(Membership.org_id == org.id)).all()
        payload["members"] = []
        for membership in members:
            user = db.get(User, membership.user_id)
            if user:
                payload["members"].append(user_public(user, membership.role))
        items.append(payload)
    return {"items": items}


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
def stats(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    queued = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "queued")) or 0)
    running = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0)
    jobs = completed_job_stats(db)
    orgs = int(db.scalar(select(func.count()).select_from(Organization)) or 0)
    users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    usage_sum = db.scalar(select(func.coalesce(func.sum(UsageEvent.amount), 0)))
    return {
        "orgs": orgs,
        "users": users,
        "tasks_queued": queued,
        "tasks_running": running,
        **jobs,
        "usage_total": str(usage_sum),
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

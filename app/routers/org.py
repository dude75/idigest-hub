"""Организация: имя, люди, тариф, TTL пароля, disable, офбординг."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, require_auth
from app.errors import ErrorCode
from app.models import Membership, Tariff, UsageEvent, User, new_id
from app.presenters import org_public, user_public
from app.routers.auth import invalidate_user_sessions, revoke_user_tokens
from app.security import hash_password, random_password
from app.services.access import guard_last_org_admin
from app.services.audit import write_audit
from app.services.offboarding import transfer_user, wipe_user_content
from app.services.stats import completed_job_stats
from app.timeutil import utcnow

router = APIRouter()


class OrgPatch(BaseModel):
    name: str | None = None


class OrgTariffBody(BaseModel):
    tariff_id: str


class OrgSettingsPatch(BaseModel):
    password_ttl_days: int | None = None


class CreateUserBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "org_member"
    locale: str = "en"


class RoleBody(BaseModel):
    role: str


class OffboardBody(BaseModel):
    action: str
    target_user_id: str | None = None


@router.get("/org/available-tariffs")
def available_tariffs(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    from app.presenters import tariff_public

    ctx.require_org()
    rows = db.scalars(
        select(Tariff).where(Tariff.archived_at.is_(None), Tariff.available_on_signup.is_(True))
    ).all()
    return {"items": [tariff_public(row) for row in rows]}


@router.get("/org")
def get_org(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    org, _ = ctx.require_org()
    total = db.scalar(select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(UsageEvent.org_id == org.id))
    return org_public(org, usage={"total_amount": str(total)})


@router.get("/org/stats")
def org_stats(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    org, _ = ctx.require_org()
    return completed_job_stats(db, org_id=org.id)


@router.patch("/org")
def patch_org(
    body: OrgPatch, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    if body.name and body.name.strip():
        org.name = body.name.strip()
        org.updated_at = utcnow()
    return org_public(org)


@router.patch("/org/tariff")
def patch_org_tariff(
    body: OrgTariffBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    tariff = db.get(Tariff, body.tariff_id)
    if tariff is None or tariff.archived_at is not None or not tariff.available_on_signup:
        ctx.raise_error(ErrorCode.tariff_not_available)
    org.tariff_id = tariff.id
    org.updated_at = utcnow()
    org.tariff = tariff
    write_audit(db, "org.tariff.self", ctx, {"tariff_id": tariff.id})
    return org_public(org)


@router.patch("/org/settings")
def patch_org_settings(
    body: OrgSettingsPatch, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    if body.password_ttl_days is not None:
        if body.password_ttl_days < 0:
            ctx.raise_error(ErrorCode.validation_error)
        org.password_ttl_days = body.password_ttl_days
        org.updated_at = utcnow()
    return org_public(org)


@router.get("/org/users")
def list_users(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    org, _ = ctx.require_org()
    memberships = db.scalars(select(Membership).where(Membership.org_id == org.id)).all()
    items = []
    for membership in memberships:
        user = db.get(User, membership.user_id)
        if user:
            items.append(user_public(user, membership.role))
    return {"items": items}


@router.post("/org/users")
def create_user(
    body: CreateUserBody, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    if body.role not in {"org_admin", "org_member"}:
        ctx.raise_error(ErrorCode.validation_error)
    email = str(body.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        ctx.raise_error(ErrorCode.email_taken)
    now = utcnow()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(body.password),
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
    db.add(Membership(id=new_id(), user_id=user.id, org_id=org.id, role=body.role))
    return user_public(user, body.role)


@router.patch("/org/users/{user_id}")
def patch_user_role(
    user_id: str,
    body: RoleBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org_admin()
    if body.role not in {"org_admin", "org_member"}:
        ctx.raise_error(ErrorCode.validation_error)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user_id)
    )
    if membership is None:
        ctx.raise_error(ErrorCode.not_found)
    if membership.role == "org_admin" and body.role == "org_member":
        guard_last_org_admin(db, org.id, user_id, ctx.locale)
    membership.role = body.role
    user = db.get(User, user_id)
    return user_public(user, body.role) if user else {"id": user_id}


@router.post("/org/users/{user_id}/disable")
def disable_user(
    user_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if membership.role == "org_admin":
        guard_last_org_admin(db, org.id, user_id, ctx.locale)
    user.disabled_at = utcnow()
    user.updated_at = utcnow()
    invalidate_user_sessions(db, user.id)
    revoke_user_tokens(db, user.id)
    write_audit(db, "user.disable", ctx, {"user_id": user.id})
    return user_public(user, membership.role)


@router.post("/org/users/{user_id}/enable")
def enable_user(
    user_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    user.disabled_at = None
    user.updated_at = utcnow()
    write_audit(db, "user.enable", ctx, {"user_id": user.id})
    return user_public(user, membership.role)


@router.post("/org/users/{user_id}/reset-password")
def reset_user_password(
    user_id: str, db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)
) -> dict:
    org, _ = ctx.require_org_admin()
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    password = random_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    user.updated_at = utcnow()
    invalidate_user_sessions(db, user.id)
    return {"status": "ok", "password": password}


@router.post("/org/users/{user_id}/offboard")
def offboard_user(
    user_id: str,
    body: OffboardBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    org, _ = ctx.require_org_admin()
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if membership.role == "org_admin":
        guard_last_org_admin(db, org.id, user_id, ctx.locale)
    if body.action == "transfer":
        if not body.target_user_id:
            ctx.raise_error(ErrorCode.validation_error)
        target_m = db.scalar(
            select(Membership).where(
                Membership.org_id == org.id, Membership.user_id == body.target_user_id
            )
        )
        target = db.get(User, body.target_user_id) if body.target_user_id else None
        if target_m is None or target is None or target.disabled_at is not None:
            ctx.raise_error(ErrorCode.not_found)
        transfer_user(db, user, target)
        write_audit(db, "user.offboard.transfer", ctx, {"user_id": user.id, "target": target.id})
    elif body.action == "wipe":
        wipe_user_content(db, user)
        write_audit(db, "user.offboard.wipe", ctx, {"user_id": user.id})
    else:
        ctx.raise_error(ErrorCode.validation_error)
    db.delete(membership)
    db.delete(user)
    return {"status": "ok"}

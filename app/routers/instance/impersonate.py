from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, load_org_bundle, require_auth
from app.errors import ErrorCode
from app.models import Membership, Organization, User
from app.routers.instance._body import ImpersonateBody
from app.routers.instance._router import router
from app.schemas.common import OkStatusResponse
from app.services.audit import write_audit



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

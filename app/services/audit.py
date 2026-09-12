"""Аудит действий (ТЗ §14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.deps import AuthContext
from app.models import AuditLog, Membership, User, new_id
from app.timeutil import utcnow


def write_audit(
    db: Session,
    action: str,
    ctx: AuthContext | None = None,
    payload: dict[str, Any] | None = None,
    actor_id: str | None = None,
    on_behalf_of: str | None = None,
) -> None:
    actor = actor_id
    behalf = on_behalf_of
    if ctx is not None:
        actor = ctx.actor.id
        if ctx.impersonating:
            behalf = ctx.user.id
    db.add(
        AuditLog(
            id=new_id(),
            actor_user_id=actor,
            on_behalf_of_user_id=behalf,
            action=action,
            payload_json=payload,
            created_at=utcnow(),
        )
    )


def list_audit(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
) -> list[dict[str, Any]]:
    actor = aliased(User)
    behalf = aliased(User)
    query = (
        select(AuditLog, actor.email, behalf.email)
        .outerjoin(actor, actor.id == AuditLog.actor_user_id)
        .outerjoin(behalf, behalf.id == AuditLog.on_behalf_of_user_id)
        .order_by(AuditLog.created_at.desc())
    )
    if start is not None:
        query = query.where(AuditLog.created_at >= start)
    if end is not None:
        query = query.where(AuditLog.created_at < end)
    if org_id:
        member_ids = select(Membership.user_id).where(Membership.org_id == org_id)
        query = query.where(
            or_(
                AuditLog.actor_user_id.in_(member_ids),
                AuditLog.on_behalf_of_user_id.in_(member_ids),
            )
        )
    if user_id:
        query = query.where(
            or_(
                AuditLog.actor_user_id == user_id,
                AuditLog.on_behalf_of_user_id == user_id,
            )
        )
    if action:
        query = query.where(AuditLog.action == action)
    rows = db.execute(query).all()
    return [
        {
            "id": row[0].id,
            "action": row[0].action,
            "actor_email": row[1],
            "on_behalf_of_email": row[2],
            "payload": row[0].payload_json,
            "created_at": row[0].created_at.isoformat(),
        }
        for row in rows
    ]

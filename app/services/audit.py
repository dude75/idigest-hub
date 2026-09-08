"""Аудит действий (ТЗ §14)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.models import AuditLog, new_id
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

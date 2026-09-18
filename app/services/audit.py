"""Аудит действий (ТЗ §14)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.deps import AuthContext
from app.models import AuditLog, Membership, User, new_id
from app.timeutil import isoformat_utc, utcnow


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


def write_public_audit(
    db: Session,
    action: str,
    *,
    org_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    body = {"org_id": org_id, **(payload or {})}
    write_audit(db, action, payload=body)


def _audit_filters(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
) -> list:
    filters = []
    if start is not None:
        filters.append(AuditLog.created_at >= start)
    if end is not None:
        filters.append(AuditLog.created_at < end)
    if org_id:
        member_ids = select(Membership.user_id).where(Membership.org_id == org_id)
        filters.append(
            or_(
                AuditLog.actor_user_id.in_(member_ids),
                AuditLog.on_behalf_of_user_id.in_(member_ids),
            )
        )
    if user_id:
        filters.append(
            or_(
                AuditLog.actor_user_id == user_id,
                AuditLog.on_behalf_of_user_id == user_id,
            )
        )
    if action:
        filters.append(AuditLog.action == action)
    return filters


def list_audit(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    filters = _audit_filters(
        start=start,
        end=end,
        org_id=org_id,
        user_id=user_id,
        action=action,
    )
    count_q = select(func.count()).select_from(AuditLog)
    if filters:
        count_q = count_q.where(*filters)
    total = int(db.scalar(count_q) or 0)

    actor = aliased(User)
    behalf = aliased(User)
    query = (
        select(AuditLog, actor.email, behalf.email)
        .outerjoin(actor, actor.id == AuditLog.actor_user_id)
        .outerjoin(behalf, behalf.id == AuditLog.on_behalf_of_user_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if filters:
        query = query.where(*filters)
    rows = db.execute(query).all()
    items = [
        {
            "id": row[0].id,
            "action": row[0].action,
            "actor_email": row[1],
            "on_behalf_of_email": row[2],
            "payload": row[0].payload_json,
            "created_at": isoformat_utc(row[0].created_at),
        }
        for row in rows
    ]
    return items, total


_EXPORT_BATCH = 1000
_CSV_HEADER = ("created_at", "action", "actor_email", "on_behalf_of_email", "payload")


def export_audit_csv(
    db: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(_CSV_HEADER)
    offset = 0
    while True:
        items, total = list_audit(
            db,
            start=start,
            end=end,
            org_id=org_id,
            user_id=user_id,
            action=action,
            limit=_EXPORT_BATCH,
            offset=offset,
        )
        if not items:
            break
        for item in items:
            payload = item["payload"]
            payload_text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""
            writer.writerow(
                [
                    item["created_at"],
                    item["action"],
                    item["actor_email"] or "",
                    item["on_behalf_of_email"] or "",
                    payload_text,
                ]
            )
        offset += len(items)
        if offset >= total:
            break
    return buf.getvalue()

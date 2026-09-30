"""Удаление завершённых строк tasks (история задач), без артефактов и без usage_events."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import InstanceSettings, Task, UsageEvent
from app.timeutil import utcnow

log = logging.getLogger("app")

ACTIVE_TASK_STATUSES = ("queued", "running")
_PURGE_BATCH = 500


def _purge_filters(
    *,
    org_id: str | None = None,
    user_id: str | None = None,
    retention_days: int | None = None,
) -> list:
    filters = [~Task.status.in_(ACTIVE_TASK_STATUSES)]
    org = (org_id or "").strip()
    user = (user_id or "").strip()
    if org:
        filters.append(Task.org_id == org)
    if user:
        filters.append(Task.user_id == user)
    if retention_days is not None and retention_days > 0:
        cutoff = utcnow() - timedelta(days=int(retention_days))
        filters.append(Task.updated_at < cutoff)
    return filters


def purge_terminal_tasks(
    db: Session,
    *,
    org_id: str | None = None,
    user_id: str | None = None,
    retention_days: int | None = None,
) -> int:
    filters = _purge_filters(org_id=org_id, user_id=user_id, retention_days=retention_days)
    deleted = 0
    while True:
        ids = list(db.scalars(select(Task.id).where(*filters).limit(_PURGE_BATCH)).all())
        if not ids:
            break
        db.execute(update(UsageEvent).where(UsageEvent.task_id.in_(ids)).values(task_id=None))
        db.execute(delete(Task).where(Task.id.in_(ids)))
        db.flush()
        deleted += len(ids)
    if deleted:
        log.info(
            "purged terminal tasks count=%s org_id=%s user_id=%s retention_days=%s",
            deleted,
            org_id or "",
            user_id or "",
            retention_days,
        )
    return deleted


def purge_expired_task_history(db: Session, settings: InstanceSettings) -> int:
    days = int(settings.task_history_retention_days)
    if days <= 0:
        return 0
    return purge_terminal_tasks(db, retention_days=days)

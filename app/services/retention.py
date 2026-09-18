"""Удаление аудио старше лимита хранения тарифа организации."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Audio, Organization, Task
from app.services.artifacts import hard_delete_audio
from app.timeutil import as_utc, utcnow

log = logging.getLogger("app")


def purge_expired_audio(db: Session) -> int:
    now = utcnow()
    orgs = list(db.scalars(select(Organization).options(joinedload(Organization.tariff))).all())
    deleted = 0
    for org in orgs:
        days = int(org.tariff.audio_retention_days)
        if days <= 0:
            continue
        cutoff = now - timedelta(days=days)
        rows = list(db.scalars(select(Audio).where(Audio.org_id == org.id)).all())
        for audio in rows:
            created = as_utc(audio.created_at)
            if created >= cutoff:
                continue
            busy = db.scalar(
                select(Task.id)
                .where(Task.audio_id == audio.id, Task.status.in_(("queued", "running")))
                .limit(1)
            )
            if busy:
                continue
            hard_delete_audio(db, audio)
            deleted += 1
    if deleted:
        log.info("purged expired audio count=%s", deleted)
    return deleted

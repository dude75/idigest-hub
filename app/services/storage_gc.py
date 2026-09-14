"""Durable queue for blob deletes (local/S3) with retry on failure and startup."""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PendingStorageDelete, new_id
from app.services.storage import get_storage
from app.timeutil import utcnow

log = logging.getLogger("app")

_storage_delete_hooks_registered = False
_SESSION_FLAG = "storage_delete_queued"
_drain_lock = threading.Lock()


def queue_storage_delete(session: Session, storage_path: str) -> None:
    """Persist blob delete intent in the same DB transaction as the row removal."""
    existing = session.scalar(
        select(PendingStorageDelete.id)
        .where(PendingStorageDelete.storage_path == storage_path)
        .limit(1)
    )
    if existing is None:
        session.add(
            PendingStorageDelete(
                id=new_id(),
                storage_path=storage_path,
                created_at=utcnow(),
            )
        )
    session.info[_SESSION_FLAG] = True


def drain_pending_storage_deletes(db: Session, *, limit: int = 50) -> int:
    """Try to delete queued blobs; return count of rows removed from the queue."""
    with _drain_lock:
        rows = list(
            db.scalars(
                select(PendingStorageDelete)
                .order_by(PendingStorageDelete.created_at)
                .limit(limit)
            ).all()
        )
        if not rows:
            return 0

        storage = get_storage()
        removed = 0
        for row in rows:
            try:
                storage.delete(row.storage_path)
                db.delete(row)
                removed += 1
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)[:500]
                log.exception(
                    "pending storage delete failed path=%s attempts=%s",
                    row.storage_path,
                    row.attempts,
                )
        db.commit()
        return removed


def drain_all_pending_storage_deletes() -> int:
    """Process the full queue; used on startup and after commit."""
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    total = 0
    db = SessionLocal()
    try:
        while True:
            removed = drain_pending_storage_deletes(db, limit=100)
            total += removed
            if removed == 0:
                break
    finally:
        db.close()
    if total:
        log.info("drained pending storage deletes count=%s", total)
    return total


def _drain_pending_background() -> None:
    try:
        drain_all_pending_storage_deletes()
    except Exception:
        log.exception("background pending storage delete drain failed")


def register_storage_delete_hooks() -> None:
    global _storage_delete_hooks_registered
    if _storage_delete_hooks_registered:
        return
    from sqlalchemy import event
    from sqlalchemy.orm import Session as OrmSession

    @event.listens_for(OrmSession, "after_commit")
    def _schedule_storage_purge(session: OrmSession) -> None:
        if not session.info.pop(_SESSION_FLAG, False):
            return
        threading.Thread(target=_drain_pending_background, daemon=True).start()

    @event.listens_for(OrmSession, "after_rollback")
    def _drop_storage_delete_flag(session: OrmSession) -> None:
        session.info.pop(_SESSION_FLAG, None)

    _storage_delete_hooks_registered = True


def reset_storage_delete_hooks() -> None:
    """Test helper."""
    global _storage_delete_hooks_registered
    _storage_delete_hooks_registered = False

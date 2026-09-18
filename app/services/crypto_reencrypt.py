"""Background re-encryption of retiring DEKs onto the active DEK."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import (
    ENCRYPTED_COLUMNS,
    decrypt_str,
    delete_retiring_dek,
    encrypt_str,
    get_active_dek,
    token_dek_id,
)
from app.models import (
    DataEncryptionKey,
    EncryptionJob,
    InstanceSettings,
    Organization,
    Summary,
    Transcript,
    WorkerNode,
    new_id,
)
from app.timeutil import utcnow

log = logging.getLogger("app")

BATCH_SIZE = 50

_active_job_id: str | None = None
_cancelled: set[str] = set()
_bg_thread: threading.Thread | None = None


def active_job_id() -> str | None:
    return _active_job_id


def request_cancel(job_id: str) -> None:
    _cancelled.add(job_id)


def _is_cancelled(job_id: str) -> bool:
    return job_id in _cancelled


def _init_progress() -> dict[str, Any]:
    progress: dict[str, Any] = {"tables": {}, "retiring_deleted": 0}
    for table, column in ENCRYPTED_COLUMNS:
        key = f"{table}.{column}"
        progress["tables"][key] = {"total": 0, "done": 0}
    return progress


def _count_pending(db: Session, table: str, column: str, retiring_ids: set[str]) -> int:
    pending = 0
    if table == "worker_nodes":
        for row in db.scalars(select(WorkerNode)).all():
            dek = token_dek_id(getattr(row, column))
            if dek in retiring_ids:
                pending += 1
        return pending
    if table == "instance_settings":
        row = db.get(InstanceSettings, 1)
        if row is None:
            return 0
        dek = token_dek_id(getattr(row, column))
        return 1 if dek in retiring_ids else 0
    if table == "organizations":
        for row in db.scalars(select(Organization)).all():
            dek = token_dek_id(getattr(row, column))
            if dek in retiring_ids:
                pending += 1
        return pending
    if table == "transcripts":
        for row in db.scalars(select(Transcript)).all():
            dek = token_dek_id(getattr(row, column))
            if dek in retiring_ids:
                pending += 1
        return pending
    if table == "summaries":
        for row in db.scalars(select(Summary)).all():
            dek = token_dek_id(getattr(row, column))
            if dek in retiring_ids:
                pending += 1
        return pending
    return pending


def _reencrypt_batch(
    db: Session,
    table: str,
    column: str,
    retiring_ids: set[str],
    *,
    limit: int,
) -> int:
    done = 0
    if table == "worker_nodes":
        rows = list(db.scalars(select(WorkerNode)).all())
        for row in rows:
            if done >= limit:
                break
            value = getattr(row, column)
            if token_dek_id(value) not in retiring_ids:
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            done += 1
        return done
    if table == "instance_settings":
        row = db.get(InstanceSettings, 1)
        if row is None or done >= limit:
            return 0
        value = getattr(row, column)
        if token_dek_id(value) not in retiring_ids:
            return 0
        plain = decrypt_str(value, db)
        setattr(row, column, encrypt_str(plain, db))
        return 1
    if table == "organizations":
        rows = list(db.scalars(select(Organization)).all())
        for row in rows:
            if done >= limit:
                break
            value = getattr(row, column)
            if token_dek_id(value) not in retiring_ids:
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            done += 1
        return done
    if table == "transcripts":
        rows = list(db.scalars(select(Transcript)).all())
        for row in rows:
            if done >= limit:
                break
            value = getattr(row, column)
            if token_dek_id(value) not in retiring_ids:
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            done += 1
        return done
    if table == "summaries":
        rows = list(db.scalars(select(Summary)).all())
        for row in rows:
            if done >= limit:
                break
            value = getattr(row, column)
            if token_dek_id(value) not in retiring_ids:
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            done += 1
        return done
    return done


def _run_job(job_id: str) -> None:
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    global _active_job_id
    try:
        job = db.get(EncryptionJob, job_id)
        if job is None:
            return
        retiring = list(
            db.scalars(select(DataEncryptionKey).where(DataEncryptionKey.status == "retiring")).all()
        )
        retiring_ids = {row.id for row in retiring}
        if not retiring_ids:
            job.status = "completed"
            job.completed_at = utcnow()
            job.progress_json = _init_progress()
            db.commit()
            return

        progress = job.progress_json or _init_progress()
        for table, column in ENCRYPTED_COLUMNS:
            key = f"{table}.{column}"
            progress["tables"].setdefault(key, {"total": 0, "done": 0})
            progress["tables"][key]["total"] = _count_pending(db, table, column, retiring_ids)

        job.status = "running"
        job.started_at = utcnow()
        job.progress_json = progress
        db.commit()

        active_id, _ = get_active_dek(db)
        if job.target_dek_id != active_id:
            job.status = "failed"
            job.error = "target DEK is not active"
            job.completed_at = utcnow()
            db.commit()
            return

        while retiring_ids and not _is_cancelled(job_id):
            moved_any = False
            for table, column in ENCRYPTED_COLUMNS:
                key = f"{table}.{column}"
                n = _reencrypt_batch(db, table, column, retiring_ids, limit=BATCH_SIZE)
                if n:
                    moved_any = True
                    progress["tables"][key]["done"] = progress["tables"][key].get("done", 0) + n
                    job.progress_json = dict(progress)
                    db.commit()
            if not moved_any:
                break
            time.sleep(0.05)

        if _is_cancelled(job_id):
            job.status = "canceled"
            job.completed_at = utcnow()
            db.commit()
            return

        deleted = 0
        for row in retiring:
            if delete_retiring_dek(db, row.id):
                deleted += 1
        progress["retiring_deleted"] = deleted
        job.progress_json = progress
        job.status = "completed"
        job.completed_at = utcnow()
        db.commit()
        log.info("crypto reencrypt completed job=%s deleted_deks=%s", job_id, deleted)
    except Exception as exc:
        log.exception("crypto reencrypt failed job=%s", job_id)
        db.rollback()
        job = db.get(EncryptionJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:500]
            job.completed_at = utcnow()
            db.commit()
    finally:
        _active_job_id = None
        _cancelled.discard(job_id)
        db.close()


def _run_job_thread(job_id: str) -> None:
    _run_job(job_id)


def start_reencrypt_job(db: Session) -> EncryptionJob | None:
    global _active_job_id, _bg_thread
    if _active_job_id is not None:
        return None

    retiring = list(db.scalars(select(DataEncryptionKey).where(DataEncryptionKey.status == "retiring")).all())
    if not retiring:
        return None

    active_id, _ = get_active_dek(db)
    now = utcnow()
    job = EncryptionJob(
        id=new_id(),
        target_dek_id=active_id,
        status="queued",
        progress_json=_init_progress(),
        created_at=now,
    )
    db.add(job)
    db.flush()
    db.commit()

    _active_job_id = job.id
    thread = threading.Thread(target=_run_job_thread, args=(job.id,), name=f"reencrypt-{job.id[:8]}", daemon=True)
    _bg_thread = thread
    thread.start()
    return job


def latest_job(db: Session) -> EncryptionJob | None:
    return db.scalar(select(EncryptionJob).order_by(EncryptionJob.created_at.desc()).limit(1))


def wait_reencrypt_job(timeout_sec: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if _bg_thread is None or not _bg_thread.is_alive():
            return
        _bg_thread.join(timeout=0.05)


def reset_crypto_reencrypt() -> None:
    """Test helper."""
    global _active_job_id, _bg_thread
    wait_reencrypt_job(timeout_sec=5.0)
    _active_job_id = None
    _cancelled.clear()
    _bg_thread = None

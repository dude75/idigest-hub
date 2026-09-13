"""Background execution of URL import tasks."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import Audio, Organization, Task, new_id
from app.services.import_platforms import (
    allowed_extractors,
    effective_download_proxy,
    normalize_import_audio_bitrate_kbps,
)
from app.services.storage import PayloadTooLarge, get_storage
from app.services.url_import import UrlImportError, cleanup_import_path, download_audio
from app.timeutil import utcnow

log = logging.getLogger("app")

MAX_CONCURRENT_IMPORTS = 2

_active: set[str] = set()
_cancelled: set[str] = set()
_bg_threads: dict[str, threading.Thread] = {}


def is_import_canceled(task_id: str) -> bool:
    return task_id in _cancelled


def request_import_cancel(task_id: str) -> None:
    _cancelled.add(task_id)


def import_slots_available() -> bool:
    return len(_active) < MAX_CONCURRENT_IMPORTS


def _update_task_meta(db: Session, task: Task, stage: str, extra: dict[str, Any] | None = None) -> None:
    meta = dict(task.meta_json or {})
    meta["stage"] = stage
    if extra:
        meta.update(extra)
    task.meta_json = meta
    task.updated_at = utcnow()
    db.flush()


def _fail_task(db: Session, task: Task, code: str, meta: dict[str, Any] | None = None) -> None:
    payload = dict(task.meta_json or {})
    if meta:
        payload.update(meta)
    payload["stage"] = "error"
    task.meta_json = payload
    task.status = "error"
    task.error_code = code
    task.updated_at = utcnow()
    db.flush()
    log.warning(
        "import task failed task=%s code=%s host=%s reason=%s detail=%s",
        task.id,
        code,
        payload.get("host"),
        payload.get("reason"),
        payload.get("error_detail"),
    )
    from app.prometheus_metrics import observe_task_terminal

    observe_task_terminal(task)


async def _run_import_task(task_id: str) -> None:
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    source_path = None
    try:
        task = db.get(Task, task_id)
        if task is None or task.type != "import":
            return
        if task.status != "running":
            return

        from app.deps import get_instance_settings

        settings = get_instance_settings(db)
        if not settings.import_enabled:
            _fail_task(db, task, "import_disabled")
            db.commit()
            return

        meta = dict(task.meta_json or {})
        url = str(meta.get("url") or "").strip()
        if not url:
            _fail_task(db, task, "invalid_url")
            db.commit()
            return

        org = db.get(Organization, task.org_id)
        if org is None:
            _fail_task(db, task, "not_found")
            db.commit()
            return

        max_bytes = int(task.snap_max_upload_bytes)
        proxy = effective_download_proxy(settings, db)
        allowed = allowed_extractors(settings)
        max_bitrate = normalize_import_audio_bitrate_kbps(settings.import_audio_bitrate_kbps)

        def on_progress(stage: str, extra: dict[str, Any]) -> None:
            session = SessionLocal()
            try:
                row = session.get(Task, task_id)
                if row is None:
                    return
                _update_task_meta(session, row, stage, extra)
                session.commit()
            finally:
                session.close()

        result = await asyncio.to_thread(
            download_audio,
            url,
            settings_allowed=allowed,
            proxy=proxy,
            cookies_path=settings.download_cookies_path,
            max_audio_bitrate_kbps=max_bitrate,
            max_bytes=max_bytes,
            on_progress=on_progress,
            is_canceled=lambda: is_import_canceled(task_id),
        )
        source_path = result.source_path

        if is_import_canceled(task_id):
            _fail_task(db, task, "canceled")
            db.commit()
            return

        audio_id = new_id()
        storage = get_storage()
        try:
            storage_path = await storage.save_file_path(
                audio_id, result.suffix, result.source_path, max_bytes=max_bytes
            )
        except PayloadTooLarge:
            _fail_task(db, task, "payload_too_large", {"host": result.host})
            db.commit()
            return

        audio = Audio(
            id=audio_id,
            org_id=task.org_id,
            owner_user_id=task.user_id,
            storage_path=storage_path,
            original_filename=result.original_filename,
            duration_sec=result.duration_sec,
            created_at=utcnow(),
        )
        db.add(audio)
        task.audio_id = audio.id
        task.status = "success"
        task.error_code = None
        task.meta_json = {
            **meta,
            "stage": "done",
            "host": result.host,
            "platform": result.platform_label,
            "title": result.title,
            "extractor": result.extractor_key,
        }
        task.updated_at = utcnow()
        from app.prometheus_metrics import observe_task_terminal

        observe_task_terminal(task)
        db.commit()
    except UrlImportError as exc:
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            _fail_task(db, task, exc.code, exc.meta)
            db.commit()
    except Exception as exc:
        log.exception("import task failed task=%s", task_id)
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            detail = str(exc).strip()
            if len(detail) > 500:
                detail = detail[:497] + "..."
            _fail_task(
                db,
                task,
                "download_failed",
                {"error_detail": detail} if detail else None,
            )
            db.commit()
    finally:
        if source_path is not None:
            cleanup_import_path(source_path)
        _active.discard(task_id)
        _cancelled.discard(task_id)
        _bg_threads.pop(task_id, None)
        db.close()


def _run_import_thread(task_id: str) -> None:
    asyncio.run(_run_import_task(task_id))


def maybe_start_import(db: Session, task: Task) -> None:
    if task.type != "import" or task.status != "queued":
        return
    if task.id in _active or task.id in _bg_threads:
        return
    if not import_slots_available():
        task.meta_json = {**(task.meta_json or {}), "stage": "queued"}
        return

    _active.add(task.id)
    task.status = "running"
    task.meta_json = {**(task.meta_json or {}), "stage": "probing"}
    task.updated_at = utcnow()
    db.flush()
    db.commit()
    thread = threading.Thread(
        target=_run_import_thread,
        args=(task.id,),
        name=f"import-{task.id[:8]}",
        daemon=True,
    )
    _bg_threads[task.id] = thread
    thread.start()


def wait_import_tasks(timeout_sec: float = 30.0) -> None:
    """Test helper: block until background import threads finish."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        threads = [thread for thread in _bg_threads.values() if thread.is_alive()]
        if not threads:
            return
        for thread in threads:
            thread.join(timeout=0.05)


def reset_import_runner() -> None:
    """Test helper."""
    wait_import_tasks(timeout_sec=5.0)
    _active.clear()
    _cancelled.clear()
    _bg_threads.clear()

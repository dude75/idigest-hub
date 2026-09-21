"""Background execution of meeting capture tasks."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Audio, Task, WorkerNode, new_id
from app.services.capture_workers import (
    delete_capture_task,
    download_capture_artifact,
    get_capture_task,
    map_capture_worker_error,
    post_capture,
    stop_capture_task,
)
from app.services.storage import PayloadTooLarge, get_storage
from app.services.upload_validation import InvalidAudioContent, resolve_capture_artifact
from app.services.workers import WorkerClientError
from app.timeutil import utcnow

log = logging.getLogger("app")

MAX_CONCURRENT_CAPTURES = 2
_POLL_SEC = 1.5

_active: set[str] = set()
_cancelled: set[str] = set()
_stop_requested: set[str] = set()
_bg_threads: dict[str, threading.Thread] = {}


def is_capture_canceled(task_id: str) -> bool:
    return task_id in _cancelled


def request_capture_cancel(task_id: str) -> None:
    _cancelled.add(task_id)


def request_capture_stop(task_id: str) -> None:
    _stop_requested.add(task_id)


def capture_slots_available() -> bool:
    return len(_active) < MAX_CONCURRENT_CAPTURES


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
    from app.prometheus_metrics import observe_task_terminal

    observe_task_terminal(task)


def _worker_error_code(body: dict[str, Any]) -> str | None:
    err = body.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        return str(code) if code else None
    return None


def _filename_from_headers(headers: dict[str, str], default: str) -> str:
    disposition = headers.get("content-disposition") or ""
    if "filename=" in disposition:
        part = disposition.split("filename=", 1)[1].strip().strip('"')
        if part:
            return part
    return default


async def _run_capture_task(task_id: str) -> None:
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    temp_path: Path | None = None
    worker_node: WorkerNode | None = None
    worker_task_id: str | None = None
    try:
        task = db.get(Task, task_id)
        if task is None or task.type != "capture":
            return
        if task.status != "running":
            return
        if is_capture_canceled(task_id):
            _fail_task(db, task, "canceled")
            db.commit()
            return

        from app.deps import get_instance_settings

        settings = get_instance_settings(db)
        if not settings.capture_enabled:
            _fail_task(db, task, "capture_disabled")
            db.commit()
            return

        meta = dict(task.meta_json or {})
        meeting_url = str(meta.get("meeting_url") or "").strip()
        if not meeting_url or not task.worker_id:
            _fail_task(db, task, "invalid_url")
            db.commit()
            return

        worker_node = db.get(WorkerNode, task.worker_id)
        if worker_node is None:
            _fail_task(db, task, "pipeline_error")
            db.commit()
            return

        pin = str(meta.get("pin") or "")
        jwt = meta.get("jwt")
        jwt_str = jwt if isinstance(jwt, str) and jwt.strip() else None
        connector = str(meta.get("connector") or "jitsi")
        display_name = str(meta.get("display_name") or "Transcription Bot")

        _update_task_meta(db, task, "joining")
        db.commit()

        if is_capture_canceled(task_id):
            _fail_task(db, task, "canceled")
            db.commit()
            return

        try:
            body = await post_capture(
                db,
                worker_node,
                connector=connector,
                meeting_url=meeting_url,
                pin=pin,
                jwt=jwt_str,
                display_name=display_name,
            )
        except WorkerClientError as exc:
            code = map_capture_worker_error(exc.worker_code)
            if exc.worker_code == "join_failed":
                code = "pipeline_error"
            if exc.worker_code == "invalid_url":
                code = "invalid_url"
            if exc.worker_code == "queue_full":
                code = "queue_full"
            _fail_task(db, task, code)
            db.commit()
            return

        worker_status = str(body.get("status") or "")
        worker_meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
        worker_task_id = str(worker_meta.get("task_id") or "")
        if not worker_task_id:
            _fail_task(db, task, "pipeline_error")
            db.commit()
            return

        task.worker_task_id = worker_task_id
        if worker_status == "error":
            _fail_task(db, task, map_capture_worker_error(_worker_error_code(body)))
            db.commit()
            return

        _update_task_meta(
            db,
            task,
            "capturing",
            {
                "worker_capture_status": worker_status,
                "meeting_host": worker_meta.get("meeting_host") or meta.get("meeting_host"),
                "meeting_room": worker_meta.get("meeting_room") or meta.get("meeting_room"),
            },
        )
        db.commit()

        while True:
            if is_capture_canceled(task_id):
                await delete_capture_task(db, worker_node, worker_task_id)
                _fail_task(db, task, "canceled")
                db.commit()
                return

            if task_id in _stop_requested and worker_task_id:
                _stop_requested.discard(task_id)
                try:
                    await stop_capture_task(db, worker_node, worker_task_id)
                except WorkerClientError:
                    log.warning("capture stop request failed task=%s", task_id)
                _update_task_meta(db, task, "finalizing")
                db.commit()

            status_code, poll = await get_capture_task(db, worker_node, worker_task_id)
            if status_code == 404:
                _fail_task(db, task, "not_found")
                db.commit()
                return

            worker_status = str(poll.get("status") or "")
            _update_task_meta(db, task, worker_status if worker_status else "capturing", {"worker_capture_status": worker_status})
            db.commit()

            if worker_status == "success":
                break
            if worker_status == "error":
                _fail_task(db, task, map_capture_worker_error(_worker_error_code(poll)))
                db.commit()
                return
            if worker_status == "canceled":
                _fail_task(db, task, "canceled")
                db.commit()
                return

            await asyncio.sleep(_POLL_SEC)

        _update_task_meta(db, task, "downloading")
        db.commit()

        max_bytes = int(task.snap_max_upload_bytes)
        code, content, headers = await download_capture_artifact(db, worker_node, worker_task_id)
        if code != 200 or not content:
            _fail_task(db, task, "download_failed")
            db.commit()
            return

        filename_default = _filename_from_headers(headers, "capture.mp3")
        suffix, filename = resolve_capture_artifact(
            content,
            headers,
            filename_from_disposition=filename_default,
        )

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        duration_sec = None
        poll_meta = poll.get("meta") if isinstance(poll.get("meta"), dict) else {}
        raw_duration = poll_meta.get("duration_sec")
        if isinstance(raw_duration, (int, float)):
            duration_sec = float(raw_duration)

        audio_id = new_id()
        storage = get_storage()
        db.commit()
        try:
            storage_path = await storage.save_file_path(
                audio_id, suffix, temp_path, max_bytes=max_bytes
            )
        except PayloadTooLarge:
            _fail_task(db, task, "payload_too_large")
            db.commit()
            return
        except InvalidAudioContent:
            _fail_task(db, task, "invalid_file")
            db.commit()
            return

        audio = Audio(
            id=audio_id,
            org_id=task.org_id,
            owner_user_id=task.user_id,
            storage_path=storage_path,
            original_filename=filename,
            source_url=meeting_url[:2048],
            duration_sec=duration_sec,
            created_at=utcnow(),
        )
        db.add(audio)
        task.audio_id = audio.id
        task.status = "success"
        task.error_code = None
        task.meta_json = {
            **meta,
            "stage": "done",
            "meeting_host": meta.get("meeting_host"),
            "meeting_room": meta.get("meeting_room"),
            "duration_sec": duration_sec,
        }
        task.updated_at = utcnow()
        from app.prometheus_metrics import observe_task_terminal
        from app.services.dispatcher import enqueue_transcribe_after_ingest

        observe_task_terminal(task)
        enqueue_transcribe_after_ingest(db, task)
        db.commit()
    except Exception as exc:
        log.exception("capture task failed task=%s", task_id)
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None:
            detail = str(exc).strip()
            if len(detail) > 500:
                detail = detail[:497] + "..."
            _fail_task(
                db,
                task,
                "pipeline_error",
                {"error_detail": detail} if detail else None,
            )
            db.commit()
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if worker_node is not None and worker_task_id:
            try:
                await delete_capture_task(db, worker_node, worker_task_id)
            except Exception:
                pass
        _active.discard(task_id)
        _cancelled.discard(task_id)
        _stop_requested.discard(task_id)
        _bg_threads.pop(task_id, None)
        db.close()


def _run_capture_thread(task_id: str) -> None:
    asyncio.run(_run_capture_task(task_id))


def maybe_start_capture(db: Session, task: Task) -> None:
    if task.type != "capture" or task.status != "queued":
        return
    if task.id in _active or task.id in _bg_threads:
        return
    if not capture_slots_available():
        task.meta_json = {**(task.meta_json or {}), "stage": "queued"}
        return

    _active.add(task.id)
    task.status = "running"
    task.meta_json = {**(task.meta_json or {}), "stage": "queued"}
    task.updated_at = utcnow()
    db.flush()
    db.commit()
    thread = threading.Thread(
        target=_run_capture_thread,
        args=(task.id,),
        name=f"capture-{task.id[:8]}",
        daemon=True,
    )
    _bg_threads[task.id] = thread
    thread.start()


def wait_capture_tasks(timeout_sec: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        threads = [thread for thread in _bg_threads.values() if thread.is_alive()]
        if not threads:
            return
        for thread in threads:
            thread.join(timeout=0.05)


def reset_capture_runner() -> None:
    wait_capture_tasks(timeout_sec=5.0)
    _active.clear()
    _cancelled.clear()
    _stop_requested.clear()
    _bg_threads.clear()

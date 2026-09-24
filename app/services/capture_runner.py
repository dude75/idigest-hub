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

from app.models import Audio, Organization, Task, WorkerNode, new_id
from app.services.capture_workers import (
    delete_capture_task,
    download_capture_artifact,
    get_capture_task,
    map_capture_worker_error,
    post_capture,
    stop_capture_task,
)
from app.services.storage import PayloadTooLarge, get_storage
from app.services.upload_validation import (
    InvalidAudioContent,
    MIN_CAPTURE_ARTIFACT_BYTES,
    resolve_capture_artifact,
    validate_capture_download,
)
from app.services.workers import WorkerClientError
from app.timeutil import utcnow

log = logging.getLogger("app")

_POLL_SEC = 1.5
_CAPTURE_ACTIVE_WORKER_STATUSES = frozenset(
    {"queued", "running", "capturing", "finalizing", "joining"},
)
_CAPTURE_STOP_FORWARD_STATUSES = frozenset({"queued", "running", "capturing", "joining"})
_FINALIZING_STUCK_SEC = 900.0

_active: set[str] = set()
_cancelled: set[str] = set()
_stop_requested: set[str] = set()
_bg_threads: dict[str, threading.Thread] = {}
_start_lock = threading.Lock()
_persist_locks_guard = threading.Lock()
_persist_locks: dict[str, threading.Lock] = {}
_DISPATCHED_CAPTURE_STAGES = frozenset({"joining", "capturing", "finalizing", "downloading"})


def is_capture_canceled(task_id: str) -> bool:
    return task_id in _cancelled


def request_capture_cancel(task_id: str) -> None:
    _cancelled.add(task_id)


def request_capture_stop(task_id: str) -> None:
    _stop_requested.add(task_id)


def capture_stop_pending(task_id: str, task: Task) -> bool:
    if task_id in _stop_requested:
        return True
    meta = task.meta_json if isinstance(task.meta_json, dict) else {}
    return meta.get("stop_requested") is True


def mark_capture_stop_requested(db: Session, task: Task) -> None:
    request_capture_stop(task.id)
    meta = dict(task.meta_json or {})
    meta["stop_requested"] = True
    stage = str(meta.get("stage") or "")
    if stage not in {"downloading", "done"}:
        meta["stage"] = "finalizing"
    task.meta_json = meta
    task.updated_at = utcnow()
    db.flush()


async def forward_capture_stop(db: Session, task: Task) -> None:
    worker_task_id = (task.worker_task_id or "").strip()
    if not worker_task_id or not task.worker_id:
        return
    node = db.get(WorkerNode, task.worker_id)
    if node is None:
        return
    try:
        await stop_capture_task(db, node, worker_task_id)
    except WorkerClientError:
        log.warning("capture worker stop failed hub_task=%s worker_task=%s", task.id, worker_task_id)


async def forward_capture_cancel(db: Session, task: Task) -> None:
    worker_task_id = (task.worker_task_id or "").strip()
    if not worker_task_id or not task.worker_id:
        return
    node = db.get(WorkerNode, task.worker_id)
    if node is None:
        return
    try:
        await delete_capture_task(db, node, worker_task_id)
    except Exception:
        log.warning("capture worker cancel failed hub_task=%s worker_task=%s", task.id, worker_task_id)


async def apply_capture_stop(db: Session, task: Task) -> None:
    mark_capture_stop_requested(db, task)
    await forward_capture_stop(db, task)


def is_capture_thread_running(task_id: str) -> bool:
    return _capture_thread_alive(task_id)


async def request_hub_capture_stop(db: Session, task: Task) -> bool:
    """Record stop; let the capture bg thread talk to the worker when it is running.

    Returns True when the hub should run a dispatcher tick (no bg thread to drive stop).
    """
    mark_capture_stop_requested(db, task)
    if is_capture_thread_running(task.id):
        return False
    await forward_capture_stop(db, task)
    return True


async def request_hub_capture_cancel(db: Session, task: Task) -> bool:
    """Record cancel; delegate worker DELETE to the bg thread when it is running."""
    request_capture_cancel(task.id)
    if is_capture_thread_running(task.id):
        return False
    await forward_capture_cancel(db, task)
    return True


def should_schedule_capture_task_tick(task: Task) -> bool:
    """Skip dispatcher ticks while a healthy capture thread owns a running task."""
    if task.type != "capture" or task.status != "running":
        return True
    return not is_capture_thread_running(task.id)


async def run_capture_worker_cancel(hub_task_id: str) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        task = db.get(Task, hub_task_id)
        if task is not None:
            await forward_capture_cancel(db, task)
    finally:
        db.close()


def _capture_worker_held_by_other(db: Session, worker_id: str, exclude_task_id: str) -> bool:
    """One in-flight capture per worker node (same model as transcribe/summarize dispatch)."""
    from sqlalchemy import select

    running = db.scalars(
        select(Task).where(
            Task.type == "capture",
            Task.worker_id == worker_id,
            Task.id != exclude_task_id,
            Task.status == "running",
        )
    ).first()
    if running is not None:
        return True
    for task_id in _active:
        if task_id == exclude_task_id:
            continue
        other = db.get(Task, task_id)
        if other is not None and other.worker_id == worker_id:
            return True
    for task_id, thread in _bg_threads.items():
        if task_id == exclude_task_id or not thread.is_alive():
            continue
        other = db.get(Task, task_id)
        if other is not None and other.worker_id == worker_id:
            return True
    return False


def capture_worker_capacity_available(db: Session, task: Task) -> bool:
    """Gate capture start: dispatch-ready node and free workers.available (or legacy one job per node)."""
    worker_id = (task.worker_id or "").strip()
    if not worker_id:
        return False
    node = db.get(WorkerNode, worker_id)
    if node is None:
        return False
    from app.deps import get_instance_settings
    from app.services.capture_platforms import allowed_connectors
    from app.services.worker_availability import (
        parse_health_worker_pool,
        worker_is_dispatch_available,
        worker_node_has_pool_capacity,
    )

    settings = get_instance_settings(db)
    connectors = allowed_connectors(settings)
    if not worker_is_dispatch_available(node, capture_connectors=connectors):
        return False
    if parse_health_worker_pool(node.last_health) is not None:
        return worker_node_has_pool_capacity(node)
    return not _capture_worker_held_by_other(db, worker_id, task.id)


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


def _capture_already_dispatched(task: Task) -> bool:
    meta = task.meta_json if isinstance(task.meta_json, dict) else {}
    stage = str(meta.get("stage") or "")
    if stage in _DISPATCHED_CAPTURE_STAGES:
        return True
    return bool(meta.get("worker_capture_status"))


def _lose_capture_worker_link(db: Session, task: Task, *, reason: str) -> None:
    if _capture_already_dispatched(task):
        _fail_task(
            db,
            task,
            "pipeline_error",
            {"error_detail": f"capture worker link lost ({reason})"},
        )
        log.warning("capture task=%s lost worker link (%s)", task.id, reason)
        return
    _requeue_capture_task(db, task, reason=reason)


def _requeue_capture_task(db: Session, task: Task, *, reason: str) -> None:
    task.status = "queued"
    meta = dict(task.meta_json or {})
    meta["stage"] = "queued"
    task.meta_json = meta
    task.worker_id = None
    task.worker_task_id = None
    task.updated_at = utcnow()
    log.info("recover capture task=%s running->queued (%s)", task.id, reason)


def _hub_stage_for_worker_status(worker_status: str, *, artifact_ready: bool = False) -> str:
    if worker_status == "success":
        return "downloading" if artifact_ready else "finalizing"
    if worker_status in _DISPATCHED_CAPTURE_STAGES:
        return worker_status
    if worker_status in _CAPTURE_ACTIVE_WORKER_STATUSES:
        return "capturing"
    return "capturing"


def _persist_lock(task_id: str) -> threading.Lock:
    with _persist_locks_guard:
        return _persist_locks.setdefault(task_id, threading.Lock())


def _artifact_ready_in_poll(poll: dict[str, Any]) -> bool:
    status = str(poll.get("status") or "")
    if status != "success":
        return False
    artifact = poll.get("artifact")
    if not isinstance(artifact, dict):
        return True
    if artifact.get("ready") is False:
        return False
    size = artifact.get("size_bytes")
    if isinstance(size, int) and 0 < size < MIN_CAPTURE_ARTIFACT_BYTES:
        return False
    return True


async def _persist_capture_artifact(
    db: Session,
    task: Task,
    worker_node: WorkerNode,
    worker_task_id: str,
    poll: dict[str, Any],
) -> bool:
    with _persist_lock(task.id):
        return await _persist_capture_artifact_locked(
            db, task, worker_node, worker_task_id, poll
        )


async def _persist_capture_artifact_locked(
    db: Session,
    task: Task,
    worker_node: WorkerNode,
    worker_task_id: str,
    poll: dict[str, Any],
) -> bool:
    db.refresh(task)
    if task.audio_id:
        return task.status == "success"
    if task.status != "running":
        return False

    meta = dict(task.meta_json or {})
    meeting_url = str(meta.get("meeting_url") or "").strip()
    if not meeting_url:
        _fail_task(db, task, "invalid_url")
        db.commit()
        return False

    _update_task_meta(db, task, "downloading", {"worker_capture_status": "success"})
    db.commit()

    temp_path: Path | None = None
    try:
        max_bytes = int(task.snap_max_upload_bytes)
        code, content, headers = await download_capture_artifact(db, worker_node, worker_task_id)
        if code != 200 or not content:
            _fail_task(db, task, "download_failed")
            db.commit()
            return False
        try:
            from app.services.upload_validation import validate_capture_artifact_against_poll

            validate_capture_download(content, headers)
            validate_capture_artifact_against_poll(content, poll)
        except InvalidAudioContent:
            _fail_task(db, task, "invalid_file")
            db.commit()
            return False

        filename_default = _filename_from_headers(headers, "capture.mp3")
        suffix, _ = resolve_capture_artifact(
            content,
            headers,
            filename_from_disposition=filename_default,
        )
        from app.services.capture_meeting import capture_storage_filename

        filename = capture_storage_filename(meta, suffix)

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        duration_sec = None
        poll_meta = poll.get("meta") if isinstance(poll.get("meta"), dict) else {}
        raw_duration = poll_meta.get("duration_sec")
        if isinstance(raw_duration, (int, float)):
            duration_sec = float(raw_duration)

        db.refresh(task)
        if task.audio_id:
            return task.status == "success"
        if task.status != "running":
            return False

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
            return False
        except InvalidAudioContent:
            _fail_task(db, task, "invalid_file")
            db.commit()
            return False

        if not storage.exists(storage_path):
            _fail_task(db, task, "download_failed", {"error_detail": "storage write missing"})
            db.commit()
            return False

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
            "worker_capture_status": "success",
        }
        task.updated_at = utcnow()
        from app.prometheus_metrics import observe_task_terminal
        from app.services.dispatcher import enqueue_transcribe_after_ingest

        observe_task_terminal(task)
        follow_up = enqueue_transcribe_after_ingest(db, task)
        db.commit()
        log.info(
            "capture persisted hub_task=%s audio_id=%s bytes=%s duration_sec=%s follow_up=%s",
            task.id,
            audio.id,
            len(content),
            duration_sec,
            follow_up.id if follow_up else None,
        )
        return True
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


async def try_finish_capture_task(db: Session, task: Task) -> None:
    """Download capture artifact when the worker is already success (e.g. hub thread lost)."""
    if task.type != "capture" or task.status != "running" or task.audio_id:
        return
    worker_task_id = (task.worker_task_id or "").strip()
    if not worker_task_id or not task.worker_id:
        return
    worker_node = db.get(WorkerNode, task.worker_id)
    if worker_node is None:
        return
    try:
        status_code, poll = await get_capture_task(db, worker_node, worker_task_id)
    except WorkerClientError:
        return
    if status_code != 200:
        return
    worker_status = str(poll.get("status") or "")
    if worker_status == "success" and _artifact_ready_in_poll(poll):
        await _persist_capture_artifact(db, task, worker_node, worker_task_id, poll)
        return
    if worker_status in _CAPTURE_ACTIVE_WORKER_STATUSES or worker_status == "success":
        ready = worker_status == "success" and _artifact_ready_in_poll(poll)
        _update_task_meta(
            db,
            task,
            _hub_stage_for_worker_status(worker_status, artifact_ready=ready),
            {"worker_capture_status": worker_status},
        )


async def _poll_until_capture_artifact(
    db: Session,
    node: WorkerNode,
    worker_task_id: str,
    *,
    attempts: int = 8,
) -> tuple[int, dict[str, Any]]:
    last_code = 0
    last_poll: dict[str, Any] = {}
    for attempt in range(attempts):
        last_code, last_poll = await get_capture_task(db, node, worker_task_id)
        if last_code != 200:
            return last_code, last_poll
        status = str(last_poll.get("status") or "")
        if status in {"error", "canceled"}:
            return last_code, last_poll
        if status == "success" and _artifact_ready_in_poll(last_poll):
            return last_code, last_poll
        await asyncio.sleep(0.5 if attempt < 3 else _POLL_SEC)
    return last_code, last_poll


async def recover_capture_task(db: Session, task: Task, nodes: list[WorkerNode]) -> None:
    """Reattach hub capture tasks to icapture-worker after process restart."""
    if task.type != "capture" or task.status != "running":
        return

    worker_task_id = (task.worker_task_id or "").strip()
    if not worker_task_id or not task.worker_id:
        _lose_capture_worker_link(db, task, reason="no worker_task_id")
        return

    node = next((n for n in nodes if n.id == task.worker_id), None)
    if node is None:
        _lose_capture_worker_link(db, task, reason="worker node missing")
        return

    try:
        status_code, poll = await get_capture_task(db, node, worker_task_id)
    except WorkerClientError:
        log.info("recover capture task=%s keep running (worker unreachable)", task.id)
        return

    if status_code == 404:
        _lose_capture_worker_link(db, task, reason="worker 404")
        return
    if status_code >= 500:
        log.info("recover capture task=%s keep running (worker http %s)", task.id, status_code)
        return

    worker_status = str(poll.get("status") or "")
    if worker_status == "error":
        _fail_task(db, task, map_capture_worker_error(_worker_error_code(poll)))
        return
    if worker_status == "canceled":
        _fail_task(db, task, "canceled")
        return
    if worker_status == "success" or worker_status in _CAPTURE_ACTIVE_WORKER_STATUSES or worker_status:
        ready = worker_status == "success" and _artifact_ready_in_poll(poll)
        _update_task_meta(
            db,
            task,
            _hub_stage_for_worker_status(worker_status, artifact_ready=ready),
            {"worker_capture_status": worker_status},
        )
    else:
        _lose_capture_worker_link(db, task, reason=f"unknown worker status {worker_status!r}")
        return

    if capture_stop_pending(task.id, task) and worker_status != "success":
        await forward_capture_stop(db, task)
        _update_task_meta(db, task, "finalizing", {"worker_capture_status": "finalizing"})


def _capture_thread_alive(task_id: str) -> bool:
    thread = _bg_threads.get(task_id)
    return thread is not None and thread.is_alive()


def _spawn_capture_thread(task_id: str) -> None:
    thread = threading.Thread(
        target=_run_capture_thread,
        args=(task_id,),
        name=f"capture-{task_id[:8]}",
        daemon=True,
    )
    _bg_threads[task_id] = thread
    thread.start()


def _fail_capture_meeting_error(db: Session, task: Task, exc: Any) -> None:
    from app.services.capture_meeting import CaptureMeetingError, normalize_host
    from app.services.import_platforms import host_from_url

    if not isinstance(exc, CaptureMeetingError):
        _fail_task(db, task, "pipeline_error")
        return
    code = exc.code
    if code == "capture_disabled":
        fail_code = "capture_disabled"
    elif code == "invalid_url":
        fail_code = "invalid_url"
    elif code == "meeting_host_not_configured":
        fail_code = "meeting_host_not_configured"
    else:
        fail_code = "pipeline_error"
    meta: dict[str, Any] | None = None
    if fail_code == "meeting_host_not_configured":
        meeting_url = str((task.meta_json or {}).get("meeting_url") or "")
        host = normalize_host(host_from_url(meeting_url))
        if host:
            meta = {"meeting_host": host}
    _fail_task(db, task, fail_code, meta)


def _bind_capture_worker(db: Session, task: Task, settings: Any) -> WorkerNode | None:
    """Resolve org host map → capture worker (also after retry/requeue cleared worker_id)."""
    meta = dict(task.meta_json or {})
    meeting_url = str(meta.get("meeting_url") or "").strip()
    if not meeting_url:
        _fail_task(db, task, "invalid_url")
        return None

    if task.worker_id:
        node = db.get(WorkerNode, task.worker_id)
        if node is not None and node.type == "capture" and node.enabled:
            return node

    org = db.get(Organization, task.org_id)
    if org is None:
        _fail_task(db, task, "not_found")
        return None

    from app.services.capture_meeting import CaptureMeetingError, org_capture_bot_display_name, resolve_capture_target
    from app.services.capture_platforms import allowed_connectors

    display_name = str(meta.get("display_name") or org_capture_bot_display_name(org))
    pin = str(meta.get("pin") or "")
    try:
        target = resolve_capture_target(
            db,
            org=org,
            meeting_url=meeting_url,
            pin=pin,
            settings_allowed=allowed_connectors(settings),
            display_name=display_name,
        )
    except CaptureMeetingError as exc:
        _fail_capture_meeting_error(db, task, exc)
        return None

    task.worker_id = target.worker.id
    meta["meeting_host"] = target.meeting_host
    meta["meeting_room"] = target.meeting_room
    meta["connector"] = target.connector
    meta["display_name"] = display_name
    if target.jwt:
        meta["jwt"] = target.jwt
    task.meta_json = meta
    db.flush()
    return target.worker


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
    task: Task | None = None
    try:
        task = db.get(Task, task_id)
        if task is None or task.type != "capture":
            return
        if task.status != "running" or task.audio_id:
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

        worker_node = _bind_capture_worker(db, task, settings)
        if worker_node is None:
            db.commit()
            return

        meta = dict(task.meta_json or {})
        meeting_url = str(meta.get("meeting_url") or "").strip()
        pin = str(meta.get("pin") or "")
        jwt = meta.get("jwt")
        jwt_str = jwt if isinstance(jwt, str) and jwt.strip() else None
        connector = str(meta.get("connector") or "jitsi")
        from app.services.capture_meeting import DEFAULT_CAPTURE_BOT_DISPLAY_NAME

        display_name = str(meta.get("display_name") or DEFAULT_CAPTURE_BOT_DISPLAY_NAME)

        worker_task_id = (task.worker_task_id or "").strip() or None
        resuming = worker_task_id is not None

        if not resuming:
            _update_task_meta(db, task, "joining")
            db.commit()

            if is_capture_canceled(task_id):
                _fail_task(db, task, "canceled")
                db.commit()
                return

            log.info(
                "capture dispatch hub_task=%s worker_id=%s base_url=%s host=%s room=%s",
                task.id,
                worker_node.id,
                worker_node.base_url,
                meta.get("meeting_host"),
                meta.get("meeting_room"),
            )
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
            db.commit()
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
        else:
            log.info("capture resume hub_task=%s worker_task=%s", task_id, worker_task_id)
            db.commit()

        if capture_stop_pending(task_id, task) and worker_task_id:
            await forward_capture_stop(db, task)
            _update_task_meta(db, task, "finalizing")
            db.commit()

        while True:
            db.refresh(task)
            if is_capture_canceled(task_id):
                await forward_capture_cancel(db, task)
                _fail_task(db, task, "canceled")
                db.commit()
                return

            status_code, poll = await get_capture_task(db, worker_node, worker_task_id)
            if status_code == 404:
                _fail_task(db, task, "not_found")
                db.commit()
                return

            worker_status = str(poll.get("status") or "")
            if (
                capture_stop_pending(task_id, task)
                and worker_task_id
                and worker_status in _CAPTURE_STOP_FORWARD_STATUSES
            ):
                await forward_capture_stop(db, task)
                worker_status = "finalizing"
            artifact_ready = worker_status == "success" and _artifact_ready_in_poll(poll)
            stage = _hub_stage_for_worker_status(worker_status, artifact_ready=artifact_ready)
            if capture_stop_pending(task_id, task) and stage in _CAPTURE_STOP_FORWARD_STATUSES:
                stage = "finalizing"
            meta = dict(task.meta_json or {})
            if worker_status == "finalizing":
                meta.setdefault("finalizing_since", utcnow().isoformat())
            else:
                meta.pop("finalizing_since", None)
            meta["worker_capture_status"] = worker_status
            meta["stage"] = stage
            task.meta_json = meta
            task.updated_at = utcnow()
            db.flush()
            db.commit()

            if worker_status == "finalizing":
                since_raw = meta.get("finalizing_since")
                if isinstance(since_raw, str):
                    try:
                        from datetime import datetime

                        from app.timeutil import as_utc

                        since = as_utc(datetime.fromisoformat(since_raw.replace("Z", "+00:00")))
                        elapsed = (utcnow() - since).total_seconds()
                        if elapsed > _FINALIZING_STUCK_SEC:
                            _fail_task(db, task, "pipeline_error", {"error_detail": "capture finalize timeout"})
                            db.commit()
                            return
                    except ValueError:
                        pass

            if worker_status == "success":
                if not _artifact_ready_in_poll(poll):
                    await asyncio.sleep(_POLL_SEC)
                    continue
                meta = dict(task.meta_json or {})
                meta.pop("stop_requested", None)
                meta.pop("finalizing_since", None)
                task.meta_json = meta
                db.flush()
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

        db.refresh(task)
        if task.audio_id or task.status != "running":
            return

        if not _artifact_ready_in_poll(poll) or str(poll.get("status") or "") != "success":
            status_code, poll = await _poll_until_capture_artifact(db, worker_node, worker_task_id)
            if status_code == 404:
                _fail_task(db, task, "not_found")
                db.commit()
                return
            worker_status = str(poll.get("status") or "")
            if worker_status == "error":
                _fail_task(db, task, map_capture_worker_error(_worker_error_code(poll)))
                db.commit()
                return
            if worker_status == "canceled":
                _fail_task(db, task, "canceled")
                db.commit()
                return
            if worker_status != "success" or not _artifact_ready_in_poll(poll):
                _fail_task(db, task, "download_failed", {"error_detail": "capture artifact not ready"})
                db.commit()
                return

        await _persist_capture_artifact(db, task, worker_node, worker_task_id, poll)
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
            terminal = db.get(Task, task_id)
            if terminal is not None and (terminal.status == "success" or is_capture_canceled(task_id)):
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
    if task.type != "capture":
        return
    if task.status not in {"queued", "running"}:
        return
    if task.audio_id:
        return
    with _start_lock:
        if _capture_thread_alive(task.id):
            return
        _active.discard(task.id)
        _bg_threads.pop(task.id, None)
        if not capture_worker_capacity_available(db, task):
            meta = dict(task.meta_json or {})
            meta["stage"] = "queue_full"
            task.meta_json = meta
            task.updated_at = utcnow()
            db.flush()
            return

        _active.add(task.id)
        if task.status == "queued":
            task.status = "running"
            task.meta_json = {**(task.meta_json or {}), "stage": "queued"}
            task.updated_at = utcnow()
            db.flush()
        db.commit()
        _spawn_capture_thread(task.id)


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
    with _persist_locks_guard:
        _persist_locks.clear()

"""Очередь хаба: dispatch, poll, 404-redispatch, таймаут пустого пула (ТЗ §5–6)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import MAX_SUMMARIZE_PAYLOAD_BYTES
from app.crypto import encrypt_str
from app.models import Audio, Organization, Skill, Summary, Task, Transcript, WorkerNode, new_id
from app.services.billing import apply_success_charge, summarize_amount, transcribe_amount
from app.services.workers import (
    WorkerClientError,
    delete_task,
    get_health,
    get_ready,
    get_task,
    map_worker_error,
    post_summarize,
    post_transcribe,
)
from app.timeutil import as_utc, utcnow

log = logging.getLogger("app")


def utterances_to_text(utterances: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in utterances:
        speaker = item.get("speaker")
        text = str(item.get("text") or "")
        if speaker:
            lines.append(f"{speaker}: {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def combine_skills(skills: list[Skill]) -> str:
    parts = [f"## {skill.name}\n\n{skill.body.strip()}" for skill in skills]
    return "\n\n".join(parts)


async def refresh_node_health(db: Session, node: WorkerNode) -> None:
    try:
        status, body = await get_health(node)
        ready_code = None
        if node.type == "summarize":
            ready_code = await get_ready(node)
        payload = dict(body)
        payload["_http"] = status
        if ready_code is not None:
            payload["_ready_http"] = ready_code
        node.last_health = payload
        node.last_seen_version = body.get("version") if status == 200 else node.last_seen_version
        node.last_health_at = utcnow()
        node.updated_at = utcnow()
    except Exception:
        node.last_health = {"_http": 0, "status": "unreachable"}
        node.last_health_at = utcnow()
        log.info("worker health failed node=%s", node.id)


def _engines(node: WorkerNode) -> dict[str, str]:
    health = node.last_health or {}
    engines = health.get("engines") or {}
    return engines if isinstance(engines, dict) else {}


def transcribe_pool_state(nodes: list[WorkerNode], asr: str, diar: str | None) -> str:
    """empty | waiting | ready. waiting = enabled nodes exist but engines unavailable (no timeout)."""
    enabled = [n for n in nodes if n.enabled and n.type == "transcribe"]
    if not enabled:
        return "empty"
    ready: list[WorkerNode] = []
    waiting = False
    for node in enabled:
        health = node.last_health or {}
        if health.get("_http") != 200:
            waiting = True
            continue
        engines = _engines(node)
        asr_st = engines.get(asr, "disabled")
        diar_st = engines.get(diar, "loaded") if diar else "loaded"
        if asr_st == "loaded" and diar_st == "loaded":
            ready.append(node)
            continue
        if asr_st == "unavailable" or (diar and diar_st == "unavailable"):
            waiting = True
    if ready:
        return "ready"
    if waiting:
        return "waiting"
    return "empty"


def summarize_pool_state(nodes: list[WorkerNode]) -> str:
    enabled = [n for n in nodes if n.enabled and n.type == "summarize"]
    if not enabled:
        return "empty"
    for node in enabled:
        health = node.last_health or {}
        if health.get("_ready_http") == 200:
            return "ready"
    return "empty"


def transcribe_candidates(nodes: list[WorkerNode], asr: str, diar: str | None) -> list[WorkerNode]:
    out: list[WorkerNode] = []
    for node in nodes:
        if not node.enabled or node.type != "transcribe":
            continue
        engines = _engines(node)
        asr_st = engines.get(asr, "disabled")
        diar_st = engines.get(diar, "loaded") if diar else "loaded"
        if asr_st == "loaded" and diar_st == "loaded":
            out.append(node)
    return out


def summarize_candidates(nodes: list[WorkerNode]) -> list[WorkerNode]:
    out: list[WorkerNode] = []
    for node in nodes:
        if not node.enabled or node.type != "summarize":
            continue
        health = node.last_health or {}
        if health.get("_ready_http") == 200:
            out.append(node)
    return out


def pick_node(db: Session, candidates: list[WorkerNode]) -> WorkerNode | None:
    if not candidates:
        return None

    def score(node: WorkerNode) -> tuple[float, int]:
        in_flight = len(
            db.scalars(
                select(Task).where(
                    Task.worker_id == node.id,
                    Task.status.in_(("queued", "running")),
                    Task.worker_task_id.is_not(None),
                )
            ).all()
        )
        weight = max(node.weight, 1)
        return (in_flight / weight, -weight)

    return sorted(candidates, key=score)[0]


def _fail(task: Task, code: str) -> None:
    task.status = "error"
    task.error_code = code
    task.updated_at = utcnow()
    task.worker_id = None
    task.worker_task_id = None
    from app.prometheus_metrics import observe_task_terminal

    observe_task_terminal(task)


def _maybe_timeout(task: Task, pool: str, timeout_sec: int) -> bool:
    if task.retry_without_timeout or pool != "empty" or timeout_sec <= 0:
        return False
    elapsed = (utcnow() - as_utc(task.queued_at)).total_seconds()
    if elapsed >= timeout_sec:
        _fail(task, "dispatch_timeout")
        return True
    return False


def _commit(db: Session) -> None:
    db.flush()
    db.commit()


async def _finish_worker_cleanup(node: WorkerNode | None, worker_task_id: str | None) -> None:
    if node is not None and worker_task_id:
        await delete_task(node, worker_task_id)


def _persist_transcript(db: Session, task: Task, utterances: list[dict[str, Any]]) -> Transcript | None:
    if task.skip_persist:
        _fail(task, task.skip_reason or "source_deleted")
        return None
    row = Transcript(
        id=new_id(),
        org_id=task.org_id,
        owner_user_id=task.user_id,
        source_audio_id=task.audio_id,
        utterances_encrypted=encrypt_str(json.dumps(utterances, ensure_ascii=False)),
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    task.produced_transcript_id = row.id
    task.status = "success"
    task.error_code = None
    task.updated_at = utcnow()
    from app.prometheus_metrics import observe_task_terminal

    observe_task_terminal(task)
    return row


def _persist_summary(db: Session, task: Task, body: str) -> Summary | None:
    if task.skip_persist:
        _fail(task, task.skip_reason or "source_deleted")
        return None
    row = Summary(
        id=new_id(),
        org_id=task.org_id,
        owner_user_id=task.user_id,
        source_transcript_id=task.transcript_id,
        skill_ids_json=list(task.skill_ids_json or []),
        body_encrypted=encrypt_str(body),
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    task.produced_summary_id = row.id
    task.status = "success"
    task.error_code = None
    task.updated_at = utcnow()
    from app.prometheus_metrics import observe_task_terminal

    observe_task_terminal(task)
    return row


def _charge(
    db: Session, task: Task, audio_sec: float | None, amount: Decimal, *, summary_chars: int | None = None
) -> None:
    org = db.get(Organization, task.org_id)
    if org is None:
        return
    apply_success_charge(db, task, org, audio_sec=audio_sec, amount=amount, summary_chars=summary_chars)


async def _on_transcribe_success(
    db: Session, task: Task, node: WorkerNode, body: dict[str, Any]
) -> None:
    utterances = body.get("transcript") or []
    if not isinstance(utterances, list):
        utterances = []
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    duration = meta.get("audio_duration_sec")
    audio_sec = float(duration) if duration is not None else 0.0
    if task.audio_id and audio_sec:
        audio = db.get(Audio, task.audio_id)
        if audio is not None and audio.duration_sec is None:
            audio.duration_sec = audio_sec
    amount = transcribe_amount(task, audio_sec)
    worker_task_id = task.worker_task_id
    _persist_transcript(db, task, utterances)
    _charge(db, task, audio_sec, amount)
    task.meta_json = {"stage": "done", **{k: meta.get(k) for k in ("audio_duration_sec", "asr_model")}}
    task.worker_task_id = None
    task.worker_id = None
    _commit(db)
    await _finish_worker_cleanup(node, worker_task_id)


async def _on_summarize_success(
    db: Session, task: Task, node: WorkerNode, body: dict[str, Any]
) -> None:
    summary = body.get("summary")
    text = summary if isinstance(summary, str) else ""
    amount = summarize_amount(task, text)
    worker_task_id = task.worker_task_id
    _persist_summary(db, task, text)
    _charge(db, task, None, amount, summary_chars=len(text))
    task.meta_json = {"stage": "done"}
    task.worker_task_id = None
    task.worker_id = None
    _commit(db)
    await _finish_worker_cleanup(node, worker_task_id)


async def _on_worker_terminal_error(
    db: Session, task: Task, node: WorkerNode, body: dict[str, Any]
) -> None:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = map_worker_error(err.get("code") if isinstance(err, dict) else None)
    worker_task_id = task.worker_task_id
    _fail(task, code)
    _commit(db)
    await _finish_worker_cleanup(node, worker_task_id)


async def poll_running_task(db: Session, task: Task, nodes: list[WorkerNode]) -> None:
    node = next((n for n in nodes if n.id == task.worker_id), None)
    if node is None or not task.worker_task_id:
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        return
    try:
        status_code, body = await get_task(node, task.worker_task_id)
    except WorkerClientError:
        log.info("worker poll network error task=%s", task.id)
        return
    if status_code == 404:
        if task.status == "success" or task.produced_transcript_id or task.produced_summary_id:
            task.worker_id = None
            task.worker_task_id = None
            return
        log.info("worker 404 redispatch task=%s", task.id)
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        return
    if status_code >= 500:
        return
    worker_status = body.get("status")
    if worker_status == "success":
        if task.type == "transcribe":
            await _on_transcribe_success(db, task, node, body)
        else:
            await _on_summarize_success(db, task, node, body)
        return
    if worker_status == "error":
        await _on_worker_terminal_error(db, task, node, body)
        return
    if worker_status in {"queued", "running"}:
        task.status = "running"
        task.meta_json = {"stage": worker_status}
        task.updated_at = utcnow()


async def dispatch_queued_task(db: Session, task: Task, nodes: list[WorkerNode], timeout_sec: int) -> None:
    if task.type == "import":
        return
    if task.type == "transcribe":
        pool = transcribe_pool_state(nodes, task.snap_asr_model or "whisper", task.snap_diarization_model)
        candidates = transcribe_candidates(
            nodes, task.snap_asr_model or "whisper", task.snap_diarization_model
        )
    else:
        pool = summarize_pool_state(nodes)
        candidates = summarize_candidates(nodes)
    if pool == "waiting":
        task.retry_without_timeout = True
        task.meta_json = {"stage": "waiting_engine"}
        return
    if _maybe_timeout(task, pool, timeout_sec):
        return
    if not candidates:
        task.meta_json = {"stage": "queued"}
        return

    tried_payload_too_large = 0
    remaining = list(candidates)
    while remaining:
        node = pick_node(db, remaining)
        if node is None:
            break
        remaining = [n for n in remaining if n.id != node.id]
        try:
            if task.type == "transcribe":
                audio = db.get(Audio, task.audio_id) if task.audio_id else None
                if audio is None:
                    _fail(task, "source_deleted")
                    return
                from app.services.storage import get_storage

                async with get_storage().local_path_for_worker(audio.storage_path) as audio_path:
                    body = await post_transcribe(
                        node,
                        audio_path,
                        audio.original_filename,
                        task.snap_asr_model or "whisper",
                        task.snap_diarization_model,
                    )
            else:
                transcript = db.get(Transcript, task.transcript_id) if task.transcript_id else None
                if transcript is None:
                    _fail(task, "source_deleted")
                    return
                from app.crypto import decrypt_str

                utterances = json.loads(decrypt_str(transcript.utterances_encrypted))
                text = utterances_to_text(utterances)
                skill_ids = list(task.skill_ids_json or [])
                skills: list[Skill] = []
                for sid in skill_ids:
                    skill = db.get(Skill, sid)
                    if skill is None:
                        _fail(task, "not_found")
                        return
                    skills.append(skill)
                skill_text = combine_skills(skills)
                payload_len = len(text.encode()) + len(skill_text.encode())
                if payload_len > MAX_SUMMARIZE_PAYLOAD_BYTES:
                    _fail(task, "text_too_long")
                    return
                body = await post_summarize(node, text, skill_text)
        except WorkerClientError as exc:
            if exc.kind == "queue_full":
                task.retry_without_timeout = True
                task.meta_json = {"stage": "queue_full"}
                continue
            if exc.kind == "payload_too_large":
                tried_payload_too_large += 1
                continue
            if exc.kind in {"timeout", "http"}:
                log.info("worker post network error task=%s", task.id)
                continue
            mapped = map_worker_error(exc.worker_code)
            if mapped == "engine_unavailable":
                task.retry_without_timeout = True
                continue
            _fail(task, mapped)
            return
        worker_task_id = body.get("meta", {}).get("task_id") if isinstance(body.get("meta"), dict) else None
        worker_task_id = worker_task_id or body.get("task_id")
        task.worker_id = node.id
        task.worker_task_id = str(worker_task_id) if worker_task_id else None
        task.status = "running"
        task.meta_json = {"stage": "dispatched"}
        task.updated_at = utcnow()
        worker_status = body.get("status")
        if worker_status == "success":
            if task.type == "transcribe":
                await _on_transcribe_success(db, task, node, body)
            else:
                await _on_summarize_success(db, task, node, body)
        elif worker_status == "error":
            await _on_worker_terminal_error(db, task, node, body)
        return
    if tried_payload_too_large and tried_payload_too_large >= len(candidates):
        _fail(task, "payload_too_large")


_tick_lock: asyncio.Lock | None = None


def tick_lock() -> asyncio.Lock:
    global _tick_lock
    if _tick_lock is None:
        _tick_lock = asyncio.Lock()
    return _tick_lock


async def tick_once(db: Session, task_id: str | None = None, *, refresh_health: bool = True) -> None:
    # Persist the caller's pending writes first so SQLite is not locked during worker HTTP.
    _commit(db)
    settings = get_settings()
    nodes = list(db.scalars(select(WorkerNode)).all())
    now = utcnow()
    if refresh_health:
        for node in nodes:
            if (
                node.last_health_at is not None
                and (now - as_utc(node.last_health_at)).total_seconds() < 5
            ):
                continue
            await refresh_node_health(db, node)
    _commit(db)
    query = select(Task).where(Task.status.in_(("queued", "running")))
    if task_id:
        query = query.where(Task.id == task_id)
    tasks = list(db.scalars(query).all())
    from app.services.import_runner import maybe_start_import

    for task in tasks:
        if task.type == "import":
            if task.status == "queued":
                maybe_start_import(db, task)
            continue
        if task.status == "running" and task.worker_task_id:
            await poll_running_task(db, task, nodes)
        if task.status == "queued":
            await dispatch_queued_task(db, task, nodes, settings.DISPATCH_NO_CANDIDATE_SEC)
        _commit(db)


async def locked_tick(db: Session, task_id: str | None = None) -> None:
    async with tick_lock():
        await tick_once(db, task_id=task_id)


async def dispatcher_loop(stop_event: asyncio.Event) -> None:
    from app.db import SessionLocal, get_engine
    from app.prometheus_metrics import (
        mark_dispatcher_started,
        mark_dispatcher_tick_success,
        observe_dispatcher_tick,
        observe_dispatcher_tick_error,
    )

    get_engine()
    assert SessionLocal is not None
    settings = get_settings()
    mark_dispatcher_started()
    while not stop_event.is_set():
        session = SessionLocal()
        tick_started = time.perf_counter()
        try:
            async with tick_lock():
                await tick_once(session)
                from app.services.retention import purge_expired_audio

                purge_expired_audio(session)
            session.commit()
            mark_dispatcher_tick_success()
            observe_dispatcher_tick(time.perf_counter() - tick_started)
        except Exception:
            session.rollback()
            observe_dispatcher_tick_error()
            log.exception("dispatcher tick failed")
        finally:
            session.close()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.DISPATCH_POLL_SEC)
        except TimeoutError:
            pass

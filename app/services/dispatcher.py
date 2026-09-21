"""Очередь хаба: dispatch, poll, 404-redispatch, таймаут пустого пула (ТЗ §5–6)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import MAX_SUMMARIZE_PAYLOAD_BYTES
from app.crypto import encrypt_str
from app.db import release_connection
from app.models import Audio, Organization, Skill, Summary, Task, Transcript, WorkerNode, new_id
from app.presenters import transcript_display_title
from app.services.billing import apply_success_charge, summarize_amount, transcribe_amount
from app.services.transcript_payload import (
    build_worker_payload,
    decode_transcript_payload,
    summarize_input_text,
)
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
_ERROR_DETAIL_MAX_LEN = 500

# Keep last successful health if a probe throws (busy worker, event-loop stall).
_HEALTH_FAIL_GRACE_SEC = 60


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


def _keep_last_good_health(node: WorkerNode) -> bool:
    health = node.last_health or {}
    last_at = node.last_health_at
    if health.get("_http") != 200 or last_at is None:
        return False
    return (utcnow() - as_utc(last_at)).total_seconds() < _HEALTH_FAIL_GRACE_SEC


async def _probe_node_health(node: WorkerNode) -> None:
    """HTTP only — does not touch the Session, safe to run concurrently."""
    try:
        status, body = await get_health(None, node)
        ready_code = None
        if node.type == "summarize":
            ready_code = await get_ready(None, node)
        payload = dict(body)
        payload["_http"] = status
        if ready_code is not None:
            payload["_ready_http"] = ready_code
        node.last_health = payload
        node.last_seen_version = body.get("version") if status == 200 else node.last_seen_version
        node.last_health_at = utcnow()
        node.updated_at = utcnow()
    except Exception as exc:
        log.info("worker health probe error node=%s error=%s", node.id, exc)
        if _keep_last_good_health(node):
            return
        node.last_health = {"_http": 0, "status": "unreachable"}
        node.last_health_at = utcnow()
        log.info("worker health failed node=%s", node.id)


async def refresh_node_health(db: Session, node: WorkerNode) -> None:
    release_connection(db)
    await _probe_node_health(node)


async def refresh_nodes_health(
    db: Session, nodes: list[WorkerNode], *, force: bool = False
) -> None:
    now = utcnow()
    stale = [
        node
        for node in nodes
        if force
        or node.last_health_at is None
        or (now - as_utc(node.last_health_at)).total_seconds() >= 5
    ]
    if not stale:
        return
    release_connection(db)
    await asyncio.gather(*(_probe_node_health(node) for node in stale))


def _engines(node: WorkerNode) -> dict[str, str]:
    health = node.last_health or {}
    engines = health.get("engines") or {}
    return engines if isinstance(engines, dict) else {}


def transcribe_pool_state(nodes: list[WorkerNode], asr: str, diar: str | None) -> str:
    """empty | waiting | ready. waiting = enabled nodes exist but engines unavailable (no timeout)."""
    from app.services.transcribe_models import worker_offers_model

    enabled = [n for n in nodes if n.enabled and n.type == "transcribe"]
    if not enabled:
        return "empty"
    offering = [n for n in enabled if worker_offers_model(n, asr=asr, diar=diar)]
    if not offering:
        return "empty"
    ready: list[WorkerNode] = []
    waiting = False
    for node in offering:
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
    from app.services.transcribe_models import worker_offers_model

    out: list[WorkerNode] = []
    for node in nodes:
        if not node.enabled or node.type != "transcribe":
            continue
        if not worker_offers_model(node, asr=asr, diar=diar):
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


def _worker_error_detail(body: dict[str, Any] | None) -> str | None:
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return None
    message = err.get("message")
    if not isinstance(message, str):
        return None
    text = " ".join(message.split())
    if not text:
        return None
    if len(text) <= _ERROR_DETAIL_MAX_LEN:
        return text
    return text[: _ERROR_DETAIL_MAX_LEN - 3] + "..."


def _fail(task: Task, code: str, *, error_detail: str | None = None) -> None:
    task.status = "error"
    task.error_code = code
    task.updated_at = utcnow()
    task.worker_id = None
    task.worker_task_id = None
    if error_detail:
        meta = dict(task.meta_json or {})
        meta["stage"] = "error"
        meta["error_detail"] = error_detail
        task.meta_json = meta
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


async def _finish_worker_cleanup(db: Session, node: WorkerNode | None, worker_task_id: str | None) -> None:
    if node is not None and worker_task_id:
        await delete_task(db, node, worker_task_id)


def _persist_transcript(db: Session, task: Task, payload: dict[str, Any]) -> Transcript | None:
    if task.skip_persist:
        _fail(task, task.skip_reason or "source_deleted")
        return None
    title: str | None = None
    if task.audio_id:
        audio = db.get(Audio, task.audio_id)
        if audio and audio.original_filename:
            title = Path(audio.original_filename).stem or None
    row = Transcript(
        id=new_id(),
        org_id=task.org_id,
        owner_user_id=task.user_id,
        source_audio_id=task.audio_id,
        title=title,
        utterances_encrypted=encrypt_str(json.dumps(payload, ensure_ascii=False), db),
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


def enqueue_transcribe_after_ingest(db: Session, ingest_task: Task) -> Task | None:
    if ingest_task.type not in {"import", "capture"} or ingest_task.status != "success" or not ingest_task.audio_id:
        return None
    meta = dict(ingest_task.meta_json or {})
    if meta.get("pipeline_transcribe") is not True:
        return None
    if meta.get("follow_up_task_id"):
        existing = db.get(Task, str(meta["follow_up_task_id"]))
        if existing is not None:
            return existing

    org = db.get(Organization, ingest_task.org_id)
    if org is None:
        return None
    tariff = org.tariff
    if not tariff.unlimited and org.balance <= 0:
        log.warning(
            "ingest pipeline transcribe skipped: insufficient balance task=%s",
            ingest_task.id,
        )
        return None

    skill_ids = list(ingest_task.skill_ids_json or [])
    now = utcnow()
    follow_up = Task(
        id=new_id(),
        type="transcribe",
        status="queued",
        org_id=ingest_task.org_id,
        user_id=ingest_task.user_id,
        audio_id=ingest_task.audio_id,
        skill_ids_json=skill_ids or None,
        queued_at=now,
        created_at=now,
        updated_at=now,
        snap_unlimited=ingest_task.snap_unlimited,
        snap_price_per_audio_sec=ingest_task.snap_price_per_audio_sec,
        snap_price_per_summarize_job=ingest_task.snap_price_per_summarize_job,
        snap_price_per_1k_summary_chars=ingest_task.snap_price_per_1k_summary_chars,
        snap_max_upload_bytes=ingest_task.snap_max_upload_bytes,
        snap_asr_model=ingest_task.snap_asr_model,
        snap_diarization_model=ingest_task.snap_diarization_model,
    )
    db.add(follow_up)
    db.flush()
    meta["follow_up_task_id"] = follow_up.id
    ingest_task.meta_json = meta
    return follow_up


def enqueue_transcribe_after_import(db: Session, import_task: Task) -> Task | None:
    return enqueue_transcribe_after_ingest(db, import_task)


def _enqueue_summarize_after_transcribe(db: Session, task: Task) -> Task | None:
    skill_ids = list(task.skill_ids_json or [])
    if not skill_ids or not task.produced_transcript_id:
        return None
    now = utcnow()
    follow_up = Task(
        id=new_id(),
        type="summarize",
        status="queued",
        org_id=task.org_id,
        user_id=task.user_id,
        transcript_id=task.produced_transcript_id,
        skill_ids_json=skill_ids,
        queued_at=now,
        created_at=now,
        updated_at=now,
        snap_unlimited=task.snap_unlimited,
        snap_price_per_audio_sec=task.snap_price_per_audio_sec,
        snap_price_per_summarize_job=task.snap_price_per_summarize_job,
        snap_price_per_1k_summary_chars=task.snap_price_per_1k_summary_chars,
        snap_max_upload_bytes=task.snap_max_upload_bytes,
        snap_asr_model=None,
        snap_diarization_model=None,
    )
    db.add(follow_up)
    db.flush()
    meta = dict(task.meta_json or {})
    meta["follow_up_task_id"] = follow_up.id
    task.meta_json = meta
    return follow_up


def _persist_summary(db: Session, task: Task, body: str) -> Summary | None:
    if task.skip_persist:
        _fail(task, task.skip_reason or "source_deleted")
        return None
    summary_id = new_id()
    transcript = db.get(Transcript, task.transcript_id) if task.transcript_id else None
    source_filename: str | None = None
    if transcript and transcript.source_audio_id:
        audio = db.get(Audio, transcript.source_audio_id)
        if audio:
            source_filename = audio.original_filename
    skill_ids = list(task.skill_ids_json or [])
    skill_names = [
        skill.name
        for sid in skill_ids
        if (skill := db.get(Skill, sid)) is not None
    ]
    if transcript:
        tr_name = transcript_display_title(transcript, source_filename=source_filename)
        if skill_names:
            title = f"{tr_name} · {', '.join(skill_names)}"
        else:
            title = f"{tr_name}-{summary_id[:8]}"
    else:
        title = ", ".join(skill_names) if skill_names else summary_id[:8]
    row = Summary(
        id=summary_id,
        org_id=task.org_id,
        owner_user_id=task.user_id,
        source_transcript_id=task.transcript_id,
        skill_ids_json=list(task.skill_ids_json or []),
        title=title,
        body_encrypted=encrypt_str(body, db),
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
    worker_meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    duration = worker_meta.get("audio_duration_sec")
    audio_sec = float(duration) if duration is not None else 0.0
    if task.audio_id and audio_sec:
        audio = db.get(Audio, task.audio_id)
        if audio is not None and audio.duration_sec is None:
            audio.duration_sec = audio_sec
    amount = transcribe_amount(task, audio_sec)
    worker_task_id = task.worker_task_id
    _persist_transcript(db, task, build_worker_payload(body, utterances))
    _charge(db, task, audio_sec, amount)
    follow_up = _enqueue_summarize_after_transcribe(db, task)
    meta = dict(task.meta_json or {})
    meta["stage"] = "done"
    for key in ("audio_duration_sec", "asr_model"):
        val = worker_meta.get(key)
        if val is not None:
            meta[key] = val
    task.meta_json = meta
    task.worker_task_id = None
    task.worker_id = None
    _commit(db)
    await _finish_worker_cleanup(db, node, worker_task_id)
    if follow_up is not None:
        await _dispatch_follow_up_task(db, follow_up.id)


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
    await _finish_worker_cleanup(db, node, worker_task_id)


async def _on_worker_terminal_error(
    db: Session, task: Task, node: WorkerNode, body: dict[str, Any]
) -> None:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = map_worker_error(err.get("code") if isinstance(err, dict) else None)
    detail = _worker_error_detail(body)
    worker_task_id = task.worker_task_id
    log.info("worker terminal error task=%s code=%s detail=%s", task.id, code, detail or "")
    _fail(task, code, error_detail=detail)
    _commit(db)
    await _finish_worker_cleanup(db, node, worker_task_id)


async def recover_orphaned_tasks(db: Session) -> None:
    """Reconcile running tasks after hub process restart."""
    nodes = list(db.scalars(select(WorkerNode)).all())
    await refresh_nodes_health(db, nodes, force=True)

    running = list(db.scalars(select(Task).where(Task.status == "running")).all())
    if not running:
        return

    log.info("recover orphaned tasks count=%d", len(running))
    for task in running:
        if task.type == "import":
            task.status = "queued"
            meta = dict(task.meta_json or {})
            meta["stage"] = "queued"
            task.meta_json = meta
            task.worker_id = None
            task.worker_task_id = None
            task.updated_at = utcnow()
            log.info("recover task=%s type=%s running->queued", task.id, task.type)
            continue
        if task.type == "capture":
            from app.services.capture_runner import recover_capture_task

            await recover_capture_task(db, task, nodes)
            continue
        await _recover_worker_task(db, task, nodes)

    _commit(db)


async def _recover_worker_task(db: Session, task: Task, nodes: list[WorkerNode]) -> None:
    if task.type not in {"transcribe", "summarize"}:
        return

    if not task.worker_task_id:
        task.worker_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        log.info("recover task=%s running->queued (no worker_task_id)", task.id)
        return

    node = next((n for n in nodes if n.id == task.worker_id), None)
    if node is None:
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        log.info("recover task=%s running->queued (worker node missing)", task.id)
        return

    try:
        status_code, body = await get_task(db, node, task.worker_task_id)
    except WorkerClientError:
        log.info("recover task=%s running->queued (worker unreachable)", task.id)
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        return

    if status_code == 404:
        if task.produced_transcript_id or task.produced_summary_id:
            task.worker_id = None
            task.worker_task_id = None
            return
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        log.info("recover task=%s running->queued (worker 404)", task.id)
        return

    if status_code >= 500:
        log.info("recover task=%s running->queued (worker http %s)", task.id, status_code)
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
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
        return

    log.info("recover task=%s running->queued (unknown worker status %s)", task.id, worker_status)
    task.worker_id = None
    task.worker_task_id = None
    task.status = "queued"
    task.updated_at = utcnow()


async def poll_running_task(db: Session, task: Task, nodes: list[WorkerNode]) -> None:
    node = next((n for n in nodes if n.id == task.worker_id), None)
    if node is None or not task.worker_task_id:
        task.worker_id = None
        task.worker_task_id = None
        task.status = "queued"
        task.updated_at = utcnow()
        return
    try:
        status_code, body = await get_task(db, node, task.worker_task_id)
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
        from app.services.transcribe_models import worker_offers_model

        asr = task.snap_asr_model or "whisper"
        diar = task.snap_diarization_model
        enabled = [n for n in nodes if n.enabled and n.type == "transcribe"]
        if enabled and not any(worker_offers_model(n, asr=asr, diar=diar) for n in enabled):
            task.meta_json = {
                "stage": "no_matching_worker",
                "asr_model": asr,
                "diarization_model": diar,
            }
        else:
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

                release_connection(db)
                async with get_storage().local_path_for_worker(audio.storage_path) as audio_path:
                    body = await post_transcribe(
                        db,
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

                payload = decode_transcript_payload(decrypt_str(transcript.utterances_encrypted, db))
                text = summarize_input_text(payload)
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
                body = await post_summarize(db, node, text, skill_text)
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
            detail = _worker_error_detail(exc.body)
            log.info("worker post error task=%s code=%s detail=%s", task.id, mapped, detail or "")
            _fail(task, mapped, error_detail=detail)
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


async def _dispatch_follow_up_task(db: Session, follow_up_id: str) -> None:
    """Dispatch a chained task without re-acquiring tick_lock (caller already holds it)."""
    follow_up = db.get(Task, follow_up_id)
    if follow_up is None or follow_up.status != "queued":
        return
    settings = get_settings()
    nodes = list(db.scalars(select(WorkerNode)).all())
    await dispatch_queued_task(db, follow_up, nodes, settings.DISPATCH_NO_CANDIDATE_SEC)


_tick_lock: asyncio.Lock | None = None
_inflight_ticks: set[tuple[str | None, bool]] = set()


def tick_lock() -> asyncio.Lock:
    global _tick_lock
    if _tick_lock is None:
        _tick_lock = asyncio.Lock()
    return _tick_lock


def _claim_tick_job(task_id: str | None, refresh_health: bool) -> bool:
    key = (task_id, refresh_health)
    if key in _inflight_ticks:
        return False
    _inflight_ticks.add(key)
    return True


def _release_tick_job(task_id: str | None, refresh_health: bool) -> None:
    _inflight_ticks.discard((task_id, refresh_health))


def schedule_locked_tick(
    background_tasks: Any,
    task_id: str | None = None,
    *,
    refresh_health: bool = True,
    wait: bool = True,
) -> None:
    """Queue a dispatcher tick.

    Polls pass wait=False: if a tick is already uploading/polling a worker,
    skip instead of stacking BackgroundTasks that pin request DB sessions.
    """
    if not wait and tick_lock().locked():
        return
    background_tasks.add_task(locked_tick_job, task_id, refresh_health=refresh_health)


async def tick_once(db: Session, task_id: str | None = None, *, refresh_health: bool = True) -> None:
    # Persist the caller's pending writes first so SQLite is not locked during worker HTTP.
    _commit(db)
    settings = get_settings()
    nodes = list(db.scalars(select(WorkerNode)).all())
    if refresh_health:
        await refresh_nodes_health(db, nodes)
    _commit(db)
    query = select(Task).where(Task.status.in_(("queued", "running")))
    if task_id:
        query = query.where(Task.id == task_id)
    tasks = list(db.scalars(query).all())
    from app.services.capture_runner import maybe_start_capture, try_finish_capture_task
    from app.services.import_runner import maybe_start_import

    for task in tasks:
        if task.type == "import":
            if task.status == "queued":
                maybe_start_import(db, task)
            continue
        if task.type == "capture":
            await try_finish_capture_task(db, task)
            maybe_start_capture(db, task)
            continue
        if task.status == "running" and task.worker_task_id:
            await poll_running_task(db, task, nodes)
        if task.status == "queued":
            await dispatch_queued_task(db, task, nodes, settings.DISPATCH_NO_CANDIDATE_SEC)
        _commit(db)


async def locked_tick(
    db: Session, task_id: str | None = None, *, refresh_health: bool = True
) -> None:
    async with tick_lock():
        await tick_once(db, task_id=task_id, refresh_health=refresh_health)


async def locked_tick_job(task_id: str | None = None, *, refresh_health: bool = True) -> None:
    """Run a dispatcher tick in a fresh DB session (for BackgroundTasks)."""
    if not _claim_tick_job(task_id, refresh_health):
        return
    from app.db import SessionLocal

    try:
        async with tick_lock():
            db = SessionLocal()
            try:
                await tick_once(db, task_id=task_id, refresh_health=refresh_health)
                db.commit()
            except Exception:
                db.rollback()
                log.exception("background tick failed task=%s", task_id)
            finally:
                db.close()
    finally:
        _release_tick_job(task_id, refresh_health)


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
    session = SessionLocal()
    try:
        async with tick_lock():
            await recover_orphaned_tasks(session)
        session.commit()
    except Exception:
        session.rollback()
        log.exception("task recovery failed")
    finally:
        session.close()
    while not stop_event.is_set():
        tick_started = time.perf_counter()
        try:
            async with tick_lock():
                session = SessionLocal()
                try:
                    await tick_once(session)
                    from app.services.retention import purge_expired_audio

                    purge_expired_audio(session)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            from app.services.storage_gc import drain_all_pending_storage_deletes

            await asyncio.to_thread(drain_all_pending_storage_deletes)
            mark_dispatcher_tick_success()
            observe_dispatcher_tick(time.perf_counter() - tick_started)
        except Exception:
            observe_dispatcher_tick_error()
            log.exception("dispatcher tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.DISPATCH_POLL_SEC)
        except TimeoutError:
            pass

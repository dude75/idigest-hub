"""Impact preview before deleting a worker node."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_instance_settings
from app.models import Task, User, WorkerNode
from app.services.transcribe_models import dispatchable_pairs, resolve_transcribe_models


def _pairs_set(pairs: list[dict[str, str | None]]) -> set[tuple[str, str | None]]:
    return {(item["asr_model"], item.get("diarization_model")) for item in pairs}


def _pair_public(asr: str, diar: str | None) -> dict[str, str | None]:
    return {"asr_model": asr, "diarization_model": diar}


def _transcribe_impact(db: Session, node: WorkerNode, all_nodes: list[WorkerNode]) -> dict[str, Any]:
    settings = get_instance_settings(db)
    enabled_transcribe = [row for row in all_nodes if row.enabled and row.type == "transcribe"]
    remaining_transcribe = [row for row in enabled_transcribe if row.id != node.id]

    before_pairs = _pairs_set(dispatchable_pairs(enabled_transcribe))
    after_pairs = _pairs_set(dispatchable_pairs(remaining_transcribe))
    lost_pairs = sorted(before_pairs - after_pairs, key=lambda item: (item[0], item[1] or ""))

    instance_combo = (settings.asr_model, settings.diarization_model)
    instance_defaults_broken = bool(lost_pairs) and instance_combo in before_pairs and instance_combo not in after_pairs

    affected_users: list[dict[str, str | None]] = []
    for user in db.scalars(select(User).order_by(User.email)).all():
        prefs = resolve_transcribe_models(user, settings)
        combo = (prefs["asr_model"], prefs["diarization_model"])
        if combo in after_pairs:
            continue
        if combo not in before_pairs:
            continue
        affected_users.append(
            {
                "id": user.id,
                "email": user.email,
                "asr_model": prefs["asr_model"],
                "diarization_model": prefs["diarization_model"],
            }
        )

    affected_tasks: list[dict[str, Any]] = []
    for task in db.scalars(
        select(Task).where(Task.type == "transcribe", Task.status.in_(("queued", "running")))
    ).all():
        combo = (task.snap_asr_model or "whisper", task.snap_diarization_model)
        on_worker = task.worker_id == node.id
        if combo not in after_pairs or (on_worker and task.status == "running"):
            affected_tasks.append(
                {
                    "task_id": task.id,
                    "status": task.status,
                    "asr_model": combo[0],
                    "diarization_model": combo[1],
                    "on_worker": on_worker,
                }
            )

    blocking = bool(lost_pairs or instance_defaults_broken or affected_users or affected_tasks)
    return {
        "blocking": blocking,
        "remaining_transcribe_workers": len(remaining_transcribe),
        "lost_model_pairs": [_pair_public(asr, diar) for asr, diar in lost_pairs],
        "instance_defaults_broken": instance_defaults_broken,
        "instance_defaults": {
            "asr_model": settings.asr_model,
            "diarization_model": settings.diarization_model,
        },
        "affected_users": affected_users,
        "affected_users_count": len(affected_users),
        "affected_tasks": affected_tasks,
        "affected_tasks_count": len(affected_tasks),
    }


def _summarize_impact(db: Session, node: WorkerNode, all_nodes: list[WorkerNode]) -> dict[str, Any]:
    enabled_summarize = [row for row in all_nodes if row.enabled and row.type == "summarize"]
    remaining_summarize = [row for row in enabled_summarize if row.id != node.id]
    last_enabled_worker = node.enabled and len(remaining_summarize) == 0

    running_on_worker = list(
        db.scalars(
            select(Task).where(
                Task.type == "summarize",
                Task.status == "running",
                Task.worker_id == node.id,
            )
        ).all()
    )
    queued_summarize = []
    if last_enabled_worker:
        queued_summarize = list(
            db.scalars(select(Task).where(Task.type == "summarize", Task.status == "queued")).all()
        )

    affected_tasks = [
        {"task_id": task.id, "status": task.status, "on_worker": task.worker_id == node.id}
        for task in [*running_on_worker, *queued_summarize]
    ]
    blocking = bool(last_enabled_worker or running_on_worker or queued_summarize)
    return {
        "blocking": blocking,
        "remaining_summarize_workers": len(remaining_summarize),
        "last_enabled_worker": last_enabled_worker,
        "affected_tasks": affected_tasks,
        "affected_tasks_count": len(affected_tasks),
    }


def compute_worker_delete_impact(db: Session, node: WorkerNode) -> dict[str, Any]:
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    payload: dict[str, Any] = {
        "worker": {
            "id": node.id,
            "name": node.name,
            "type": node.type,
            "enabled": node.enabled,
            "base_url": node.base_url,
        },
        "blocking": False,
    }
    if node.type == "transcribe":
        payload.update(_transcribe_impact(db, node, all_nodes))
    elif node.type == "summarize":
        payload.update(_summarize_impact(db, node, all_nodes))
    else:
        payload["detail"] = {}
    payload["blocking"] = bool(payload.get("blocking"))
    return payload

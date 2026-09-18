"""Impact preview before deleting or reconfiguring a worker node."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_instance_settings
from app.models import Task, User, WorkerNode
from app.services.transcribe_models import dispatchable_pairs, resolve_transcribe_models
from app.timeutil import utcnow


def _pairs_set(pairs: list[dict[str, str | None]]) -> set[tuple[str, str | None]]:
    return {(item["asr_model"], item.get("diarization_model")) for item in pairs}


def _pair_public(asr: str, diar: str | None) -> dict[str, str | None]:
    return {"asr_model": asr, "diarization_model": diar}


def _pair_sort_key(item: tuple[str, str | None]) -> tuple[str, str]:
    asr, diar = item
    return (asr, diar or "")


def _replacement_options(
    after_pairs: set[tuple[str, str | None]],
    settings,
) -> tuple[dict[str, str | None] | None, list[dict[str, str | None]]]:
    available = [_pair_public(asr, diar) for asr, diar in sorted(after_pairs, key=_pair_sort_key)]
    if not available:
        return None, []
    instance_combo = (settings.asr_model, settings.diarization_model)
    if instance_combo in after_pairs:
        return _pair_public(instance_combo[0], instance_combo[1]), available
    for asr, diar in sorted(after_pairs, key=_pair_sort_key):
        if asr == settings.asr_model:
            return _pair_public(asr, diar), available
    first = sorted(after_pairs, key=_pair_sort_key)[0]
    return _pair_public(first[0], first[1]), available


def _enabled(nodes: list[WorkerNode], worker_type: str) -> list[WorkerNode]:
    return [row for row in nodes if row.enabled and row.type == worker_type]


def _with_worker_state(
    node: WorkerNode,
    *,
    type: str | None = None,
    enabled: bool | None = None,
    asr_models: list[str] | None = None,
    diarization_models: list[str] | None = None,
) -> WorkerNode:
    snap = copy.copy(node)
    if type is not None:
        snap.type = type
    if enabled is not None:
        snap.enabled = enabled
    if asr_models is not None:
        snap.asr_models_json = asr_models
    if diarization_models is not None:
        snap.diarization_models_json = diarization_models
    if snap.type != "transcribe":
        snap.asr_models_json = None
        snap.diarization_models_json = None
    return snap


def _transcribe_impact(
    db: Session,
    *,
    before_nodes: list[WorkerNode],
    after_nodes: list[WorkerNode],
    focus_worker_id: str,
) -> dict[str, Any]:
    settings = get_instance_settings(db)
    enabled_before = _enabled(before_nodes, "transcribe")
    enabled_after = _enabled(after_nodes, "transcribe")

    before_pairs = _pairs_set(dispatchable_pairs(enabled_before))
    after_pairs = _pairs_set(dispatchable_pairs(enabled_after))
    lost_pairs = sorted(before_pairs - after_pairs, key=lambda item: (item[0], item[1] or ""))

    instance_combo = (settings.asr_model, settings.diarization_model)
    instance_defaults_broken = bool(lost_pairs) and instance_combo in before_pairs and instance_combo not in after_pairs

    affected_users: list[dict[str, str | None]] = []
    for user in db.scalars(select(User).order_by(User.email)).all():
        prefs = resolve_transcribe_models(user, settings)
        combo = (prefs["asr_model"], prefs["diarization_model"])
        if combo in after_pairs or combo not in before_pairs:
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
        on_worker = task.worker_id == focus_worker_id
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

    suggested, available = _replacement_options(after_pairs, settings)
    blocking = bool(lost_pairs or instance_defaults_broken or affected_users or affected_tasks)
    return {
        "blocking": blocking,
        "remaining_transcribe_workers": len(enabled_after),
        "lost_model_pairs": [_pair_public(asr, diar) for asr, diar in lost_pairs],
        "available_pairs": available,
        "suggested_replacement": suggested,
        "can_remediate": bool(blocking and suggested),
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


def _summarize_impact(
    db: Session,
    *,
    before_nodes: list[WorkerNode],
    after_nodes: list[WorkerNode],
    focus_worker_id: str,
    focus_was_enabled: bool,
) -> dict[str, Any]:
    enabled_before = _enabled(before_nodes, "summarize")
    enabled_after = _enabled(after_nodes, "summarize")
    last_enabled_worker = focus_was_enabled and len(enabled_before) > 0 and len(enabled_after) == 0

    running_on_worker = list(
        db.scalars(
            select(Task).where(
                Task.type == "summarize",
                Task.status == "running",
                Task.worker_id == focus_worker_id,
            )
        ).all()
    )
    queued_summarize = []
    if last_enabled_worker:
        queued_summarize = list(
            db.scalars(select(Task).where(Task.type == "summarize", Task.status == "queued")).all()
        )

    affected_tasks = [
        {"task_id": task.id, "status": task.status, "on_worker": task.worker_id == focus_worker_id}
        for task in [*running_on_worker, *queued_summarize]
    ]
    blocking = bool(last_enabled_worker or running_on_worker or queued_summarize)
    return {
        "blocking": blocking,
        "remaining_summarize_workers": len(enabled_after),
        "last_enabled_worker": last_enabled_worker,
        "affected_tasks": affected_tasks,
        "affected_tasks_count": len(affected_tasks),
    }


def _worker_public(node: WorkerNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "enabled": node.enabled,
        "base_url": node.base_url,
    }


def _compute_impact(
    db: Session,
    node: WorkerNode,
    *,
    before_nodes: list[WorkerNode],
    after_nodes: list[WorkerNode],
    action: str,
) -> dict[str, Any]:
    after_node = next((row for row in after_nodes if row.id == node.id), None)
    worker_type = after_node.type if after_node is not None else node.type
    payload: dict[str, Any] = {
        "action": action,
        "worker": _worker_public(after_node or node),
        "blocking": False,
    }
    if worker_type == "transcribe":
        payload.update(
            _transcribe_impact(
                db,
                before_nodes=before_nodes,
                after_nodes=after_nodes,
                focus_worker_id=node.id,
            )
        )
    elif worker_type == "summarize":
        payload.update(
            _summarize_impact(
                db,
                before_nodes=before_nodes,
                after_nodes=after_nodes,
                focus_worker_id=node.id,
                focus_was_enabled=node.enabled,
            )
        )
    payload["blocking"] = bool(payload.get("blocking"))
    return payload


def compute_worker_delete_impact(db: Session, node: WorkerNode) -> dict[str, Any]:
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    after_nodes = [row for row in all_nodes if row.id != node.id]
    return _compute_impact(db, node, before_nodes=all_nodes, after_nodes=after_nodes, action="delete")


def apply_transcribe_remediation(
    db: Session,
    *,
    after_nodes: list[WorkerNode],
    before_nodes: list[WorkerNode],
    focus_worker_id: str,
    asr_model: str,
    diarization_model: str | None,
) -> dict[str, int | bool]:
    settings = get_instance_settings(db)
    enabled_before = _enabled(before_nodes, "transcribe")
    enabled_after = _enabled(after_nodes, "transcribe")
    before_pairs = _pairs_set(dispatchable_pairs(enabled_before))
    after_pairs = _pairs_set(dispatchable_pairs(enabled_after))
    replacement = (asr_model.strip(), diarization_model.strip() if diarization_model else None)
    if replacement not in after_pairs:
        raise ValueError("invalid_replacement")

    users_updated = 0
    tasks_updated = 0
    instance_updated = False

    instance_combo = (settings.asr_model, settings.diarization_model)
    if instance_combo in before_pairs and instance_combo not in after_pairs:
        settings.asr_model = replacement[0]
        settings.diarization_model = replacement[1]
        instance_updated = True

    for user in db.scalars(select(User)).all():
        prefs = resolve_transcribe_models(user, settings)
        combo = (prefs["asr_model"], prefs["diarization_model"])
        if combo in after_pairs or combo not in before_pairs:
            continue
        user.asr_model = replacement[0]
        user.diarization_model = "" if replacement[1] is None else replacement[1]
        user.updated_at = utcnow()
        users_updated += 1

    for task in db.scalars(
        select(Task).where(Task.type == "transcribe", Task.status.in_(("queued", "running")))
    ).all():
        combo = (task.snap_asr_model or "whisper", task.snap_diarization_model)
        on_worker = task.worker_id == focus_worker_id
        if combo in after_pairs and not (on_worker and task.status == "running"):
            continue
        if combo not in before_pairs and not on_worker:
            continue
        task.snap_asr_model = replacement[0]
        task.snap_diarization_model = replacement[1]
        if task.status == "running":
            task.worker_id = None
            task.worker_task_id = None
            task.status = "queued"
            task.meta_json = {"stage": "queued"}
        task.retry_without_timeout = False
        task.updated_at = utcnow()
        tasks_updated += 1

    return {
        "instance_defaults_updated": instance_updated,
        "users_updated": users_updated,
        "tasks_updated": tasks_updated,
    }


def compute_worker_change_impact(
    db: Session,
    node: WorkerNode,
    *,
    type: str,
    enabled: bool,
    asr_models: list[str] | None = None,
    diarization_models: list[str] | None = None,
) -> dict[str, Any]:
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    after_nodes = [
        _with_worker_state(
            row,
            type=type,
            enabled=enabled,
            asr_models=asr_models if type == "transcribe" else None,
            diarization_models=diarization_models if type == "transcribe" else None,
        )
        if row.id == node.id
        else row
        for row in all_nodes
    ]
    return _compute_impact(db, node, before_nodes=all_nodes, after_nodes=after_nodes, action="change")

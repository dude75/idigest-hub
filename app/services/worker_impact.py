"""Impact preview before deleting or reconfiguring a worker node."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_instance_settings
from app.models import OrgCaptureJitsiHost, Organization, Task, User, WorkerNode
from app.services.capture_platforms import worker_offers_connector
from app.services.summarize_models import resolve_summarize_models, worker_summarize_model
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
    capture_connectors: list[str] | None = None,
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
    if capture_connectors is not None:
        snap.capture_connectors_json = capture_connectors
    if snap.type != "transcribe":
        snap.asr_models_json = None
        snap.diarization_models_json = None
    if snap.type != "capture":
        snap.capture_connectors_json = None
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


def _capture_worker_public(node: WorkerNode) -> dict[str, str]:
    return {
        "id": node.id,
        "name": node.name,
        "base_url": node.base_url,
    }


def _capture_replacement_workers(nodes: list[WorkerNode]) -> list[WorkerNode]:
    out = [
        node
        for node in nodes
        if node.type == "capture" and node.enabled and worker_offers_connector(node, "jitsi")
    ]
    out.sort(key=lambda item: (item.name.lower(), item.created_at))
    return out


def _capture_jitsi_hosts(db: Session, worker_id: str) -> list[OrgCaptureJitsiHost]:
    return list(
        db.scalars(select(OrgCaptureJitsiHost).where(OrgCaptureJitsiHost.worker_id == worker_id)).all()
    )


def _capture_jitsi_hosts_detail(db: Session, worker_id: str) -> list[dict[str, str]]:
    rows = _capture_jitsi_hosts(db, worker_id)
    if not rows:
        return []
    org_ids = {row.org_id for row in rows}
    names = {
        org.id: org.name
        for org in db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
    }
    out: list[dict[str, str]] = []
    for row in rows:
        out.append(
            {
                "host": row.host,
                "org_id": row.org_id,
                "org_name": (names.get(row.org_id) or "").strip() or row.org_id,
            }
        )
    out.sort(key=lambda item: (item["org_name"].lower(), item["host"]))
    return out


def _capture_tasks(db: Session, worker_id: str) -> list[Task]:
    return list(
        db.scalars(
            select(Task).where(
                Task.type == "capture",
                Task.worker_id == worker_id,
                Task.status.in_(("queued", "running")),
            )
        ).all()
    )


def _capture_impact(
    db: Session,
    *,
    worker_id: str,
    enabled_before: bool,
    enabled_after: bool,
    connectors_before: list[str],
    connectors_after: list[str],
    action: str,
    after_nodes: list[WorkerNode],
) -> dict[str, Any]:
    jitsi_hosts = _capture_jitsi_hosts_detail(db, worker_id)
    tasks = _capture_tasks(db, worker_id)
    losing_jitsi = "jitsi" in connectors_before and "jitsi" not in connectors_after
    disabling = enabled_before and not enabled_after
    blocking = bool(jitsi_hosts) and (disabling or losing_jitsi or action == "delete")
    if tasks and (disabling or action == "delete"):
        blocking = True
    replacements = _capture_replacement_workers(after_nodes)
    suggested = replacements[0] if replacements else None
    return {
        "blocking": blocking,
        "capture_jitsi_hosts": jitsi_hosts,
        "capture_jitsi_hosts_count": len(jitsi_hosts),
        "capture_tasks_count": len(tasks),
        "capture_losing_jitsi": losing_jitsi and bool(jitsi_hosts),
        "available_capture_workers": [_capture_worker_public(node) for node in replacements],
        "suggested_capture_worker": _capture_worker_public(suggested) if suggested else None,
        "can_remediate": bool(blocking and suggested),
    }


def _summarize_models_set(nodes: list[WorkerNode]) -> set[str]:
    models: set[str] = set()
    for node in _enabled(nodes, "summarize"):
        model = worker_summarize_model(node)
        if model:
            models.add(model)
    return models


def _summarize_model_public(model: str) -> dict[str, str]:
    return {"summarize_model": model}


def _summarize_replacement_options(
    after_models: set[str],
    settings,
) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    available = [_summarize_model_public(model) for model in sorted(after_models)]
    if not available:
        return None, []
    instance_model = (settings.summarize_model or "").strip()
    if instance_model and instance_model in after_models:
        return _summarize_model_public(instance_model), available
    return _summarize_model_public(sorted(after_models)[0]), available


def _summarize_impact(
    db: Session,
    *,
    before_nodes: list[WorkerNode],
    after_nodes: list[WorkerNode],
    focus_worker_id: str,
    focus_was_enabled: bool,
) -> dict[str, Any]:
    settings = get_instance_settings(db)
    enabled_before = _enabled(before_nodes, "summarize")
    enabled_after = _enabled(after_nodes, "summarize")
    before_models = _summarize_models_set(before_nodes)
    after_models = _summarize_models_set(after_nodes)
    lost_models = sorted(before_models - after_models)
    last_enabled_worker = focus_was_enabled and len(enabled_before) > 0 and len(enabled_after) == 0

    instance_model = (settings.summarize_model or "").strip() or None
    instance_defaults_broken = bool(lost_models) and instance_model in before_models and instance_model not in after_models

    affected_users: list[dict[str, str | None]] = []
    for user in db.scalars(select(User).order_by(User.email)).all():
        prefs = resolve_summarize_models(user, settings, available=sorted(after_models))
        model = prefs["summarize_model"]
        if not model or model in after_models or model not in before_models:
            continue
        affected_users.append(
            {
                "id": user.id,
                "email": user.email,
                "summarize_model": model,
            }
        )

    affected_tasks: list[dict[str, Any]] = []
    for task in db.scalars(
        select(Task).where(Task.type == "summarize", Task.status.in_(("queued", "running")))
    ).all():
        model = (task.snap_summarize_model or "").strip() or None
        on_worker = task.worker_id == focus_worker_id
        if model and model in after_models and not (on_worker and task.status == "running"):
            continue
        if not model and not last_enabled_worker and not on_worker:
            continue
        if not model and not last_enabled_worker:
            continue
        affected_tasks.append(
            {
                "task_id": task.id,
                "status": task.status,
                "summarize_model": model,
                "on_worker": on_worker,
            }
        )

    suggested, available = _summarize_replacement_options(after_models, settings)
    blocking = bool(
        lost_models
        or instance_defaults_broken
        or affected_users
        or affected_tasks
        or last_enabled_worker
    )
    return {
        "blocking": blocking,
        "remaining_summarize_workers": len(enabled_after),
        "last_enabled_worker": last_enabled_worker,
        "lost_summarize_models": lost_models,
        "available_summarize_models": available,
        "suggested_summarize_replacement": suggested,
        "can_remediate": bool(blocking and suggested),
        "instance_defaults_broken": instance_defaults_broken,
        "instance_defaults": {"summarize_model": settings.summarize_model},
        "affected_users": affected_users,
        "affected_users_count": len(affected_users),
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
    elif worker_type == "capture":
        snap = after_node if after_node is not None else node
        if action == "delete":
            enabled_after = False
            connectors_after: list[str] = []
        else:
            enabled_after = snap.enabled
            connectors_after = list(snap.capture_connectors_json or [])
        payload.update(
            _capture_impact(
                db,
                worker_id=node.id,
                enabled_before=node.enabled,
                enabled_after=enabled_after,
                connectors_before=list(node.capture_connectors_json or []),
                connectors_after=connectors_after,
                action=action,
                after_nodes=after_nodes,
            )
        )
    payload["blocking"] = bool(payload.get("blocking"))
    return payload


def compute_worker_delete_impact(db: Session, node: WorkerNode) -> dict[str, Any]:
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    after_nodes = [row for row in all_nodes if row.id != node.id]
    return _compute_impact(db, node, before_nodes=all_nodes, after_nodes=after_nodes, action="delete")


def prepare_worker_node_delete(db: Session, worker_id: str) -> dict[str, int]:
    """Drop FK references so worker_nodes row can be removed (capture Jitsi maps, task.worker_id)."""
    jitsi_hosts = _capture_jitsi_hosts(db, worker_id)
    for row in jitsi_hosts:
        db.delete(row)

    tasks_updated = 0
    for task in db.scalars(select(Task).where(Task.worker_id == worker_id)).all():
        if task.type == "capture" and task.status in ("queued", "running"):
            task.worker_id = None
            task.worker_task_id = None
            task.status = "queued"
            task.meta_json = {"stage": "queued"}
            task.retry_without_timeout = False
        else:
            task.worker_id = None
            if task.status == "running":
                task.worker_task_id = None
        task.updated_at = utcnow()
        tasks_updated += 1

    return {"jitsi_hosts_removed": len(jitsi_hosts), "tasks_updated": tasks_updated}


def apply_capture_remediation(
    db: Session,
    *,
    after_nodes: list[WorkerNode],
    focus_worker_id: str,
    replacement_worker_id: str,
) -> dict[str, int]:
    replacement = next((node for node in after_nodes if node.id == replacement_worker_id), None)
    if replacement is None or replacement.type != "capture" or not replacement.enabled:
        raise ValueError("invalid_replacement")
    if not worker_offers_connector(replacement, "jitsi"):
        raise ValueError("invalid_replacement")

    jitsi_hosts_updated = 0
    for row in _capture_jitsi_hosts(db, focus_worker_id):
        row.worker_id = replacement_worker_id
        row.updated_at = utcnow()
        jitsi_hosts_updated += 1

    tasks_updated = 0
    for task in _capture_tasks(db, focus_worker_id):
        if task.status == "running":
            task.worker_id = None
            task.worker_task_id = None
            task.status = "queued"
            task.meta_json = {"stage": "queued"}
        else:
            task.worker_id = replacement_worker_id
            task.worker_task_id = None
        task.retry_without_timeout = False
        task.updated_at = utcnow()
        tasks_updated += 1

    db.flush()
    return {"jitsi_hosts_updated": jitsi_hosts_updated, "tasks_updated": tasks_updated}


def apply_summarize_remediation(
    db: Session,
    *,
    after_nodes: list[WorkerNode],
    before_nodes: list[WorkerNode],
    focus_worker_id: str,
    summarize_model: str,
) -> dict[str, int | bool]:
    replacement = summarize_model.strip()
    if not replacement:
        raise ValueError("invalid_replacement")
    settings = get_instance_settings(db)
    before_models = _summarize_models_set(before_nodes)
    after_models = _summarize_models_set(after_nodes)
    if replacement not in after_models:
        raise ValueError("invalid_replacement")

    users_updated = 0
    tasks_updated = 0
    instance_updated = False

    instance_model = (settings.summarize_model or "").strip() or None
    if instance_model and instance_model in before_models and instance_model not in after_models:
        settings.summarize_model = replacement
        instance_updated = True

    for user in db.scalars(select(User)).all():
        prefs = resolve_summarize_models(user, settings, available=sorted(after_models))
        model = prefs["summarize_model"]
        if not model or model in after_models or model not in before_models:
            continue
        user.summarize_model = replacement
        user.updated_at = utcnow()
        users_updated += 1

    for task in db.scalars(
        select(Task).where(Task.type == "summarize", Task.status.in_(("queued", "running")))
    ).all():
        model = (task.snap_summarize_model or "").strip() or None
        on_worker = task.worker_id == focus_worker_id
        if model and model in after_models and not (on_worker and task.status == "running"):
            continue
        if not model and not on_worker:
            continue
        task.snap_summarize_model = replacement
        if task.status == "running":
            task.worker_id = None
            task.worker_task_id = None
            task.status = "queued"
            task.meta_json = {"stage": "queued"}
        task.retry_without_timeout = False
        task.updated_at = utcnow()
        tasks_updated += 1

    db.flush()
    return {
        "instance_defaults_updated": instance_updated,
        "users_updated": users_updated,
        "tasks_updated": tasks_updated,
    }


def apply_transcribe_remediation(
    db: Session,
    *,
    after_nodes: list[WorkerNode],
    before_nodes: list[WorkerNode],
    focus_worker_id: str,
    asr_model: str,
    diarization_model: str | None,
) -> dict[str, int | bool]:
    if not asr_model:
        raise ValueError("invalid_replacement")
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

    db.flush()
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
    capture_connectors: list[str] | None = None,
) -> dict[str, Any]:
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    after_nodes = [
        _with_worker_state(
            row,
            type=type,
            enabled=enabled,
            asr_models=asr_models if type == "transcribe" else None,
            diarization_models=diarization_models if type == "transcribe" else None,
            capture_connectors=capture_connectors if type == "capture" else None,
        )
        if row.id == node.id
        else row
        for row in all_nodes
    ]
    return _compute_impact(db, node, before_nodes=all_nodes, after_nodes=after_nodes, action="change")


def compute_worker_capture_change_impact(
    db: Session,
    node: WorkerNode,
    *,
    enabled: bool,
    capture_connectors: list[str] | None,
) -> dict[str, Any]:
    return compute_worker_change_impact(
        db,
        node,
        type="capture",
        enabled=enabled,
        capture_connectors=capture_connectors,
    )

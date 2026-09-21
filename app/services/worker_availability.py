"""Dispatch-ready worker counts for instance admin."""

from __future__ import annotations

from typing import Any

from app.models import WorkerNode
from app.services.capture_platforms import aggregate_capture_worker_slots, worker_offers_connector
from app.services.transcribe_models import _node_model_lists


def _engines(node: WorkerNode) -> dict[str, str]:
    health = node.last_health or {}
    engines = health.get("engines") or {}
    return engines if isinstance(engines, dict) else {}


def worker_is_dispatch_available(node: WorkerNode, *, capture_connectors: list[str]) -> bool:
    if not node.enabled:
        return False
    health = node.last_health or {}
    if node.type == "transcribe":
        if health.get("_http") != 200:
            return False
        asr_list, diar_list = _node_model_lists(node)
        engines = _engines(node)
        for asr in asr_list:
            if engines.get(asr, "disabled") != "loaded":
                continue
            if not diar_list:
                return True
            for diar in diar_list:
                if engines.get(diar, "loaded") == "loaded":
                    return True
        return False
    if node.type == "summarize":
        return health.get("_ready_http") == 200
    if node.type == "capture":
        if health.get("_http") != 200:
            return False
        return any(worker_offers_connector(node, connector_id) for connector_id in capture_connectors)
    return False


def _type_bucket(nodes: list[WorkerNode], worker_type: str, *, capture_connectors: list[str]) -> dict[str, int]:
    typed = [node for node in nodes if node.type == worker_type]
    return {
        "total": len(typed),
        "enabled": sum(1 for node in typed if node.enabled),
        "available": sum(
            1 for node in typed if worker_is_dispatch_available(node, capture_connectors=capture_connectors)
        ),
    }


def hub_worker_slots(bucket: dict[str, int]) -> dict[str, int]:
    """Transcribe/summarize: slots = dispatch-ready nodes (available) of enabled pool (max)."""
    enabled = int(bucket.get("enabled") or 0)
    available = int(bucket.get("available") or 0)
    return {
        "max": enabled,
        "available": available,
        "active": max(enabled - available, 0),
    }


def workers_availability_summary(
    nodes: list[WorkerNode],
    *,
    capture_connectors: list[str],
    import_max_concurrent: int,
) -> dict[str, Any]:
    by_type = {
        worker_type: _type_bucket(nodes, worker_type, capture_connectors=capture_connectors)
        for worker_type in ("transcribe", "summarize", "capture")
    }
    return {
        "total": len(nodes),
        "enabled": sum(1 for node in nodes if node.enabled),
        "available": sum(
            1 for node in nodes if worker_is_dispatch_available(node, capture_connectors=capture_connectors)
        ),
        "by_type": by_type,
        "hub_limits": {
            "import_max_concurrent": import_max_concurrent,
        },
        "capture_slots": aggregate_capture_worker_slots(nodes),
        "transcribe_slots": hub_worker_slots(by_type["transcribe"]),
        "summarize_slots": hub_worker_slots(by_type["summarize"]),
    }

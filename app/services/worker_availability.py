"""Dispatch-ready worker counts for instance admin."""

from __future__ import annotations

from typing import Any

from app.models import WorkerNode
from app.services.capture_platforms import worker_offers_connector
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


def hub_node_capacity(bucket: dict[str, int]) -> dict[str, int]:
    """Fallback: dispatch-ready hub nodes (available) of enabled pool (max)."""
    enabled = int(bucket.get("enabled") or 0)
    available = int(bucket.get("available") or 0)
    return {
        "max": enabled,
        "available": available,
        "active": max(enabled - available, 0),
    }


def _normalize_worker_base_url(base_url: str) -> str:
    return base_url.rstrip("/").lower()


def parse_health_worker_pool(health: dict[str, Any] | None) -> dict[str, int] | None:
    """Worker GET /health → workers.max|active|available (shared contract for all types)."""
    if not health or health.get("_http") != 200:
        return None
    raw = health.get("workers")
    if not isinstance(raw, dict):
        return None
    try:
        return {
            "max": max(0, int(raw.get("max") or 0)),
            "active": max(0, int(raw.get("active") or 0)),
            "available": max(0, int(raw.get("available") or 0)),
        }
    except (TypeError, ValueError):
        return None


def aggregate_worker_pool(
    nodes: list[WorkerNode],
    worker_type: str,
    *,
    capture_connectors: list[str],
) -> dict[str, int] | None:
    """Sum health.workers pools; one physical worker (same base_url) is counted once."""
    pools_by_url: dict[str, dict[str, int]] = {}
    for node in nodes:
        if node.type != worker_type or not node.enabled:
            continue
        if not worker_is_dispatch_available(node, capture_connectors=capture_connectors):
            continue
        pool = parse_health_worker_pool(node.last_health)
        if pool is None:
            continue
        url_key = _normalize_worker_base_url(node.base_url)
        pools_by_url.setdefault(url_key, pool)
    if not pools_by_url:
        return None
    total_max = 0
    total_active = 0
    total_available = 0
    for pool in pools_by_url.values():
        total_max += pool["max"]
        total_active += pool["active"]
        total_available += pool["available"]
    return {"max": total_max, "active": total_active, "available": total_available}


def type_capacity(
    nodes: list[WorkerNode],
    worker_type: str,
    bucket: dict[str, int],
    *,
    capture_connectors: list[str],
) -> dict[str, int]:
    return aggregate_worker_pool(nodes, worker_type, capture_connectors=capture_connectors) or hub_node_capacity(
        bucket
    )


def worker_node_has_pool_capacity(node: WorkerNode) -> bool:
    pool = parse_health_worker_pool(node.last_health)
    return pool is not None and pool["available"] > 0


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
        "capture_capacity": type_capacity(
            nodes, "capture", by_type["capture"], capture_connectors=capture_connectors
        ),
        "transcribe_capacity": type_capacity(
            nodes, "transcribe", by_type["transcribe"], capture_connectors=capture_connectors
        ),
        "summarize_capacity": type_capacity(
            nodes, "summarize", by_type["summarize"], capture_connectors=capture_connectors
        ),
    }

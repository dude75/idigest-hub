"""Capture connector catalog and instance whitelist helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import InstanceSettings, WorkerNode

CAPTURE_CONNECTOR_CATALOG: tuple[dict[str, Any], ...] = (
    {"id": "jitsi", "label": "Jitsi Meet"},
    {"id": "zoom", "label": "Zoom"},
)

_CATALOG_BY_ID = {item["id"]: item for item in CAPTURE_CONNECTOR_CATALOG}


def catalog_entry(connector_id: str) -> dict[str, Any] | None:
    return _CATALOG_BY_ID.get(connector_id)


def default_allowed_connectors() -> list[str]:
    return ["jitsi"]


def normalize_allowed_connectors(raw: list[str] | None) -> list[str]:
    if not raw:
        return default_allowed_connectors()
    out: list[str] = []
    for item in raw:
        key = str(item).strip()
        if key and key in _CATALOG_BY_ID and key not in out:
            out.append(key)
    return out or default_allowed_connectors()


def allowed_connectors(settings: InstanceSettings) -> list[str]:
    raw = settings.capture_allowed_connectors_json
    if raw is None:
        return default_allowed_connectors()
    if isinstance(raw, list):
        return normalize_allowed_connectors([str(x) for x in raw])
    return default_allowed_connectors()


def org_jitsi_capture_enabled(settings: InstanceSettings) -> bool:
    """True when instance admin enabled capture and Jitsi is an allowed connector."""
    return bool(settings.capture_enabled) and "jitsi" in allowed_connectors(settings)


def validate_allowed_connectors(ids: list[str]) -> list[str]:
    out: list[str] = []
    for item in ids:
        key = str(item).strip()
        if not key:
            continue
        if key not in _CATALOG_BY_ID:
            raise ValueError(f"unknown capture connector: {key}")
        if key not in out:
            out.append(key)
    if not out:
        raise ValueError("at least one capture connector is required")
    return out


def connector_public(entry: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    return {"id": entry["id"], "label": entry["label"], "enabled": enabled}


def admin_connectors(settings: InstanceSettings) -> list[dict[str, Any]]:
    allowed = set(allowed_connectors(settings))
    return [connector_public(entry, enabled=entry["id"] in allowed) for entry in CAPTURE_CONNECTOR_CATALOG]


def public_connectors(settings: InstanceSettings) -> list[dict[str, Any]]:
    allowed = allowed_connectors(settings)
    out: list[str] = []
    for connector_id in allowed:
        entry = catalog_entry(connector_id)
        if entry is None:
            continue
        out.append({"id": entry["id"], "label": entry["label"]})
    return out


def parse_worker_connectors(health: dict[str, Any] | None) -> dict[str, str]:
    if not health:
        return {}
    connectors = health.get("connectors")
    if not isinstance(connectors, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in connectors.items():
        if isinstance(value, dict):
            status = str(value.get("status") or "")
            out[str(key)] = status
    return out


def worker_offers_connector(node: WorkerNode, connector_id: str) -> bool:
    if node.type != "capture" or not node.enabled:
        return False
    selected = list(node.capture_connectors_json or [])
    if selected and connector_id not in selected:
        return False
    health = node.last_health or {}
    statuses = parse_worker_connectors(health)
    status = statuses.get(connector_id)
    if status:
        return status == "loaded"
    return connector_id in selected


def selectable_connector_ids(health: dict[str, Any] | None) -> list[str]:
    statuses = parse_worker_connectors(health)
    return [key for key, status in statuses.items() if status == "loaded"]


def parse_capture_worker_slots(health: dict[str, Any] | None) -> dict[str, int] | None:
    """icapture-worker GET /health → slots.max|active|available."""
    if not health or health.get("_http") != 200:
        return None
    raw = health.get("slots")
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


def aggregate_capture_worker_slots(nodes: list[WorkerNode]) -> dict[str, int]:
    total_max = 0
    total_active = 0
    total_available = 0
    for node in nodes:
        if node.type != "capture" or not node.enabled:
            continue
        slots = parse_capture_worker_slots(node.last_health)
        if slots is None:
            continue
        total_max += slots["max"]
        total_active += slots["active"]
        total_available += slots["available"]
    return {"max": total_max, "active": total_active, "available": total_available}


def capture_worker_has_free_slot(node: WorkerNode) -> bool:
    if node.type != "capture" or not node.enabled:
        return False
    slots = parse_capture_worker_slots(node.last_health)
    if slots is None:
        return False
    return slots["available"] > 0

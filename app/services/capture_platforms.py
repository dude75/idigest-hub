"""Capture connector catalog and instance whitelist helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstanceSettings, WorkerNode

# Labels when worker health has not reported a connector yet.
FALLBACK_CONNECTOR_LABELS: dict[str, str] = {
    "jitsi": "Jitsi Meet",
    "telemost": "Yandex Telemost",
    "zoom": "Zoom",
    "meet": "Google Meet",
}


def _connector_label(connector_id: str, raw_label: str | None = None) -> str:
    label = (raw_label or "").strip()
    if label:
        return label
    return FALLBACK_CONNECTOR_LABELS.get(connector_id, connector_id)


def catalog_entry(connector_id: str) -> dict[str, Any] | None:
    key = str(connector_id).strip()
    if not key:
        return None
    if key in FALLBACK_CONNECTOR_LABELS:
        return {"id": key, "label": FALLBACK_CONNECTOR_LABELS[key]}
    return {"id": key, "label": key}


def default_allowed_connectors() -> list[str]:
    return ["jitsi"]


def _unique_connector_ids(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        key = str(item).strip()
        if key and key not in out:
            out.append(key)
    return out


def normalize_allowed_connectors(
    raw: list[str] | None,
    *,
    known_ids: set[str] | None = None,
) -> list[str]:
    if not raw:
        return default_allowed_connectors()
    allowed_known = known_ids if known_ids is not None else set(FALLBACK_CONNECTOR_LABELS)
    out: list[str] = []
    for item in raw:
        key = str(item).strip()
        if key and key in allowed_known and key not in out:
            out.append(key)
    return out or default_allowed_connectors()


def allowed_connectors(settings: InstanceSettings) -> list[str]:
    raw = settings.capture_allowed_connectors_json
    if raw is None:
        return default_allowed_connectors()
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            key = str(item).strip()
            if key and key not in out:
                out.append(key)
        return out or default_allowed_connectors()
    return default_allowed_connectors()


def org_jitsi_capture_enabled(settings: InstanceSettings) -> bool:
    """True when instance admin enabled capture and Jitsi is an allowed connector."""
    return bool(settings.capture_enabled) and "jitsi" in allowed_connectors(settings)


def parse_worker_connector_meta(health: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    if not health:
        return {}
    connectors = health.get("connectors")
    if not isinstance(connectors, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, value in connectors.items():
        connector_id = str(key).strip()
        if not connector_id:
            continue
        if isinstance(value, dict):
            status = str(value.get("status") or "")
            label = _connector_label(connector_id, str(value.get("label") or ""))
        elif isinstance(value, str):
            status = value.strip()
            label = _connector_label(connector_id)
        else:
            continue
        out[connector_id] = {"status": status, "label": label}
    return out


def parse_worker_connectors(health: dict[str, Any] | None) -> dict[str, str]:
    return {key: value["status"] for key, value in parse_worker_connector_meta(health).items()}


def aggregate_connector_catalog(db: Session) -> list[dict[str, Any]]:
    """Union of connectors reported on capture workers (latest health)."""
    rows = list(db.scalars(select(WorkerNode).where(WorkerNode.type == "capture")).all())
    merged: dict[str, dict[str, Any]] = {}
    for node in rows:
        for connector_id, info in parse_worker_connector_meta(node.last_health).items():
            existing = merged.get(connector_id)
            if existing is None:
                merged[connector_id] = {
                    "id": connector_id,
                    "label": info["label"],
                    "status": info["status"],
                }
                continue
            if info["status"] == "loaded":
                existing["status"] = "loaded"
            if existing.get("label") == connector_id and info["label"] != connector_id:
                existing["label"] = info["label"]
    return [merged[key] for key in sorted(merged)]


def instance_connector_catalog(db: Session, settings: InstanceSettings) -> list[dict[str, Any]]:
    """Worker-reported connectors plus instance-allowed ids (keep checkboxes if worker offline)."""
    by_id = {item["id"]: dict(item) for item in aggregate_connector_catalog(db)}
    for connector_id in allowed_connectors(settings):
        if connector_id in by_id:
            continue
        by_id[connector_id] = {
            "id": connector_id,
            "label": _connector_label(connector_id),
            "status": "unknown",
        }
    return [by_id[key] for key in sorted(by_id)]


def validate_allowed_connectors(db: Session, settings: InstanceSettings, ids: list[str]) -> list[str]:
    known = {item["id"] for item in instance_connector_catalog(db, settings)}
    if not known:
        known = set(FALLBACK_CONNECTOR_LABELS)
    out: list[str] = []
    for item in ids:
        key = str(item).strip()
        if not key:
            continue
        if key not in known:
            raise ValueError(f"unknown capture connector: {key}")
        if key not in out:
            out.append(key)
    if not out:
        raise ValueError("at least one capture connector is required")
    return out


def connector_public(entry: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    payload = {"id": entry["id"], "label": entry["label"], "enabled": enabled}
    status = entry.get("status")
    if isinstance(status, str) and status:
        payload["status"] = status
    return payload


def admin_connectors(settings: InstanceSettings, db: Session) -> list[dict[str, Any]]:
    allowed = set(allowed_connectors(settings))
    return [
        connector_public(entry, enabled=entry["id"] in allowed)
        for entry in instance_connector_catalog(db, settings)
    ]


def public_connectors(settings: InstanceSettings, db: Session) -> list[dict[str, Any]]:
    allowed = allowed_connectors(settings)
    labels = {item["id"]: item["label"] for item in instance_connector_catalog(db, settings)}
    out: list[dict[str, Any]] = []
    for connector_id in allowed:
        out.append({"id": connector_id, "label": labels.get(connector_id, _connector_label(connector_id))})
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


def normalize_worker_capture_connectors(raw: list[str] | None, health: dict[str, Any] | None) -> list[str]:
    selectable = set(selectable_connector_ids(health))
    selected = _unique_connector_ids(raw)
    return [item for item in selected if item in selectable]


def validate_worker_capture_connectors(raw: list[str] | None, health: dict[str, Any] | None) -> list[str]:
    """Keep only loaded connectors; reject when admin selected one the worker does not offer."""
    selected = _unique_connector_ids(raw)
    if not selected:
        raise ValueError("at least one capture connector is required")
    filtered = normalize_worker_capture_connectors(selected, health)
    if not filtered:
        raise ValueError("no loaded capture connectors on worker")
    dropped = [item for item in selected if item not in filtered]
    if dropped:
        raise ValueError(f"connectors not loaded on worker: {', '.join(dropped)}")
    return filtered

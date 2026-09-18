"""ASR/diarization model discovery, validation, and user/instance resolution."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstanceSettings, User, WorkerNode

ASR_ENGINE_IDS = frozenset({"whisper", "gigaam", "parakeet"})
DIARIZATION_ENGINE_IDS = frozenset({"nemo", "pyannote"})
SELECTABLE_ENGINE_STATUSES = frozenset({"loaded", "unavailable"})


def engine_kind(engine_id: str) -> str | None:
    if engine_id in ASR_ENGINE_IDS:
        return "asr"
    if engine_id in DIARIZATION_ENGINE_IDS:
        return "diarization"
    return None


def parse_worker_engines(health: dict[str, Any] | None) -> dict[str, list[dict[str, str]]]:
    """Split worker /health engines into ASR and diarization model lists."""
    raw = (health or {}).get("engines") or {}
    if not isinstance(raw, dict):
        raw = {}
    asr: list[dict[str, str]] = []
    diar: list[dict[str, str]] = []
    for engine_id, status in sorted(raw.items()):
        if not isinstance(engine_id, str) or not isinstance(status, str):
            continue
        kind = engine_kind(engine_id)
        if kind is None:
            continue
        item = {"id": engine_id, "status": status}
        if kind == "asr":
            asr.append(item)
        else:
            diar.append(item)
    return {"asr_models": asr, "diarization_models": diar}


def selectable_engine_ids(models: list[dict[str, str]]) -> list[str]:
    return [item["id"] for item in models if item.get("status") in SELECTABLE_ENGINE_STATUSES]


def normalize_model_ids(values: list[str] | None, *, allowed: set[str]) -> list[str] | None:
    if values is None:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        model_id = str(raw).strip()
        if not model_id or model_id in seen or model_id not in allowed:
            continue
        seen.add(model_id)
        out.append(model_id)
    return out


def worker_model_lists(node: WorkerNode) -> tuple[list[str] | None, list[str] | None]:
    asr = list(node.asr_models_json or []) or None
    diar = list(node.diarization_models_json or []) or None
    return asr, diar


def worker_offers_model(node: WorkerNode, *, asr: str, diar: str | None) -> bool:
    asr_models, diar_models = worker_model_lists(node)
    if asr_models is not None and asr not in asr_models:
        return False
    if diar:
        if diar_models is not None and diar not in diar_models:
            return False
    return True


def _node_model_lists(node: WorkerNode) -> tuple[list[str], list[str]]:
    node_asr, node_diar = worker_model_lists(node)
    parsed = parse_worker_engines(node.last_health)
    asr = node_asr if node_asr is not None else selectable_engine_ids(parsed["asr_models"])
    diar = node_diar if node_diar is not None else selectable_engine_ids(parsed["diarization_models"])
    return asr, diar


def dispatchable_pairs(nodes: list[WorkerNode]) -> list[dict[str, str | None]]:
    """ASR/diar pairs that at least one enabled transcribe worker offers together."""
    pairs: set[tuple[str, str | None]] = set()
    for node in nodes:
        if not node.enabled or node.type != "transcribe":
            continue
        asr_list, diar_list = _node_model_lists(node)
        for asr in asr_list:
            if diar_list:
                for diar in diar_list:
                    pairs.add((asr, diar))
            else:
                pairs.add((asr, None))
    return [
        {"asr_model": asr, "diarization_model": diar}
        for asr, diar in sorted(pairs, key=lambda item: (item[0], item[1] or ""))
    ]


def has_offering_worker(db: Session, *, asr: str, diar: str | None) -> bool:
    rows = db.scalars(
        select(WorkerNode).where(WorkerNode.type == "transcribe", WorkerNode.enabled.is_(True))
    ).all()
    return any(worker_offers_model(node, asr=asr, diar=diar) for node in rows)


def validate_dispatchable_models(db: Session, *, asr: str, diar: str | None) -> None:
    if not has_offering_worker(db, asr=asr, diar=diar):
        raise ValueError("dispatchable_models")


def aggregate_instance_models(db: Session) -> dict[str, Any]:
    rows = db.scalars(
        select(WorkerNode).where(WorkerNode.type == "transcribe", WorkerNode.enabled.is_(True))
    ).all()
    asr: set[str] = set()
    diar: set[str] = set()
    for node in rows:
        node_asr, node_diar = _node_model_lists(node)
        asr.update(node_asr)
        diar.update(node_diar)
    return {
        "asr_models": sorted(asr),
        "diarization_models": sorted(diar),
        "dispatchable_pairs": dispatchable_pairs(rows),
    }


def validate_instance_models(
    db: Session,
    *,
    asr_model: str | None = None,
    diarization_model: str | None = None,
) -> None:
    available = aggregate_instance_models(db)
    if asr_model is not None:
        asr = asr_model.strip()
        if asr and available["asr_models"] and asr not in available["asr_models"]:
            raise ValueError("asr_model")
    if diarization_model is not None:
        diar = diarization_model.strip() if isinstance(diarization_model, str) else ""
        if diar and available["diarization_models"] and diar not in available["diarization_models"]:
            raise ValueError("diarization_model")
    effective_asr = (asr_model or "").strip() or None
    effective_diar = diarization_model.strip() if isinstance(diarization_model, str) and diarization_model.strip() else None
    if effective_asr:
        validate_dispatchable_models(db, asr=effective_asr, diar=effective_diar)


def resolve_transcribe_models(user: User, settings: InstanceSettings) -> dict[str, Any]:
    user_asr = (user.asr_model or "").strip() or None
    user_diar_raw = user.diarization_model
    instance_asr = (settings.asr_model or "whisper").strip() or "whisper"
    instance_diar = settings.diarization_model
    if instance_diar is not None:
        instance_diar = instance_diar.strip() or None
    effective_asr = user_asr or instance_asr
    if user_diar_raw is not None:
        effective_diar = user_diar_raw.strip() or None
        diar_source = "user"
    else:
        effective_diar = instance_diar
        diar_source = "instance"
    return {
        "asr_model": effective_asr,
        "diarization_model": effective_diar,
        "asr_source": "user" if user_asr else "instance",
        "diarization_source": diar_source,
        "instance_asr_model": instance_asr,
        "instance_diarization_model": instance_diar,
    }

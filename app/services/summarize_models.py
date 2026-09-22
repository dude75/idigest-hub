"""Summarize LLM model discovery, validation, and user/instance resolution."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstanceSettings, User, WorkerNode
from app.services.summarize_model import summarize_model_from_health


def worker_summarize_model(node: WorkerNode) -> str | None:
    return summarize_model_from_health(node.last_health)


def worker_offers_summarize_model(node: WorkerNode, model: str) -> bool:
    offered = worker_summarize_model(node)
    if offered is None:
        return True
    return offered == model


def dispatchable_summarize_models(nodes: list[WorkerNode]) -> list[str]:
    models: set[str] = set()
    for node in nodes:
        if not node.enabled or node.type != "summarize":
            continue
        model = worker_summarize_model(node)
        if model:
            models.add(model)
    return sorted(models)


def has_offering_summarize_worker(db: Session, *, model: str) -> bool:
    rows = db.scalars(
        select(WorkerNode).where(WorkerNode.type == "summarize", WorkerNode.enabled.is_(True))
    ).all()
    return any(worker_offers_summarize_model(node, model) for node in rows)


def validate_dispatchable_summarize_model(db: Session, *, model: str) -> None:
    if not has_offering_summarize_worker(db, model=model):
        raise ValueError("dispatchable_summarize_model")


def aggregate_instance_summarize_models(db: Session) -> dict[str, Any]:
    rows = db.scalars(
        select(WorkerNode).where(WorkerNode.type == "summarize", WorkerNode.enabled.is_(True))
    ).all()
    return {"summarize_models": dispatchable_summarize_models(rows)}


def validate_instance_summarize_model(
    db: Session,
    *,
    summarize_model: str | None = None,
) -> None:
    available = aggregate_instance_summarize_models(db)
    if summarize_model is None:
        return
    model = summarize_model.strip()
    if not model:
        return
    if available["summarize_models"] and model not in available["summarize_models"]:
        raise ValueError("summarize_model")
    validate_dispatchable_summarize_model(db, model=model)


def resolve_summarize_models(
    user: User,
    settings: InstanceSettings,
    *,
    available: list[str] | None = None,
) -> dict[str, Any]:
    user_model = (user.summarize_model or "").strip() or None
    instance_model = (settings.summarize_model or "").strip() or None
    effective = user_model or instance_model
    if not effective and available:
        effective = available[0]
    return {
        "summarize_model": effective,
        "source": "user" if user_model else "instance",
        "instance_summarize_model": instance_model,
    }

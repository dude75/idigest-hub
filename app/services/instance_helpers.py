"""Shared helpers for instance admin routes."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import AuthContext
from app.errors import ErrorCode
from app.models import Organization, WorkerNode
from app.presenters import worker_public
from app.routers.instance._body import WorkerBody, WorkerProbeBody


def require_instance_admin(ctx: AuthContext) -> None:
    ctx.require_instance_admin()


def resolve_worker_token(body: WorkerProbeBody | WorkerBody, node: WorkerNode | None, db: Session, ctx: AuthContext) -> str:
    from app.crypto import decrypt_str

    if body.api_token:
        return body.api_token
    if node is not None:
        return decrypt_str(node.api_token_encrypted, db)
    ctx.raise_error(ErrorCode.validation_error)


def raise_worker_connect_error(ctx: AuthContext, exc: object) -> None:
    from app.services.workers import WorkerClientError

    if isinstance(exc, WorkerClientError) and exc.kind == "error_status" and exc.status_code == 401:
        ctx.raise_error(ErrorCode.worker_token_rejected)
    ctx.raise_error(ErrorCode.worker_unreachable)


def apply_transcribe_worker_models(
    node: WorkerNode,
    body: WorkerBody,
    *,
    probe_health: dict | None,
    ctx: AuthContext,
) -> None:
    from app.services.transcribe_models import normalize_model_ids, parse_worker_engines, selectable_engine_ids

    if body.type != "transcribe":
        node.asr_models_json = None
        node.diarization_models_json = None
        return
    if body.asr_models is None and body.diarization_models is None:
        return
    parsed = parse_worker_engines(probe_health or node.last_health)
    allowed_asr = set(selectable_engine_ids(parsed["asr_models"]))
    allowed_diar = set(selectable_engine_ids(parsed["diarization_models"]))
    asr = normalize_model_ids(body.asr_models, allowed=allowed_asr)
    diar = normalize_model_ids(body.diarization_models, allowed=allowed_diar)
    if body.asr_models is not None and not asr:
        ctx.raise_error(ErrorCode.validation_error)
    if body.diarization_models is not None and body.diarization_models and not diar:
        ctx.raise_error(ErrorCode.validation_error)
    if body.asr_models is not None:
        node.asr_models_json = asr
    if body.diarization_models is not None:
        node.diarization_models_json = diar


def apply_capture_worker_models(
    node: WorkerNode,
    body: WorkerBody,
    *,
    probe_health: dict | None,
    ctx: AuthContext,
) -> None:
    from app.services.capture_platforms import validate_worker_capture_connectors

    if body.type != "capture":
        node.capture_connectors_json = None
        return
    if body.capture_connectors is None:
        return
    health = probe_health or node.last_health
    try:
        filtered = validate_worker_capture_connectors(body.capture_connectors, health)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    node.capture_connectors_json = filtered


def org_count_for_tariff(db: Session, tariff_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff_id)) or 0)


def workers_list_payload(
    rows: list[WorkerNode],
    *,
    capture_connectors: list[str],
    import_max_concurrent: int,
) -> dict:
    from app.services.worker_availability import worker_is_dispatch_available, workers_availability_summary

    return {
        "items": [
            {
                **worker_public(row),
                "dispatch_available": worker_is_dispatch_available(
                    row, capture_connectors=capture_connectors
                ),
            }
            for row in rows
        ],
        "summary": workers_availability_summary(
            rows,
            capture_connectors=capture_connectors,
            import_max_concurrent=import_max_concurrent,
        ),
    }

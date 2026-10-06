from __future__ import annotations

from fastapi import BackgroundTasks, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import encrypt_str
from app.db import get_session
from app.deps import AuthContext, get_instance_settings, require_auth
from app.errors import ErrorCode
from app.models import WorkerNode, new_id
from app.presenters import worker_public
from app.routers.instance._body import WorkerBody, WorkerDeleteBody, WorkerProbeBody, WorkerRemediation
from app.routers.instance._router import router
from app.schemas.workers import (
    InstanceSummarizeModelsResponse,
    InstanceTranscribeModelsResponse,
    WorkerDeleteResponse,
    WorkerImpactResponse,
    WorkerListResponse,
    WorkerMutateResponse,
    WorkerProbeResponse,
    WorkerPublicResponse,
)
from app.services.instance_helpers import (
    apply_capture_worker_models,
    apply_transcribe_worker_models,
    raise_worker_connect_error,
    require_instance_admin,
    resolve_worker_token,
    workers_list_payload,
)
from app.timeutil import utcnow

@router.get("/workers", response_model=WorkerListResponse)
async def list_workers(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
    probe: bool = Query(True, description="Probe worker /health (set false for cached snapshot)"),
    refresh: bool = Query(False, description="Re-probe all enabled nodes, not only stale"),
) -> WorkerListResponse:
    require_instance_admin(ctx)
    rows = list(db.scalars(select(WorkerNode).order_by(WorkerNode.created_at)).all())
    from app.services.capture_platforms import allowed_connectors
    from app.services.dispatcher import refresh_nodes_health
    from app.services.import_platforms import normalize_import_max_concurrent

    if probe:
        targets = [
            row
            for row in rows
            if row.enabled and row.type in ("capture", "transcribe", "summarize")
        ]
        await refresh_nodes_health(db, targets, force=refresh)
        db.commit()

    settings = get_instance_settings(db)
    capture_connectors = allowed_connectors(settings)
    payload = workers_list_payload(
        rows,
        capture_connectors=capture_connectors,
        import_max_concurrent=normalize_import_max_concurrent(settings.import_max_concurrent),
    )
    return WorkerListResponse.model_validate(payload)


@router.get("/instance/transcribe-models", response_model=InstanceTranscribeModelsResponse)
def list_transcribe_models(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> InstanceTranscribeModelsResponse:
    from app.services.transcribe_models import aggregate_instance_models

    require_instance_admin(ctx)
    settings = get_instance_settings(db)
    available = aggregate_instance_models(db)
    return InstanceTranscribeModelsResponse.model_validate({**available, "default_asr_model": settings.asr_model, "default_diarization_model": settings.diarization_model})


@router.get("/instance/summarize-models", response_model=InstanceSummarizeModelsResponse)
def list_summarize_models(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> InstanceSummarizeModelsResponse:
    from app.services.summarize_models import aggregate_instance_summarize_models

    require_instance_admin(ctx)
    settings = get_instance_settings(db)
    available = aggregate_instance_summarize_models(db)
    return InstanceSummarizeModelsResponse.model_validate({**available, "default_summarize_model": settings.summarize_model})


@router.post("/workers/probe", response_model=WorkerProbeResponse)
async def probe_worker(
    body: WorkerProbeBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> WorkerProbeResponse:
    from app.services.transcribe_models import parse_worker_engines
    from app.services.workers import WorkerClientError, get_health_url, verify_worker_token

    require_instance_admin(ctx)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    node = db.get(WorkerNode, body.worker_id) if body.worker_id else None
    if body.worker_id and node is None:
        ctx.raise_error(ErrorCode.not_found)
    base_url = body.base_url.rstrip("/")
    token = resolve_worker_token(body, node, db, ctx)
    try:
        await verify_worker_token(base_url, token)
    except WorkerClientError as exc:
        raise_worker_connect_error(ctx, exc)
    status, health = await get_health_url(base_url)
    if status != 200:
        ctx.raise_error(ErrorCode.worker_unreachable)
    payload: dict = {"authorized": True, "health_status": status}
    if body.type == "transcribe":
        payload.update(parse_worker_engines(health))
    if body.type == "capture":
        from app.services.capture_platforms import parse_worker_connector_meta

        connectors = parse_worker_connector_meta(health)
        payload["connectors"] = [
            {"id": key, "status": info["status"], "label": info["label"]}
            for key, info in sorted(connectors.items())
        ]
    if body.type == "summarize":
        from app.services.summarize_models import summarize_model_from_health

        model = summarize_model_from_health(health)
        if model is not None:
            payload["summarize_model"] = model
    return WorkerProbeResponse.model_validate(payload)


@router.post("/workers", response_model=WorkerPublicResponse)
async def create_worker(
    body: WorkerBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> WorkerPublicResponse:
    from app.services.dispatcher import refresh_node_health
    from app.services.workers import WorkerClientError, verify_worker_token

    require_instance_admin(ctx)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    if not body.api_token:
        ctx.raise_error(ErrorCode.validation_error)
    base_url = body.base_url.rstrip("/")
    if body.type in {"transcribe", "capture"}:
        try:
            await verify_worker_token(base_url, body.api_token)
        except WorkerClientError as exc:
            raise_worker_connect_error(ctx, exc)
        if body.type == "transcribe" and not body.asr_models:
            ctx.raise_error(ErrorCode.validation_error)
        if body.type == "capture" and not body.capture_connectors:
            ctx.raise_error(ErrorCode.validation_error)
    now = utcnow()
    node = WorkerNode(
        id=new_id(),
        type=body.type,
        name=body.name.strip(),
        base_url=base_url,
        api_token_encrypted=encrypt_str(body.api_token, db),
        weight=max(body.weight, 1),
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    db.flush()
    if body.type == "transcribe":
        await refresh_node_health(db, node)
        apply_transcribe_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    if body.type == "capture":
        await refresh_node_health(db, node)
        apply_capture_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    return WorkerPublicResponse.model_validate(worker_public(node))


@router.patch("/workers/{worker_id}", response_model=WorkerMutateResponse)
async def patch_worker(
    worker_id: str,
    body: WorkerBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> WorkerMutateResponse:
    from app.services.dispatcher import refresh_node_health
    from app.services.workers import WorkerClientError, verify_worker_token

    require_instance_admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    from app.services.worker_impact import _with_worker_state

    nodes_before = [_with_worker_state(row) for row in db.scalars(select(WorkerNode)).all()]
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    base_url = body.base_url.rstrip("/")
    old_base_url = node.base_url
    token = resolve_worker_token(body, node, db, ctx)
    if body.type in {"transcribe", "capture"} and (body.api_token or base_url != old_base_url):
        try:
            await verify_worker_token(base_url, token)
        except WorkerClientError as exc:
            raise_worker_connect_error(ctx, exc)
    node.type = body.type
    node.name = body.name.strip()
    node.base_url = base_url
    if body.api_token:
        node.api_token_encrypted = encrypt_str(body.api_token, db)
    node.weight = max(body.weight, 1)
    node.enabled = body.enabled
    node.updated_at = utcnow()
    if body.type == "transcribe" and (
        body.api_token or base_url != old_base_url or body.asr_models is not None or body.diarization_models is not None
    ):
        await refresh_node_health(db, node)
        apply_transcribe_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    elif body.type == "capture":
        if body.capture_connectors is not None or body.api_token or base_url != old_base_url:
            await refresh_node_health(db, node)
        if body.capture_connectors is not None:
            apply_capture_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    if body.type != "transcribe":
        node.asr_models_json = None
        node.diarization_models_json = None
    if body.type != "capture":
        node.capture_connectors_json = None
    remediation_result = None
    if body.remediation is not None:
        nodes_after = list(db.scalars(select(WorkerNode)).all())
        try:
            remediation_result = _apply_worker_remediation(
                db,
                worker_type=body.type,
                after_nodes=nodes_after,
                before_nodes=nodes_before,
                focus_worker_id=node.id,
                remediation=body.remediation,
            )
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    _schedule_worker_remediation_tick(background_tasks, remediation_result)
    payload = worker_public(node)
    if remediation_result is not None:
        payload["remediation"] = remediation_result
    return WorkerMutateResponse.model_validate(payload)


@router.get("/workers/{worker_id}/delete-impact", response_model=WorkerImpactResponse)
def worker_delete_impact(
    worker_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> WorkerImpactResponse:
    from app.services.worker_impact import compute_worker_delete_impact

    require_instance_admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    return WorkerImpactResponse.model_validate(compute_worker_delete_impact(db, node))


@router.post("/workers/{worker_id}/change-impact", response_model=WorkerImpactResponse)
def worker_change_impact(
    worker_id: str,
    body: WorkerBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> WorkerImpactResponse:
    from app.services.worker_impact import compute_worker_change_impact

    require_instance_admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    if body.type == "capture":
        from app.services.capture_platforms import normalize_worker_capture_connectors
        from app.services.worker_impact import compute_worker_capture_change_impact

        connectors = (
            normalize_worker_capture_connectors(body.capture_connectors, node.last_health)
            if body.capture_connectors is not None
            else list(node.capture_connectors_json or [])
        )
        return WorkerImpactResponse.model_validate(
            compute_worker_capture_change_impact(
                db,
                node,
                enabled=body.enabled,
                capture_connectors=connectors,
            )
        )
    if body.type == "transcribe" and not body.asr_models:
        ctx.raise_error(ErrorCode.validation_error)
    return WorkerImpactResponse.model_validate(
        compute_worker_change_impact(
            db,
            node,
            type=body.type,
            enabled=body.enabled,
            asr_models=body.asr_models,
            diarization_models=body.diarization_models,
        )
    )


@router.delete("/workers/{worker_id}", response_model=WorkerDeleteResponse)
def delete_worker(
    worker_id: str,
    background_tasks: BackgroundTasks,
    body: WorkerDeleteBody | None = Body(default=None),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> WorkerDeleteResponse:
    require_instance_admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    all_nodes = list(db.scalars(select(WorkerNode)).all())
    after_nodes = [row for row in all_nodes if row.id != node.id]
    remediation = body.remediation if body else None
    remediation_result = None
    if remediation is not None:
        try:
            remediation_result = _apply_worker_remediation(
                db,
                worker_type=node.type,
                after_nodes=after_nodes,
                before_nodes=all_nodes,
                focus_worker_id=node.id,
                remediation=remediation,
            )
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    from app.services.worker_impact import prepare_worker_node_delete

    cleanup = prepare_worker_node_delete(db, node.id)
    db.delete(node)
    tick_payload = remediation_result if remediation_result else cleanup
    _schedule_worker_remediation_tick(background_tasks, tick_payload)
    payload: dict = {"status": "ok", "cleanup": cleanup}
    if remediation_result is not None:
        payload["remediation"] = remediation_result
    return WorkerDeleteResponse.model_validate(payload)


def _schedule_worker_remediation_tick(background_tasks: BackgroundTasks | None, remediation_result: dict | None) -> None:
    if background_tasks is None or not remediation_result:
        return
    if remediation_result.get("tasks_updated"):
        from app.services.dispatcher import schedule_locked_tick

        schedule_locked_tick(background_tasks, refresh_health=True, wait=False)


def _apply_worker_remediation(
    db: Session,
    *,
    worker_type: str,
    after_nodes: list[WorkerNode],
    before_nodes: list[WorkerNode],
    focus_worker_id: str,
    remediation: WorkerRemediation,
) -> dict:
    from app.services.worker_impact import (
        apply_capture_remediation,
        apply_summarize_remediation,
        apply_transcribe_remediation,
    )

    if worker_type == "transcribe":
        return apply_transcribe_remediation(
            db,
            after_nodes=after_nodes,
            before_nodes=before_nodes,
            focus_worker_id=focus_worker_id,
            asr_model=remediation.asr_model or "",
            diarization_model=remediation.diarization_model,
        )
    if worker_type == "summarize":
        if not remediation.summarize_model:
            raise ValueError("invalid_replacement")
        return apply_summarize_remediation(
            db,
            after_nodes=after_nodes,
            before_nodes=before_nodes,
            focus_worker_id=focus_worker_id,
            summarize_model=remediation.summarize_model,
        )
    if worker_type == "capture":
        if not remediation.capture_worker_id:
            raise ValueError("invalid_replacement")
        return apply_capture_remediation(
            db,
            after_nodes=after_nodes,
            focus_worker_id=focus_worker_id,
            replacement_worker_id=remediation.capture_worker_id,
        )
    raise ValueError("invalid_replacement")

"""Instance admin: воркеры, тарифы, настройки, орги, impersonate, статистика."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.crypto import encrypt_str
from app.db import get_session
from app.deps import (
    AuthContext,
    get_instance_settings,
    invalidate_session_ttl_cache,
    load_org_bundle,
    normalize_session_ttl_hours,
    require_auth,
)
from app.errors import ApiError, ErrorCode
from app.models import HiddenItem, Membership, Organization, Task, Tariff, UsageEvent, User, WorkerNode, new_id
from app.services.access import guard_last_org_admin, is_hidden
from app.money import parse_money
from app.presenters import org_public, tariff_public, user_public, worker_public
from app.routers.auth import revoke_user_auth, seed_default_tariff
from app.security import hash_password, random_password
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.services.audit import export_audit_csv, list_audit, write_audit
from app.services.export import attachment_response, safe_filename
from app.services.mfa import disable_totp, hub_local_auth_applies, totp_configured
from app.services.billing import signup_balance
from app.services.stats import org_ledger, parse_org_stats_range, usage_stats
from app.timeutil import utcnow

router = APIRouter()


class WorkerRemediation(BaseModel):
    asr_model: str | None = None
    diarization_model: str | None = None
    summarize_model: str | None = None
    capture_worker_id: str | None = None


class WorkerBody(BaseModel):
    type: str
    name: str = ""
    base_url: str
    api_token: str | None = None
    weight: int = 1
    enabled: bool = True
    asr_models: list[str] | None = None
    diarization_models: list[str] | None = None
    capture_connectors: list[str] | None = None
    remediation: WorkerRemediation | None = None


class WorkerDeleteBody(BaseModel):
    remediation: WorkerRemediation | None = None


class WorkerProbeBody(BaseModel):
    type: str
    base_url: str
    api_token: str | None = None
    worker_id: str | None = None


class TariffBody(BaseModel):
    name: str
    unlimited: bool = False
    available_on_signup: bool = False
    price_per_audio_sec: str = "0"
    price_per_summarize_job: str = "0"
    price_per_1k_summary_chars: str = "0"
    audio_retention_days: int = 0
    api_enabled: bool = True
    signup_credit: str = "0"
    max_upload_bytes: int = MAX_UPLOAD_BYTES_CAP


class WalletBody(BaseModel):
    delta: str


class SmtpTestBody(BaseModel):
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool | None = None


class SmtpTestSendBody(SmtpTestBody):
    to: str | None = None


class AgreementPreviewBody(BaseModel):
    text: str = ""


class SettingsPatch(BaseModel):
    allow_new_orgs: bool | None = None
    public_base_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool | None = None
    asr_model: str | None = None
    diarization_model: str | None = Field(default=None)
    summarize_model: str | None = None
    rate_limit_enabled: bool | None = None
    rate_limit_login_email: int | None = None
    rate_limit_login_ip: int | None = None
    rate_limit_login_global: int | None = None
    rate_limit_signup_email: int | None = None
    rate_limit_signup_ip: int | None = None
    rate_limit_signup_global: int | None = None
    rate_limit_reset_email: int | None = None
    rate_limit_reset_ip: int | None = None
    rate_limit_reset_global: int | None = None
    rate_limit_reset_confirm_ip: int | None = None
    rate_limit_reset_confirm_global: int | None = None
    rate_limit_setup_ip: int | None = None
    rate_limit_setup_global: int | None = None
    rate_limit_api_user: int | None = None
    rate_limit_api_ip: int | None = None
    rate_limit_api_global: int | None = None
    rate_limit_api_tasks_user: int | None = None
    rate_limit_api_tasks_ip: int | None = None
    rate_limit_public_link_ip: int | None = None
    rate_limit_public_link_global: int | None = None
    rate_limit_public_pin_ip: int | None = None
    import_enabled: bool | None = None
    import_allowed_extractors: list[str] | None = None
    capture_enabled: bool | None = None
    capture_allowed_connectors: list[str] | None = None
    download_proxy_url: str | None = None
    download_proxy_password: str | None = None
    download_proxy_enabled: bool | None = None
    download_cookies_path: str | None = None
    import_audio_bitrate_kbps: int | None = None
    import_max_concurrent: int | None = None
    session_ttl_hours: int | None = None
    date_time_format: str | None = None
    timezone: str | None = None
    user_agreement_text_en: str | None = None
    user_agreement_text_ru: str | None = None
    user_agreement_text_es: str | None = None
    personal_data_consent_text_en: str | None = None
    personal_data_consent_text_ru: str | None = None
    personal_data_consent_text_es: str | None = None
    privacy_policy_text_en: str | None = None
    privacy_policy_text_ru: str | None = None
    privacy_policy_text_es: str | None = None
    user_agreement_published: bool | None = None
    personal_data_consent_published: bool | None = None
    privacy_policy_published: bool | None = None
    landing_footer_text_en: str | None = None
    landing_footer_text_ru: str | None = None
    landing_footer_text_es: str | None = None
    landing_footer_published: bool | None = None


class CreateOrgBody(BaseModel):
    name: str
    tariff_id: str
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    locale: str = "en"
    is_personal: bool = False


class OrgTariffBody(BaseModel):
    tariff_id: str


class OrgDeleteBody(BaseModel):
    confirm_name: str


class OrgUserRoleBody(BaseModel):
    role: str


class ImpersonateBody(BaseModel):
    user_id: str


class BaseSkillBody(BaseModel):
    name: str
    body: str


def _admin(ctx: AuthContext) -> None:
    ctx.require_instance_admin()


def _resolve_worker_token(body: WorkerProbeBody | WorkerBody, node: WorkerNode | None, db: Session, ctx: AuthContext) -> str:
    from app.crypto import decrypt_str

    if body.api_token:
        return body.api_token
    if node is not None:
        return decrypt_str(node.api_token_encrypted, db)
    ctx.raise_error(ErrorCode.validation_error)


def _apply_transcribe_worker_models(
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


def _apply_capture_worker_models(
    node: WorkerNode,
    body: WorkerBody,
    *,
    probe_health: dict | None,
    ctx: AuthContext,
) -> None:
    from app.services.capture_platforms import normalize_allowed_connectors, selectable_connector_ids

    if body.type != "capture":
        node.capture_connectors_json = None
        return
    if body.capture_connectors is None:
        return
    allowed = set(selectable_connector_ids(probe_health or node.last_health))
    selected = normalize_allowed_connectors(body.capture_connectors)
    filtered = [item for item in selected if item in allowed]
    if body.capture_connectors is not None and not filtered:
        ctx.raise_error(ErrorCode.validation_error)
    node.capture_connectors_json = filtered


def _org_count(db: Session, tariff_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff_id)) or 0)


def _workers_list_payload(
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


@router.get("/workers")
async def list_workers(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
    probe: bool = Query(True, description="Probe worker /health (set false for cached snapshot)"),
    refresh: bool = Query(False, description="Re-probe all enabled nodes, not only stale"),
) -> dict:
    _admin(ctx)
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
    return _workers_list_payload(
        rows,
        capture_connectors=capture_connectors,
        import_max_concurrent=normalize_import_max_concurrent(settings.import_max_concurrent),
    )


@router.get("/instance/transcribe-models")
def list_transcribe_models(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.services.transcribe_models import aggregate_instance_models

    _admin(ctx)
    settings = get_instance_settings(db)
    available = aggregate_instance_models(db)
    return {
        **available,
        "default_asr_model": settings.asr_model,
        "default_diarization_model": settings.diarization_model,
    }


@router.get("/instance/summarize-models")
def list_summarize_models(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.services.summarize_models import aggregate_instance_summarize_models

    _admin(ctx)
    settings = get_instance_settings(db)
    available = aggregate_instance_summarize_models(db)
    return {
        **available,
        "default_summarize_model": settings.summarize_model,
    }


@router.post("/workers/probe")
async def probe_worker(
    body: WorkerProbeBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.transcribe_models import parse_worker_engines
    from app.services.workers import WorkerClientError, get_health_url, verify_worker_token

    _admin(ctx)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    node = db.get(WorkerNode, body.worker_id) if body.worker_id else None
    if body.worker_id and node is None:
        ctx.raise_error(ErrorCode.not_found)
    base_url = body.base_url.rstrip("/")
    token = _resolve_worker_token(body, node, db, ctx)
    try:
        await verify_worker_token(base_url, token)
    except WorkerClientError as exc:
        if exc.status_code == 401:
            ctx.raise_error(ErrorCode.validation_error)
        raise
    status, health = await get_health_url(base_url)
    if status != 200:
        ctx.raise_error(ErrorCode.validation_error)
    payload: dict = {"authorized": True, "health_status": status}
    if body.type == "transcribe":
        payload.update(parse_worker_engines(health))
    if body.type == "capture":
        from app.services.capture_platforms import parse_worker_connectors

        connectors = parse_worker_connectors(health)
        payload["connectors"] = [
            {"id": key, "status": value, "label": key}
            for key, value in sorted(connectors.items())
        ]
    if body.type == "summarize":
        from app.services.summarize_model import summarize_model_from_health

        model = summarize_model_from_health(health)
        if model is not None:
            payload["summarize_model"] = model
    return payload


@router.post("/workers")
async def create_worker(
    body: WorkerBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.services.dispatcher import refresh_node_health
    from app.services.workers import WorkerClientError, verify_worker_token

    _admin(ctx)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    if not body.api_token:
        ctx.raise_error(ErrorCode.validation_error)
    base_url = body.base_url.rstrip("/")
    if body.type in {"transcribe", "capture"}:
        try:
            await verify_worker_token(base_url, body.api_token)
        except WorkerClientError as exc:
            if exc.status_code == 401:
                ctx.raise_error(ErrorCode.validation_error)
            raise
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
        _apply_transcribe_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    if body.type == "capture":
        await refresh_node_health(db, node)
        _apply_capture_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    return worker_public(node)


@router.patch("/workers/{worker_id}")
async def patch_worker(
    worker_id: str,
    body: WorkerBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.dispatcher import refresh_node_health
    from app.services.workers import WorkerClientError, verify_worker_token

    _admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    from app.services.worker_impact import _with_worker_state

    nodes_before = [_with_worker_state(row) for row in db.scalars(select(WorkerNode)).all()]
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    base_url = body.base_url.rstrip("/")
    old_base_url = node.base_url
    token = _resolve_worker_token(body, node, db, ctx)
    if body.type in {"transcribe", "capture"} and (body.api_token or base_url != old_base_url):
        try:
            await verify_worker_token(base_url, token)
        except WorkerClientError as exc:
            if exc.status_code == 401:
                ctx.raise_error(ErrorCode.validation_error)
            raise
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
        _apply_transcribe_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
    elif body.type == "capture" and (
        body.api_token or base_url != old_base_url or body.capture_connectors is not None
    ):
        await refresh_node_health(db, node)
        _apply_capture_worker_models(node, body, probe_health=node.last_health, ctx=ctx)
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
    return payload


@router.get("/workers/{worker_id}/delete-impact")
def worker_delete_impact(
    worker_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.services.worker_impact import compute_worker_delete_impact

    _admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    return compute_worker_delete_impact(db, node)


@router.post("/workers/{worker_id}/change-impact")
def worker_change_impact(
    worker_id: str,
    body: WorkerBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.worker_impact import compute_worker_change_impact

    _admin(ctx)
    node = db.get(WorkerNode, worker_id)
    if node is None:
        ctx.raise_error(ErrorCode.not_found)
    if body.type not in {"transcribe", "summarize", "capture"}:
        ctx.raise_error(ErrorCode.validation_error)
    if body.type == "capture":
        from app.services.capture_platforms import normalize_allowed_connectors
        from app.services.worker_impact import compute_worker_capture_change_impact

        connectors = (
            normalize_allowed_connectors(body.capture_connectors)
            if body.capture_connectors is not None
            else list(node.capture_connectors_json or [])
        )
        return compute_worker_capture_change_impact(
            db,
            node,
            enabled=body.enabled,
            capture_connectors=connectors,
        )
    if body.type == "transcribe" and not body.asr_models:
        ctx.raise_error(ErrorCode.validation_error)
    return compute_worker_change_impact(
        db,
        node,
        type=body.type,
        enabled=body.enabled,
        asr_models=body.asr_models,
        diarization_models=body.diarization_models,
    )


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


@router.delete("/workers/{worker_id}")
def delete_worker(
    worker_id: str,
    background_tasks: BackgroundTasks,
    body: WorkerDeleteBody | None = Body(default=None),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
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
    payload: dict = {"status": "ok"}
    if remediation_result is not None:
        payload["remediation"] = remediation_result
    if cleanup["jitsi_hosts_removed"] or cleanup["tasks_updated"]:
        payload["cleanup"] = cleanup
    return payload


@router.get("/tariffs")
def list_tariffs(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    seed_default_tariff(db)
    rows = db.scalars(select(Tariff).order_by(Tariff.created_at)).all()
    return {"items": [tariff_public(row, _org_count(db, row.id)) for row in rows]}


def _apply_tariff(tariff: Tariff, body: TariffBody, ctx: AuthContext) -> None:
    if body.max_upload_bytes > MAX_UPLOAD_BYTES_CAP or body.max_upload_bytes <= 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.name = body.name.strip()
    tariff.unlimited = body.unlimited
    tariff.available_on_signup = body.available_on_signup and tariff.archived_at is None
    tariff.price_per_audio_sec = Decimal(body.price_per_audio_sec)
    tariff.price_per_summarize_job = parse_money(body.price_per_summarize_job)
    tariff.price_per_1k_summary_chars = Decimal(body.price_per_1k_summary_chars)
    if body.audio_retention_days < 0:
        ctx.raise_error(ErrorCode.validation_error)
    tariff.audio_retention_days = body.audio_retention_days
    tariff.api_enabled = body.api_enabled
    tariff.signup_credit = parse_money(body.signup_credit)
    tariff.max_upload_bytes = body.max_upload_bytes
    tariff.updated_at = utcnow()


@router.post("/tariffs")
def create_tariff(
    body: TariffBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    now = utcnow()
    tariff = Tariff(
        id=new_id(),
        name=body.name.strip(),
        unlimited=False,
        available_on_signup=False,
        max_upload_bytes=MAX_UPLOAD_BYTES_CAP,
        created_at=now,
        updated_at=now,
    )
    _apply_tariff(tariff, body, ctx)
    db.add(tariff)
    db.flush()
    write_audit(db, "tariff.create", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, 0)


@router.patch("/tariffs/{tariff_id}")
def patch_tariff(
    tariff_id: str,
    body: TariffBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    _apply_tariff(tariff, body, ctx)
    write_audit(db, "tariff.update", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.post("/tariffs/{tariff_id}/archive")
def archive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = utcnow()
    tariff.available_on_signup = False
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.archive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.post("/tariffs/{tariff_id}/unarchive")
def unarchive_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    tariff.archived_at = None
    tariff.updated_at = utcnow()
    write_audit(db, "tariff.unarchive", ctx, {"tariff_id": tariff.id})
    return tariff_public(tariff, _org_count(db, tariff.id))


@router.delete("/tariffs/{tariff_id}")
def delete_tariff(
    tariff_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    total = int(db.scalar(select(func.count()).select_from(Tariff)) or 0)
    if total <= 1:
        ctx.raise_error(ErrorCode.last_tariff)
    if _org_count(db, tariff.id) > 0:
        ctx.raise_error(ErrorCode.tariff_in_use)
    db.delete(tariff)
    return {"status": "ok"}


@router.post("/orgs/{org_id}/wallet")
def wallet_delta(
    org_id: str,
    body: WalletBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    delta = parse_money(body.delta)
    org.balance = parse_money(Decimal(org.balance) + delta)
    org.updated_at = utcnow()
    write_audit(db, "wallet.delta", ctx, {"org_id": org.id, "delta": str(delta)})
    return org_public(org)


@router.get("/instance/settings")
def get_settings_ep(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    _admin(ctx)
    s = get_instance_settings(db)
    from app.services.import_platforms import (
        DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
        admin_platforms,
        normalize_import_max_concurrent,
    )
    from app.services.summarize_models import aggregate_instance_summarize_models
    from app.services.transcribe_models import aggregate_instance_models

    proxy_url = s.download_proxy_url or ""
    bitrate = s.import_audio_bitrate_kbps
    if bitrate is None:
        bitrate = DEFAULT_IMPORT_AUDIO_BITRATE_KBPS
    return {
        "allow_new_orgs": s.allow_new_orgs,
        "public_base_url": s.public_base_url,
        "smtp_host": s.smtp_host,
        "smtp_port": s.smtp_port,
        "smtp_user": s.smtp_user,
        "smtp_configured": bool(s.smtp_host and s.smtp_from),
        "smtp_password_configured": bool((s.smtp_password_encrypted or "").strip()),
        "smtp_from": s.smtp_from,
        "smtp_tls": s.smtp_tls,
        "asr_model": s.asr_model,
        "diarization_model": s.diarization_model,
        "summarize_model": s.summarize_model,
        **aggregate_instance_models(db),
        **aggregate_instance_summarize_models(db),
        "import_enabled": s.import_enabled,
        "import_platforms": admin_platforms(s),
        "capture_enabled": s.capture_enabled,
        "capture_connectors": __import__(
            "app.services.capture_platforms", fromlist=["admin_connectors"]
        ).admin_connectors(s),
        "download_proxy_url": s.download_proxy_url,
        "download_proxy_configured": bool(proxy_url.strip()),
        "download_proxy_enabled": s.download_proxy_enabled,
        "download_cookies_path": s.download_cookies_path,
        "import_audio_bitrate_kbps": bitrate,
        "import_max_concurrent": normalize_import_max_concurrent(s.import_max_concurrent),
        "session_ttl_hours": s.session_ttl_hours,
        "date_time_format": s.date_time_format,
        "timezone": s.timezone,
        "user_agreement_text_en": s.user_agreement_text_en,
        "user_agreement_text_ru": s.user_agreement_text_ru,
        "user_agreement_text_es": s.user_agreement_text_es,
        "user_agreement_version": s.user_agreement_version,
        "user_agreement_published": s.user_agreement_published,
        "personal_data_consent_text_en": s.personal_data_consent_text_en,
        "personal_data_consent_text_ru": s.personal_data_consent_text_ru,
        "personal_data_consent_text_es": s.personal_data_consent_text_es,
        "personal_data_consent_version": s.personal_data_consent_version,
        "personal_data_consent_published": s.personal_data_consent_published,
        "privacy_policy_text_en": s.privacy_policy_text_en,
        "privacy_policy_text_ru": s.privacy_policy_text_ru,
        "privacy_policy_text_es": s.privacy_policy_text_es,
        "privacy_policy_version": s.privacy_policy_version,
        "privacy_policy_published": s.privacy_policy_published,
        "landing_footer_text_en": s.landing_footer_text_en,
        "landing_footer_text_ru": s.landing_footer_text_ru,
        "landing_footer_text_es": s.landing_footer_text_es,
        "landing_footer_published": s.landing_footer_published,
        **rate_limits_public(s),
    }


@router.post("/instance/settings/agreement/preview")
def preview_agreement_markdown(
    body: AgreementPreviewBody,
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    from app.services.user_agreement import normalize_agreement_markdown

    return {"text": normalize_agreement_markdown(body.text.strip())}


@router.get("/instance/legal-documents/{key}/versions")
def list_legal_document_versions_ep(
    key: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    from app.services.user_agreement import LEGAL_DOCUMENT_KEYS, legal_document_version_summary, list_legal_document_versions

    if key not in LEGAL_DOCUMENT_KEYS:
        ctx.raise_error(ErrorCode.not_found)
    rows = list_legal_document_versions(db, key)  # type: ignore[arg-type]
    author_ids = {row.created_by_user_id for row in rows if row.created_by_user_id}
    emails: dict[str, str] = {}
    if author_ids:
        for user in db.scalars(select(User).where(User.id.in_(author_ids))).all():
            emails[user.id] = user.email
    return {
        "key": key,
        "items": [
            legal_document_version_summary(row, author_email=emails.get(row.created_by_user_id or ""))
            for row in rows
        ],
    }


@router.get("/instance/legal-documents/{key}/versions/{version}")
def get_legal_document_version_ep(
    key: str,
    version: int,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    from app.services.user_agreement import LEGAL_DOCUMENT_KEYS, get_legal_document_version, legal_document_version_detail

    if key not in LEGAL_DOCUMENT_KEYS:
        ctx.raise_error(ErrorCode.not_found)
    if version <= 0:
        ctx.raise_error(ErrorCode.not_found)
    row = get_legal_document_version(db, key, version)  # type: ignore[arg-type]
    if row is None:
        ctx.raise_error(ErrorCode.not_found)
    author_email = None
    if row.created_by_user_id:
        author = db.get(User, row.created_by_user_id)
        author_email = author.email if author else None
    return legal_document_version_detail(row, author_email=author_email)


@router.patch("/instance/settings")
def patch_settings(
    body: SettingsPatch, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    s = get_instance_settings(db)
    data = body.model_dump(exclude_unset=True)
    if "diarization_model" in data:
        value = data["diarization_model"]
        s.diarization_model = value.strip() if isinstance(value, str) and value.strip() else None
        data.pop("diarization_model")
    if "smtp_password" in data:
        password = data.pop("smtp_password")
        if password:
            s.smtp_password_encrypted = encrypt_str(password, db)
    if "download_proxy_url" in data:
        from app.services.import_platforms import normalize_download_proxy_url

        raw_proxy = data.get("download_proxy_url")
        if raw_proxy is None or not str(raw_proxy).strip():
            s.download_proxy_url = None
            s.download_proxy_enabled = False
        else:
            try:
                s.download_proxy_url = normalize_download_proxy_url(str(raw_proxy))
            except ValueError:
                ctx.raise_error(ErrorCode.validation_error)
        data.pop("download_proxy_url", None)
    if "download_proxy_enabled" in data:
        enabled = bool(data.pop("download_proxy_enabled"))
        if enabled and not (s.download_proxy_url or "").strip():
            ctx.raise_error(ErrorCode.validation_error)
        s.download_proxy_enabled = enabled
    if "download_proxy_password" in data:
        proxy_password = data.pop("download_proxy_password")
        if proxy_password:
            s.download_proxy_password_encrypted = encrypt_str(proxy_password, db)
    if "import_audio_bitrate_kbps" in data:
        from app.services.import_platforms import normalize_import_audio_bitrate_kbps

        s.import_audio_bitrate_kbps = normalize_import_audio_bitrate_kbps(data.pop("import_audio_bitrate_kbps"))
    if "import_max_concurrent" in data:
        from app.services.import_platforms import normalize_import_max_concurrent

        s.import_max_concurrent = normalize_import_max_concurrent(data.pop("import_max_concurrent"))
    if "import_allowed_extractors" in data:
        from app.services.import_platforms import validate_allowed_extractors

        raw = data.pop("import_allowed_extractors")
        try:
            s.import_allowed_extractors_json = validate_allowed_extractors(list(raw or []))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "capture_allowed_connectors" in data:
        from app.services.capture_platforms import validate_allowed_connectors

        raw = data.pop("capture_allowed_connectors")
        try:
            s.capture_allowed_connectors_json = validate_allowed_connectors(list(raw or []))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "session_ttl_hours" in data:
        try:
            s.session_ttl_hours = normalize_session_ttl_hours(data.pop("session_ttl_hours"))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "date_time_format" in data:
        from app.datetime_format import DATE_TIME_FORMATS, normalize_date_time_format

        fmt = data.pop("date_time_format")
        if fmt is not None and str(fmt).strip() not in DATE_TIME_FORMATS:
            ctx.raise_error(ErrorCode.validation_error)
        s.date_time_format = normalize_date_time_format(str(fmt) if fmt is not None else None)
    if "timezone" in data:
        from app.datetime_format import normalize_timezone

        tz = data.pop("timezone")
        try:
            s.timezone = normalize_timezone(str(tz) if tz is not None else None)
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    from app.services.user_agreement import apply_legal_documents_patch

    apply_legal_documents_patch(s, data, db=db, created_by_user_id=ctx.user.id)
    for key, value in data.items():
        setattr(s, key, value)
    if "asr_model" in body.model_dump(exclude_unset=True) or "diarization_model" in body.model_dump(exclude_unset=True):
        from app.services.transcribe_models import validate_instance_models

        try:
            validate_instance_models(db, asr_model=s.asr_model, diarization_model=s.diarization_model)
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "summarize_model" in body.model_dump(exclude_unset=True):
        from app.services.summarize_models import validate_instance_summarize_model

        try:
            validate_instance_summarize_model(db, summarize_model=s.summarize_model)
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    invalidate_rate_limit_cache()
    invalidate_session_ttl_cache()
    return get_settings_ep(db, ctx)


def _resolve_smtp_test_params(body: SmtpTestBody, db: Session, ctx: AuthContext):
    from app.services.mail import resolve_smtp_params

    settings = get_instance_settings(db)
    try:
        return resolve_smtp_params(
            settings,
            db,
            host=body.smtp_host,
            port=body.smtp_port,
            user=body.smtp_user,
            password=body.smtp_password or None,
            from_addr=body.smtp_from,
            tls=body.smtp_tls,
        )
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)


def _smtp_test_error(exc: Exception) -> None:
    from app.services.mail import log

    log.warning("smtp test failed: %s", exc)
    raise ApiError(ErrorCode.validation_error, str(exc)) from exc


@router.post("/instance/smtp/test-connection")
def smtp_test_connection(
    body: SmtpTestBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.mail import check_smtp_connection

    _admin(ctx)
    params = _resolve_smtp_test_params(body, db, ctx)
    try:
        check_smtp_connection(params)
    except Exception as exc:
        _smtp_test_error(exc)
    return {"status": "ok"}


@router.post("/instance/smtp/test-send")
def smtp_test_send(
    body: SmtpTestSendBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.services.mail import send_smtp_message

    _admin(ctx)
    to_email = (body.to or ctx.user.email or "").strip()
    if not to_email:
        ctx.raise_error(ErrorCode.validation_error)
    params = _resolve_smtp_test_params(body, db, ctx)
    try:
        send_smtp_message(
            params,
            to_email,
            "idigest-hub SMTP test",
            "This is a test message from idigest-hub SMTP settings.",
        )
    except Exception as exc:
        _smtp_test_error(exc)
    return {"status": "ok", "to": to_email}


def _count_hidden_orgs(ctx: AuthContext, db: Session) -> int:
    rows = db.scalars(select(Organization.id)).all()
    return sum(1 for org_id in rows if is_hidden(db, ctx.user.id, "org", org_id))


@router.get("/orgs")
def list_orgs(
    include_hidden: bool = False,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    settings = get_instance_settings(db)
    rows = db.scalars(select(Organization).options(joinedload(Organization.tariff)).order_by(Organization.created_at)).all()
    items = []
    for org in rows:
        hidden = is_hidden(db, ctx.user.id, "org", org.id)
        if not include_hidden and hidden:
            continue
        payload = org_public(org)
        payload["hidden"] = hidden
        members = db.scalars(select(Membership).where(Membership.org_id == org.id)).all()
        payload["members"] = []
        for membership in members:
            user = db.get(User, membership.user_id)
            if user:
                payload["members"].append(user_public(user, membership.role, instance_settings=settings))
        items.append(payload)
    return {"items": items, "hidden_count": _count_hidden_orgs(ctx, db)}


@router.post("/orgs")
def create_org(
    body: CreateOrgBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    name = body.name.strip()
    if not name:
        ctx.raise_error(ErrorCode.validation_error)
    tariff = db.get(Tariff, body.tariff_id)
    if tariff is None or tariff.archived_at is not None:
        ctx.raise_error(ErrorCode.not_found)
    email = str(body.admin_email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        ctx.raise_error(ErrorCode.email_taken)
    now = utcnow()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(body.admin_password),
        auth_provider="local",
        locale=body.locale,
        password_changed_at=now,
        must_change_password=True,
        is_instance_admin=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    org = Organization(
        id=new_id(),
        name=name,
        is_personal=body.is_personal,
        tariff_id=tariff.id,
        password_ttl_days=0,
        balance=signup_balance(tariff),
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    db.flush()
    db.add(Membership(id=new_id(), user_id=user.id, org_id=org.id, role="org_admin"))
    write_audit(db, "org.create", ctx, {"org_id": org.id, "admin_user_id": user.id, "tariff_id": tariff.id})
    org.tariff = tariff
    payload = org_public(org)
    payload["members"] = [user_public(user, "org_admin")]
    return payload


@router.post("/orgs/{org_id}/delete")
def delete_org(
    org_id: str,
    body: OrgDeleteBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    if body.confirm_name.strip() != org.name:
        ctx.raise_error(ErrorCode.validation_error)
    from app.services.org_delete import delete_organization

    write_audit(
        db,
        "org.delete",
        ctx,
        {"org_id": org.id, "name": org.name, "is_personal": org.is_personal},
    )
    delete_organization(db, org)
    return {"status": "ok"}


@router.post("/orgs/{org_id}/hide")
def hide_org(
    org_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    if not is_hidden(db, ctx.user.id, "org", org.id):
        db.add(HiddenItem(id=new_id(), user_id=ctx.user.id, object_type="org", object_id=org.id))
    return {"status": "ok"}


@router.post("/orgs/{org_id}/unhide")
def unhide_org(
    org_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    hidden = db.scalar(
        select(HiddenItem).where(
            HiddenItem.user_id == ctx.user.id,
            HiddenItem.object_type == "org",
            HiddenItem.object_id == org.id,
        )
    )
    if hidden:
        db.delete(hidden)
    return {"status": "ok"}


@router.get("/orgs/{org_id}/ledger")
def org_ledger_ep(
    org_id: str,
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    if org is None:
        ctx.raise_error(ErrorCode.not_found)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    return org_ledger(
        db,
        org_id,
        start=start,
        end=end,
        user_id=(user_id or "").strip() or None,
        kind=(kind or "").strip() or None,
    )


@router.post("/orgs/{org_id}/users/{user_id}/reset-password")
def reset_org_admin_password(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None or membership.role != "org_admin":
        ctx.raise_error(ErrorCode.forbidden)
    password = random_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    user.updated_at = utcnow()
    revoke_user_auth(db, user.id)
    write_audit(db, "user.password_reset", ctx, {"user_id": user.id, "org_id": org.id})
    return {"status": "ok", "password": password}


@router.post("/orgs/{org_id}/users/{user_id}/reset-mfa")
def reset_org_user_mfa(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None:
        ctx.raise_error(ErrorCode.forbidden)
    if not hub_local_auth_applies(user=user, org=org, membership=membership):
        ctx.raise_error(ErrorCode.forbidden)
    if not totp_configured(user):
        ctx.raise_error(ErrorCode.validation_error)
    disable_totp(db, user)
    revoke_user_auth(db, user.id)
    write_audit(db, "user.mfa.reset", ctx, {"user_id": user.id, "org_id": org.id})
    return user_public(user, membership.role)


@router.patch("/orgs/{org_id}/users/{user_id}")
def patch_org_user_role(
    org_id: str,
    user_id: str,
    body: OrgUserRoleBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    membership = db.scalar(
        select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if org is None or membership is None or user is None:
        ctx.raise_error(ErrorCode.not_found)
    if user.is_instance_admin or user.disabled_at is not None:
        ctx.raise_error(ErrorCode.forbidden)
    if body.role not in {"org_admin", "org_member"}:
        ctx.raise_error(ErrorCode.validation_error)
    if membership.role == "org_admin" and body.role == "org_member":
        guard_last_org_admin(db, org.id, user_id, ctx.locale)
    membership.role = body.role
    write_audit(
        db,
        "user.role",
        ctx,
        {"user_id": user.id, "org_id": org.id, "role": body.role, "by": "instance_admin"},
    )
    settings = get_instance_settings(db)
    return user_public(user, membership.role, instance_settings=settings)


@router.patch("/orgs/{org_id}/tariff")
def assign_org_tariff(
    org_id: str,
    body: OrgTariffBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    org = db.get(Organization, org_id)
    tariff = db.get(Tariff, body.tariff_id)
    if org is None or tariff is None:
        ctx.raise_error(ErrorCode.not_found)
    org.tariff_id = tariff.id
    org.updated_at = utcnow()
    write_audit(db, "org.tariff", ctx, {"org_id": org.id, "tariff_id": tariff.id})
    db.refresh(org)
    org.tariff = tariff
    return org_public(org)


def _actor_is_org_admin(db: Session, ctx: AuthContext) -> tuple[Organization, Membership] | None:
    org, membership = load_org_bundle(db, ctx.actor)
    if org is None or membership is None or membership.role != "org_admin":
        return None
    return org, membership


@router.post("/impersonate")
def impersonate(
    body: ImpersonateBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    if ctx.session is None or ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    org_scope: str | None = None
    if ctx.is_instance_admin:
        pass
    elif ctx.is_org_admin and ctx.org is not None:
        org_scope = ctx.org.id
    else:
        ctx.raise_error(ErrorCode.forbidden)
    target = db.get(User, body.user_id)
    if target is None or target.is_instance_admin or target.disabled_at is not None:
        ctx.raise_error(ErrorCode.not_found)
    if org_scope is not None:
        if target.id == ctx.actor.id:
            ctx.raise_error(ErrorCode.forbidden)
        membership = db.scalar(
            select(Membership).where(Membership.user_id == target.id, Membership.org_id == org_scope)
        )
        if membership is None:
            ctx.raise_error(ErrorCode.not_found)
    ctx.session.impersonate_user_id = target.id
    write_audit(db, "impersonate.start", ctx, {"user_id": target.id}, on_behalf_of=target.id)
    return {"status": "ok"}


@router.delete("/impersonate")
def stop_impersonate(
    db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    if ctx.session is None:
        ctx.raise_error(ErrorCode.forbidden)
    if not ctx.actor.is_instance_admin and _actor_is_org_admin(db, ctx) is None:
        ctx.raise_error(ErrorCode.forbidden)
    write_audit(db, "impersonate.stop", ctx)
    ctx.session.impersonate_user_id = None
    return {"status": "ok"}


@router.get("/instance/audit")
def audit_log(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    user_filter = (user_id or "").strip() or None
    if user_filter and db.get(User, user_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    items, total = list_audit(
        db,
        start=start,
        end=end,
        org_id=org_filter,
        user_id=user_filter,
        action=(action or "").strip() or None,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/instance/audit/export")
def audit_log_export(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    _admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    user_filter = (user_id or "").strip() or None
    if user_filter and db.get(User, user_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    content = export_audit_csv(
        db,
        start=start,
        end=end,
        org_id=org_filter,
        user_id=user_filter,
        action=(action or "").strip() or None,
    )
    from_part = safe_filename(from_day or "start", fallback="start")
    to_part = safe_filename(to_day or "end", fallback="end")
    filename = f"audit-{from_part}_{to_part}.csv"
    return attachment_response(content, filename, "text/csv; charset=utf-8")


@router.get("/instance/stats")
def stats(
    from_day: str | None = Query(None, alias="from"),
    to_day: str | None = Query(None, alias="to"),
    org_id: str | None = None,
    user_id: str | None = None,
    kind: str | None = None,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    _admin(ctx)
    try:
        start, end = parse_org_stats_range(from_day, to_day)
    except ValueError:
        ctx.raise_error(ErrorCode.validation_error)
    org_filter = (org_id or "").strip() or None
    if org_filter and db.get(Organization, org_filter) is None:
        ctx.raise_error(ErrorCode.not_found)
    usage = usage_stats(
        db,
        org_id=org_filter,
        start=start,
        end=end,
        user_id=(user_id or "").strip() or None,
        kind=(kind or "").strip() or None,
    )
    queued = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "queued")) or 0)
    running = int(db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0)
    orgs = int(db.scalar(select(func.count()).select_from(Organization)) or 0)
    users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    from app.deps import get_instance_settings
    from app.services.download_proxy_health import download_proxy_card_status

    settings = get_instance_settings(db)
    return {
        "orgs": orgs,
        "users": users,
        "tasks_queued": queued,
        "tasks_running": running,
        "download_proxy_status": download_proxy_card_status(settings, db),
        **usage,
        "usage_total": usage["total_amount"],
    }


@router.get("/skills/base")
def list_base_skills(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    rows = db.scalars(select(Skill).where(Skill.scope == "base").order_by(Skill.name)).all()
    return {"items": [skill_public(row) for row in rows]}


@router.post("/skills/base")
def create_base_skill(
    body: BaseSkillBody, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    now = utcnow()
    skill = Skill(
        id=new_id(),
        scope="base",
        name=body.name.strip(),
        body=body.body,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    return skill_public(skill)


@router.patch("/skills/base/{skill_id}")
def patch_base_skill(
    skill_id: str,
    body: BaseSkillBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    from app.models import Skill
    from app.presenters import skill_public

    _admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    skill.name = body.name.strip()
    skill.body = body.body
    skill.updated_at = utcnow()
    return skill_public(skill)


@router.delete("/skills/base/{skill_id}")
def delete_base_skill(
    skill_id: str, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> dict:
    from app.models import Skill

    _admin(ctx)
    skill = db.get(Skill, skill_id)
    if skill is None or skill.scope != "base":
        ctx.raise_error(ErrorCode.not_found)
    db.delete(skill)
    return {"status": "ok"}

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import encrypt_str
from app.db import get_session
from app.deps import (
    AuthContext,
    get_instance_settings,
    invalidate_session_ttl_cache,
    normalize_session_ttl_hours,
    require_auth,
)
from app.errors import ApiError, ErrorCode
from app.models import User
from app.rate_limit import invalidate_rate_limit_cache, rate_limits_public
from app.routers.instance._body import AgreementPreviewBody, SettingsPatch, SmtpTestBody, SmtpTestSendBody
from app.routers.instance._router import router
from app.schemas.common import OkStatusResponse
from app.schemas.instance_settings import (
    AgreementPreviewResponse,
    InstanceSettingsResponse,
    LegalDocumentVersionDetailResponse,
    LegalDocumentVersionListResponse,
    LegalDocumentVersionSummary,
    SmtpTestSendResponse,
)
from app.services.instance_helpers import require_instance_admin

def resolve_smtp_test_params(body: SmtpTestBody, db: Session, ctx: AuthContext):
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


def smtp_test_error(exc: Exception) -> None:
    from app.services.mail import log

    log.warning("smtp test failed: %s", exc)
    raise ApiError(ErrorCode.validation_error, str(exc)) from exc

@router.get("/instance/settings", response_model=InstanceSettingsResponse)
def get_settings_ep(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> InstanceSettingsResponse:
    require_instance_admin(ctx)
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
    payload = {
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
        ).admin_connectors(s, db),
        "download_proxy_url": s.download_proxy_url,
        "download_proxy_configured": bool(proxy_url.strip()),
        "download_proxy_enabled": s.download_proxy_enabled,
        "download_cookies_path": s.download_cookies_path,
        "import_audio_bitrate_kbps": bitrate,
        "import_max_concurrent": normalize_import_max_concurrent(s.import_max_concurrent),
        "session_ttl_hours": s.session_ttl_hours,
        "task_history_retention_days": s.task_history_retention_days,
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
    return InstanceSettingsResponse.model_validate(payload)


@router.post("/instance/settings/agreement/preview", response_model=AgreementPreviewResponse)
def preview_agreement_markdown(
    body: AgreementPreviewBody,
    ctx: AuthContext = Depends(require_auth),
) -> AgreementPreviewResponse:
    require_instance_admin(ctx)
    from app.services.user_agreement import normalize_agreement_markdown

    return AgreementPreviewResponse(text=normalize_agreement_markdown(body.text.strip()))


@router.get("/instance/legal-documents/{key}/versions", response_model=LegalDocumentVersionListResponse)
def list_legal_document_versions_ep(
    key: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> LegalDocumentVersionListResponse:
    require_instance_admin(ctx)
    from app.services.user_agreement import LEGAL_DOCUMENT_KEYS, legal_document_version_summary, list_legal_document_versions

    if key not in LEGAL_DOCUMENT_KEYS:
        ctx.raise_error(ErrorCode.not_found)
    rows = list_legal_document_versions(db, key)  # type: ignore[arg-type]
    author_ids = {row.created_by_user_id for row in rows if row.created_by_user_id}
    emails: dict[str, str] = {}
    if author_ids:
        for user in db.scalars(select(User).where(User.id.in_(author_ids))).all():
            emails[user.id] = user.email
    return LegalDocumentVersionListResponse(
        key=key,
        items=[
            LegalDocumentVersionSummary.model_validate(
                legal_document_version_summary(row, author_email=emails.get(row.created_by_user_id or ""))
            )
            for row in rows
        ],
    )


@router.get("/instance/legal-documents/{key}/versions/{version}", response_model=LegalDocumentVersionDetailResponse)
def get_legal_document_version_ep(
    key: str,
    version: int,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> LegalDocumentVersionDetailResponse:
    require_instance_admin(ctx)
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
    return LegalDocumentVersionDetailResponse.model_validate(legal_document_version_detail(row, author_email=author_email))


@router.patch("/instance/settings", response_model=InstanceSettingsResponse)
def patch_settings(
    body: SettingsPatch, db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)
) -> InstanceSettingsResponse:
    require_instance_admin(ctx)
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
            s.capture_allowed_connectors_json = validate_allowed_connectors(db, s, list(raw or []))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "session_ttl_hours" in data:
        try:
            s.session_ttl_hours = normalize_session_ttl_hours(data.pop("session_ttl_hours"))
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "task_history_retention_days" in data:
        days = data.pop("task_history_retention_days")
        if days is None or int(days) < 0:
            ctx.raise_error(ErrorCode.validation_error)
        s.task_history_retention_days = int(days)
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
    return get_settings_ep(db, ctx)  # InstanceSettingsResponse


def resolve_smtp_test_params(body: SmtpTestBody, db: Session, ctx: AuthContext):
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


def smtp_test_error(exc: Exception) -> None:
    from app.services.mail import log

    log.warning("smtp test failed: %s", exc)
    raise ApiError(ErrorCode.validation_error, str(exc)) from exc


@router.post("/instance/smtp/test-connection", response_model=OkStatusResponse)
def smtp_test_connection(
    body: SmtpTestBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> OkStatusResponse:
    from app.services.mail import check_smtp_connection

    require_instance_admin(ctx)
    params = resolve_smtp_test_params(body, db, ctx)
    try:
        check_smtp_connection(params)
    except Exception as exc:
        smtp_test_error(exc)
    return OkStatusResponse()


@router.post("/instance/smtp/test-send", response_model=SmtpTestSendResponse)
def smtp_test_send(
    body: SmtpTestSendBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> SmtpTestSendResponse:
    from app.services.mail import send_smtp_message

    require_instance_admin(ctx)
    to_email = (body.to or ctx.user.email or "").strip()
    if not to_email:
        ctx.raise_error(ErrorCode.validation_error)
    params = resolve_smtp_test_params(body, db, ctx)
    try:
        send_smtp_message(
            params,
            to_email,
            "idigest-hub SMTP test",
            "This is a test message from idigest-hub SMTP settings.",
        )
    except Exception as exc:
        smtp_test_error(exc)
    return SmtpTestSendResponse(to=to_email)

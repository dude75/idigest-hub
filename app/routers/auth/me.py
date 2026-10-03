from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.constants import COOKIE_NAME
from app.cookies import clear_auth_cookies, issue_auth_cookies, oauth_embedded_session_samesite
from app.db import get_session
from app.deps import AuthContext, abort, get_instance_settings, locale_from_request, optional_auth, require_auth, session_ttl_sec_from_db
from app.errors import ErrorCode
from app.models import (
    ApiToken,
    InstanceSettings,
    Membership,
    Organization,
    PasswordResetToken,
    Session as AuthSession,
    Tariff,
    User,
    new_id,
)
from app.presenters import org_public, tariff_public, token_public, user_public
from app.routers.auth._body import AccountDeleteBody, MePatchBody
from app.routers.auth._helpers import _allowed_default_routes, _default_route, _locale
from app.routers.auth._router import router
from app.security import hash_password, hash_secret, new_api_token, new_reset_token, verify_password
from app.services.audit import write_audit
from app.services.auth_helpers import create_session, me_payload, me_with_csrf, public_base_url, revoke_user_auth, seed_default_tariff, sso_login_redirect
from app.timeutil import utcnow

from fastapi import Response
from app.schemas.auth_api import AccountDeletePreviewResponse, AccountDeleteResultResponse, BackupRestoreReportResponse
from app.schemas.me import MeResponse
from app.services.backup import build_backup
from app.services.export import content_disposition_attachment
from app.services.restore import restore_backup
from app.cookies import clear_auth_cookies
from app.services.mfa import consume_recovery_code, totp_enabled, verify_user_totp

@router.get("/me", response_model=MeResponse)
def me(
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MeResponse:
    return MeResponse.model_validate(me_with_csrf(request, response, ctx, db))


@router.get("/me/backup")
def download_backup(
    transcripts: bool = Query(False),
    summaries: bool = Query(False),
    skills: bool = Query(False),
    format: str = Query("zip", pattern="^(zip|tgz)$"),
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
):
    if not transcripts and not summaries and not skills:
        ctx.raise_error(ErrorCode.validation_error)
    content, filename, media_type = build_backup(
        ctx,
        db,
        include_transcripts=transcripts,
        include_summaries=summaries,
        include_skills=skills,
        archive_format=format,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


@router.post("/me/backup/restore", response_model=BackupRestoreReportResponse)
async def upload_backup_restore(
    file: UploadFile,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> BackupRestoreReportResponse:
    ctx.require_org()
    raw = await file.read()
    report = restore_backup(ctx, db, raw, filename=file.filename)
    return BackupRestoreReportResponse.model_validate(report.as_dict())


@router.patch("/me", response_model=MeResponse)
def patch_me(
    body: MePatchBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MeResponse:
    from app.datetime_format import DATE_TIME_FORMATS, normalize_timezone

    data = body.model_dump(exclude_unset=True)
    if "locale" in data and data["locale"]:
        ctx.user.locale = _locale(data["locale"])
        ctx.user.updated_at = utcnow()
    if "default_route" in data and data["default_route"] is not None:
        route = _default_route(data["default_route"])
        if route not in _allowed_default_routes(ctx):
            ctx.raise_error(ErrorCode.validation_error)
        ctx.user.default_route = route
        ctx.user.updated_at = utcnow()
    if "date_time_format" in data:
        fmt = data["date_time_format"]
        if fmt is None or not str(fmt).strip():
            ctx.user.date_time_format = None
        elif str(fmt).strip() in DATE_TIME_FORMATS:
            ctx.user.date_time_format = str(fmt).strip()
        else:
            ctx.raise_error(ErrorCode.validation_error)
        ctx.user.updated_at = utcnow()
    if "timezone" in data:
        tz = data["timezone"]
        if tz is None or not str(tz).strip():
            ctx.user.timezone = None
        else:
            try:
                ctx.user.timezone = normalize_timezone(str(tz))
            except ValueError:
                ctx.raise_error(ErrorCode.validation_error)
        ctx.user.updated_at = utcnow()
    if "asr_model" in data or "diarization_model" in data:
        from app.services.transcribe_models import aggregate_instance_models, resolve_transcribe_models, validate_dispatchable_models

        available = aggregate_instance_models(db)
        if "asr_model" in data:
            asr = data["asr_model"]
            if asr is None or not str(asr).strip():
                ctx.user.asr_model = None
            else:
                asr = str(asr).strip()
                if available["asr_models"] and asr not in available["asr_models"]:
                    ctx.raise_error(ErrorCode.validation_error)
                ctx.user.asr_model = asr
            ctx.user.updated_at = utcnow()
        if "diarization_model" in data:
            diar = data["diarization_model"]
            if diar is None:
                ctx.user.diarization_model = None
            elif not str(diar).strip():
                ctx.user.diarization_model = ""
            else:
                diar = str(diar).strip()
                if available["diarization_models"] and diar not in available["diarization_models"]:
                    ctx.raise_error(ErrorCode.validation_error)
                ctx.user.diarization_model = diar
            ctx.user.updated_at = utcnow()
        prefs = resolve_transcribe_models(ctx.user, get_instance_settings(db))
        try:
            validate_dispatchable_models(
                db,
                asr=prefs["asr_model"],
                diar=prefs["diarization_model"],
            )
        except ValueError:
            ctx.raise_error(ErrorCode.validation_error)
    if "summarize_model" in data:
        from app.services.summarize_models import (
            aggregate_instance_summarize_models,
            resolve_summarize_models,
            validate_dispatchable_summarize_model,
        )

        available = aggregate_instance_summarize_models(db)
        raw = data["summarize_model"]
        if raw is None or not str(raw).strip():
            ctx.user.summarize_model = None
        else:
            model = str(raw).strip()
            if available["summarize_models"] and model not in available["summarize_models"]:
                ctx.raise_error(ErrorCode.validation_error)
            ctx.user.summarize_model = model
        ctx.user.updated_at = utcnow()
        prefs = resolve_summarize_models(ctx.user, get_instance_settings(db), available=available["summarize_models"])
        if prefs["summarize_model"]:
            try:
                validate_dispatchable_summarize_model(db, model=prefs["summarize_model"])
            except ValueError:
                ctx.raise_error(ErrorCode.validation_error)
    if "tone_analytics_enabled" in data:
        raw = data["tone_analytics_enabled"]
        if raw is not None:
            ctx.user.tone_analytics_enabled = bool(raw)
            ctx.user.updated_at = utcnow()
    if "capture_bot_display_name" in data:
        from app.services.capture_meeting import normalize_capture_bot_display_name

        raw = data["capture_bot_display_name"]
        if raw is None or not str(raw).strip():
            ctx.user.capture_bot_display_name = None
        else:
            ctx.user.capture_bot_display_name = normalize_capture_bot_display_name(str(raw))
        ctx.user.updated_at = utcnow()
    return MeResponse.model_validate(me_with_csrf(request, response, ctx, db))


def _verify_account_delete_step_up(ctx: AuthContext, db: Session, body: AccountDeleteBody) -> None:
    if ctx.via_api_token or ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.user.is_instance_admin:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.user.password_hash:
        if not body.password or not verify_password(body.password, ctx.user.password_hash):
            ctx.raise_error(ErrorCode.invalid_credentials)
    if totp_enabled(ctx.user):
        code = (body.totp_code or "").strip()
        if not code:
            ctx.raise_error(ErrorCode.mfa_step_up_required)
        if not verify_user_totp(ctx.user, code, db) and not consume_recovery_code(db, ctx.user, code):
            ctx.raise_error(ErrorCode.invalid_totp)


@router.get("/me/account-delete", response_model=AccountDeletePreviewResponse)
def account_delete_preview_route(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> AccountDeletePreviewResponse:
    if ctx.via_api_token or ctx.impersonating or ctx.user.is_instance_admin:
        ctx.raise_error(ErrorCode.forbidden)
    from app.services.account_delete import account_delete_preview

    return AccountDeletePreviewResponse.model_validate(account_delete_preview(db, ctx.user, ctx.membership, ctx.org))


@router.post("/me/account-delete", response_model=AccountDeleteResultResponse)
def account_delete(
    body: AccountDeleteBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> AccountDeleteResultResponse:
    _verify_account_delete_step_up(ctx, db, body)
    from app.services.account_delete import account_delete_preview, delete_user_account

    preview = account_delete_preview(db, ctx.user, ctx.membership, ctx.org)
    write_audit(
        db,
        "user.account.delete",
        ctx,
        {
            "user_id": ctx.user.id,
            "org_id": ctx.org.id if ctx.org else None,
            "will_delete_org": preview["will_delete_org"],
            "successor_user_id": body.successor_user_id,
        },
    )
    result = delete_user_account(
        db,
        ctx.user,
        ctx.membership,
        ctx.org,
        successor_user_id=body.successor_user_id,
        locale=ctx.locale,
    )
    clear_auth_cookies(response)
    return AccountDeleteResultResponse.model_validate(result)

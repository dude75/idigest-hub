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
from app.routers.auth._body import MfaConfirmBody, MfaDisableBody, MfaRecoverBody, MfaVerifyBody
from app.routers.auth._router import router
from app.security import hash_password, hash_secret, new_api_token, new_reset_token, verify_password
from app.services.audit import write_audit
from app.services.auth_helpers import create_session, me_payload, me_with_csrf, public_base_url, revoke_user_auth, seed_default_tariff, sso_login_redirect
from app.timeutil import utcnow

from app.schemas.auth_api import MfaSetupConfirmResponse, MfaSetupStartResponse, MfaStatusResponse, OkStatusResponse
from app.schemas.me import MeResponse
from app.services.mfa import (
    hub_local_auth_applies,
    confirm_totp_setup,
    consume_mfa_challenge,
    consume_recovery_code,
    disable_totp,
    mfa_enrollment_required,
    org_mfa_required,
    resolve_mfa_challenge,
    start_totp_setup,
    totp_enabled,
    verify_user_totp,
)
from app.rate_limit import client_ip, enforce_mfa_verify, get_rate_limits

@router.post("/auth/mfa/verify", response_model=OkStatusResponse)
def mfa_verify(
    body: MfaVerifyBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> OkStatusResponse:
    locale = locale_from_request(request)
    challenge = resolve_mfa_challenge(db, body.challenge_id.strip())
    if challenge is None:
        abort(locale, ErrorCode.mfa_challenge_invalid)
    user = db.get(User, challenge.user_id)
    if user is None or user.disabled_at is not None:
        abort(locale, ErrorCode.mfa_challenge_invalid)
    limits = get_rate_limits(db)
    enforce_mfa_verify(user.email, client_ip(request), limits, locale)
    if not verify_user_totp(user, body.code, db):
        abort(locale, ErrorCode.invalid_totp)
    consume_mfa_challenge(db, challenge)
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    write_audit(db, "auth.mfa.verify", actor_id=user.id)
    return OkStatusResponse()


@router.post("/auth/mfa/recover", response_model=OkStatusResponse)
def mfa_recover(
    body: MfaRecoverBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> OkStatusResponse:
    locale = locale_from_request(request)
    challenge = resolve_mfa_challenge(db, body.challenge_id.strip())
    if challenge is None:
        abort(locale, ErrorCode.mfa_challenge_invalid)
    user = db.get(User, challenge.user_id)
    if user is None or user.disabled_at is not None:
        abort(locale, ErrorCode.mfa_challenge_invalid)
    limits = get_rate_limits(db)
    enforce_mfa_verify(user.email, client_ip(request), limits, locale)
    if not consume_recovery_code(db, user, body.recovery_code):
        abort(locale, ErrorCode.invalid_totp)
    consume_mfa_challenge(db, challenge)
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    write_audit(db, "auth.mfa.recovery", actor_id=user.id)
    return OkStatusResponse()


@router.get("/auth/mfa/status", response_model=MfaStatusResponse)
def mfa_status(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> MfaStatusResponse:
    return MfaStatusResponse(
        enabled=totp_enabled(ctx.user),
        required=org_mfa_required(user=ctx.user, org=ctx.org, membership=ctx.membership),
        enrollment_required=mfa_enrollment_required(
            user=ctx.user,
            org=ctx.org,
            membership=ctx.membership,
        ),
    )


@router.post("/auth/mfa/setup/start", response_model=MfaSetupStartResponse)
def mfa_setup_start(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> MfaSetupStartResponse:
    if ctx.impersonating or not hub_local_auth_applies(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    secret, uri = start_totp_setup(db, ctx.user)
    return MfaSetupStartResponse(secret=secret, otpauth_uri=uri)


@router.post("/auth/agreement/accept", response_model=MeResponse)
def accept_user_agreement(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MeResponse:
    from app.deps import _password_expired
    from app.services.user_agreement import accept_all_pending_documents, user_agreement_required

    if not ctx.is_instance_admin and (
        ctx.user.must_change_password or _password_expired(ctx.user, ctx.org)
    ):
        ctx.raise_error(ErrorCode.must_change_password)
    settings = get_instance_settings(db)
    if not user_agreement_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
        settings=settings,
    ):
        ctx.raise_error(ErrorCode.validation_error)
    accepted_keys = accept_all_pending_documents(ctx.user, settings)
    ctx.user.updated_at = utcnow()
    db.flush()
    write_audit(
        db,
        "auth.agreement.accept",
        ctx,
        {
            "documents": accepted_keys,
            "user_agreement_version": settings.user_agreement_version,
        },
    )
    return MeResponse.model_validate(me_payload(ctx, db))


@router.post("/auth/mfa/setup/confirm", response_model=MfaSetupConfirmResponse)
def mfa_setup_confirm(
    body: MfaConfirmBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MfaSetupConfirmResponse:
    if ctx.impersonating or not hub_local_auth_applies(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    codes = confirm_totp_setup(db, ctx.user, body.code)
    if not codes:
        ctx.raise_error(ErrorCode.invalid_totp)
    write_audit(db, "auth.mfa.enable", ctx, {})
    return MfaSetupConfirmResponse(recovery_codes=codes)


@router.post("/auth/mfa/disable", response_model=OkStatusResponse)
def mfa_disable(
    body: MfaDisableBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> OkStatusResponse:
    if ctx.impersonating or not hub_local_auth_applies(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    if not totp_enabled(ctx.user):
        ctx.raise_error(ErrorCode.validation_error)
    if org_mfa_required(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    if not ctx.user.password_hash or not verify_password(body.password, ctx.user.password_hash):
        ctx.raise_error(ErrorCode.invalid_credentials)
    if not verify_user_totp(ctx.user, body.code, db) and not consume_recovery_code(db, ctx.user, body.code):
        ctx.raise_error(ErrorCode.invalid_totp)
    disable_totp(db, ctx.user)
    revoke_user_auth(db, ctx.user.id)
    write_audit(db, "auth.mfa.disable", ctx, {})
    clear_auth_cookies(response)
    return OkStatusResponse()

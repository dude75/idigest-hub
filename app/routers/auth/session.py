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
from app.routers.auth._body import (
    LoginBody,
    PasswordChangeBody,
    ResetConfirmBody,
    ResetRequestBody,
)
from app.routers.auth._helpers import _login_membership_org, _norm_email
from app.routers.auth._router import router
from app.security import hash_password, hash_secret, new_api_token, new_reset_token, verify_password
from app.services.audit import write_audit
from app.services.auth_helpers import create_session, me_payload, me_with_csrf, public_base_url, revoke_user_auth, seed_default_tariff, sso_login_redirect
from app.timeutil import utcnow

from app.constants import PASSWORD_RESET_COOLDOWN_SEC, PASSWORD_RESET_TTL_SEC
from app.rate_limit import client_ip, enforce_login, enforce_reset_confirm, enforce_reset_request, get_rate_limits
from app.schemas.auth_api import LoginMfaRequiredResponse, LoginOkResponse, OkStatusResponse, SsoInfoResponse
from app.services.mail import send_mail, smtp_configured
from app.services.sso import (
    begin_org_sso_login,
    email_from_claims,
    exchange_code,
    org_sso_public,
    password_login_allowed,
    resolve_or_provision_user,
    sso_configured,
    sso_post_login_url,
    validate_id_token,
    verify_oauth_state,
)
from app.services.mfa import create_mfa_challenge, should_challenge_at_login

@router.post("/auth/login", response_model=LoginOkResponse | LoginMfaRequiredResponse)
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> LoginOkResponse | LoginMfaRequiredResponse:
    locale = locale_from_request(request)
    email = _norm_email(body.email)
    limits = get_rate_limits(db)
    enforce_login(email, client_ip(request), limits, locale)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.disabled_at is not None or not user.password_hash:
        abort(locale, ErrorCode.invalid_credentials)
    membership, org = _login_membership_org(db, user)
    if not password_login_allowed(
        membership=membership,
        org=org,
        is_instance_admin=user.is_instance_admin,
    ):
        abort(locale, ErrorCode.sso_login_required)
    if not verify_password(body.password, user.password_hash):
        abort(locale, ErrorCode.invalid_credentials)
    if should_challenge_at_login(user=user, org=org, membership=membership):
        challenge_id = create_mfa_challenge(db, user.id)
        return LoginMfaRequiredResponse(challenge_id=challenge_id)
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    return LoginOkResponse()


@router.get("/auth/sso/{org_id}/info", response_model=SsoInfoResponse)
def sso_info(org_id: str, request: Request, db: Session = Depends(get_session, scope="function")) -> SsoInfoResponse:
    locale = locale_from_request(request)
    org = db.get(Organization, org_id)
    if org is None:
        abort(locale, ErrorCode.not_found)
    return SsoInfoResponse.model_validate(
        {
            "org_id": org.id,
            "org_name": org.name,
            **org_sso_public(org, public_base_url=public_base_url(db)),
        }
    )


@router.get("/auth/sso/{org_id}/start")
def sso_start(org_id: str, request: Request, db: Session = Depends(get_session, scope="function")) -> RedirectResponse:
    locale = locale_from_request(request)
    org = db.get(Organization, org_id)
    if org is None:
        abort(locale, ErrorCode.not_found)
    if not sso_configured(org):
        abort(locale, ErrorCode.sso_misconfigured)
    if not org.sso_enabled:
        abort(locale, ErrorCode.sso_disabled)
    public_base = public_base_url(db)
    if not public_base:
        abort(locale, ErrorCode.sso_misconfigured)
    try:
        url = begin_org_sso_login(org=org, public_base_url=public_base, oauth_authorize_query=None)
    except ValueError as exc:
        if str(exc) == "sso_disabled":
            abort(locale, ErrorCode.sso_disabled)
        abort(locale, ErrorCode.sso_misconfigured)
    except Exception:
        abort(locale, ErrorCode.sso_misconfigured)
    return RedirectResponse(url, status_code=302)


@router.get("/auth/sso/{org_id}/callback")
def sso_callback(
    org_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    locale = locale_from_request(request)
    public_base = public_base_url(db)

    def fail(error_code: ErrorCode) -> RedirectResponse:
        if public_base:
            return sso_login_redirect(public_base, org_id, error_code)
        abort(locale, error_code)

    org = db.get(Organization, org_id)
    if org is None:
        return fail(ErrorCode.not_found)
    if not sso_configured(org) or not org.sso_enabled:
        return fail(ErrorCode.sso_disabled)
    if not public_base or not code or not state:
        return fail(ErrorCode.sso_misconfigured)
    try:
        nonce, code_verifier, oauth_authorize_query = verify_oauth_state(state, org_id)
        token_payload = exchange_code(
            db=db,
            org=org,
            public_base_url=public_base,
            code=code,
            code_verifier=code_verifier,
        )
        id_token = token_payload.get("id_token")
        if not id_token:
            return fail(ErrorCode.sso_misconfigured)
        claims = validate_id_token(org=org, id_token=id_token, nonce=nonce)
        email = email_from_claims(claims)
        sub = str(claims.get("sub") or "")
        if not email or not sub:
            return fail(ErrorCode.sso_email_missing)
        user = resolve_or_provision_user(db, org=org, email=email, sub=sub, locale=locale)
    except ValueError as exc:
        message = str(exc)
        if message == "user wrong org":
            return fail(ErrorCode.sso_user_wrong_org)
        if message == "user disabled":
            return fail(ErrorCode.account_disabled)
        return fail(ErrorCode.sso_state_invalid)
    except Exception:
        return fail(ErrorCode.sso_misconfigured)
    raw = create_session(db, user.id)
    location = sso_post_login_url(public_base, oauth_authorize_query=oauth_authorize_query)
    redirect = RedirectResponse(location, status_code=302)
    issue_auth_cookies(
        redirect,
        raw,
        max_age=session_ttl_sec_from_db(db),
        samesite=oauth_embedded_session_samesite() if oauth_authorize_query else "lax",
    )
    return redirect


@router.post("/auth/logout", response_model=OkStatusResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext | None = Depends(optional_auth),
) -> OkStatusResponse:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_secret(token)))
    clear_auth_cookies(response)
    return OkStatusResponse()


@router.post("/auth/password/change", response_model=OkStatusResponse)
def change_password(
    body: PasswordChangeBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> OkStatusResponse:
    user = ctx.user
    if ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    if not user.password_hash:
        ctx.raise_error(ErrorCode.forbidden)
    forced = user.must_change_password
    if not forced:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            ctx.raise_error(ErrorCode.invalid_credentials)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    user.updated_at = utcnow()
    revoke_user_auth(db, user.id)
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    return OkStatusResponse()


@router.post("/auth/password/reset/request", response_model=OkStatusResponse)
def reset_request(body: ResetRequestBody, request: Request, db: Session = Depends(get_session, scope="function")) -> OkStatusResponse:
    locale = locale_from_request(request)
    settings = get_instance_settings(db)
    if not smtp_configured(settings):
        abort(locale, ErrorCode.recovery_disabled)
    email = _norm_email(body.email)
    limits = get_rate_limits(db)
    enforce_reset_request(email, client_ip(request), limits, locale)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.disabled_at is None:
        membership, org = _login_membership_org(db, user)
        if not password_login_allowed(
            membership=membership,
            org=org,
            is_instance_admin=user.is_instance_admin,
        ):
            return OkStatusResponse()
        cooldown_cutoff = utcnow() - timedelta(seconds=PASSWORD_RESET_COOLDOWN_SEC)
        recent = db.scalar(
            select(PasswordResetToken.id).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > utcnow(),
                PasswordResetToken.created_at > cooldown_cutoff,
            )
        )
        if recent is not None:
            return OkStatusResponse()
        raw = new_reset_token()
        now = utcnow()
        db.add(
            PasswordResetToken(
                id=new_id(),
                user_id=user.id,
                token_hash=hash_secret(raw),
                expires_at=now + timedelta(seconds=PASSWORD_RESET_TTL_SEC),
                created_at=now,
            )
        )
        base = (settings.public_base_url or "").rstrip("/")
        link = f"{base}/reset?token={raw}"
        send_mail(
            db,
            user.email,
            "Password reset",
            f"Reset your password (valid 1 hour):\n{link}\n",
        )
    return OkStatusResponse()


@router.post("/auth/password/reset/confirm", response_model=OkStatusResponse)
def reset_confirm(body: ResetConfirmBody, request: Request, db: Session = Depends(get_session, scope="function")) -> OkStatusResponse:
    locale = locale_from_request(request)
    limits = get_rate_limits(db)
    enforce_reset_confirm(client_ip(request), limits, locale)
    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_secret(body.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        )
    )
    if row is None:
        abort(locale, ErrorCode.not_found)
    user = db.get(User, row.user_id)
    if user is None or user.disabled_at is not None:
        abort(locale, ErrorCode.not_found)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    user.updated_at = utcnow()
    row.used_at = utcnow()
    revoke_user_auth(db, user.id)
    return OkStatusResponse()


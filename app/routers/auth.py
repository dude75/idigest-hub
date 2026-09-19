"""Setup, login, signup, пароли, API-токены, /me (ТЗ §3–4, §12)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.constants import (
    COOKIE_NAME,
    DEFAULT_LOCALE,
    DEFAULT_ROUTE,
    DEFAULT_ROUTES,
    DEFAULT_TARIFF_NAME,
    INSTANCE_TABS,
    LEGACY_DEFAULT_ROUTE,
    LEGACY_INSTANCE_ROUTE,
    MAX_UPLOAD_BYTES_CAP,
    PASSWORD_RESET_COOLDOWN_SEC,
    PASSWORD_RESET_TTL_SEC,
    SECURITY_TABS,
    SUPPORTED_LOCALES,
)
from app.cookies import clear_auth_cookies, issue_auth_cookies
from app.services.secrets_bootstrap import session_secret_configured
from app.db import get_session
from app.deps import AuthContext, abort, get_instance_settings, locale_from_request, optional_auth, require_auth, session_ttl_sec_from_db
from app.errors import ErrorCode
from app.i18n import t
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
from app.services.billing import signup_balance
from app.security import (
    hash_password,
    hash_secret,
    new_api_token,
    new_reset_token,
    new_session_token,
    verify_password,
)
from app.services.audit import write_audit
from app.services.sso import (
    build_authorization_url,
    email_from_claims,
    exchange_code,
    make_oauth_state,
    org_sso_public,
    password_login_allowed,
    resolve_or_provision_user,
    sso_configured,
    validate_id_token,
    verify_oauth_state,
)
from app.services.backup import build_backup
from app.services.export import content_disposition_attachment
from app.services.mail import send_mail, smtp_configured
from app.rate_limit import (
    client_ip,
    enforce_login,
    enforce_mfa_verify,
    enforce_reset_confirm,
    enforce_reset_request,
    enforce_setup,
    enforce_signup,
    get_rate_limits,
)
from app.services.mfa import (
    hub_local_auth_applies,
    confirm_totp_setup,
    consume_mfa_challenge,
    consume_recovery_code,
    create_mfa_challenge,
    disable_totp,
    mfa_enrollment_required,
    org_mfa_required,
    resolve_mfa_challenge,
    should_challenge_at_login,
    start_totp_setup,
    totp_enabled,
    verify_user_totp,
)
from app.timeutil import as_utc, utcnow

router = APIRouter()


class SetupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    bootstrap_token: str
    locale: str = DEFAULT_LOCALE


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    tariff_id: str
    locale: str = DEFAULT_LOCALE
    accept_legal_documents: bool = False


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class PasswordChangeBody(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8)


class ResetRequestBody(BaseModel):
    email: EmailStr


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class TokenCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    totp_code: str | None = None


class MfaVerifyBody(BaseModel):
    challenge_id: str
    code: str = Field(min_length=6, max_length=16)


class MfaRecoverBody(BaseModel):
    challenge_id: str
    recovery_code: str = Field(min_length=8, max_length=32)


class MfaConfirmBody(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class MfaDisableBody(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=32)


class MePatchBody(BaseModel):
    locale: str | None = None
    default_route: str | None = None
    date_time_format: str | None = None
    timezone: str | None = None
    asr_model: str | None = None
    diarization_model: str | None = Field(default=None)
    show_only_my_items: bool | None = None


class AccountDeleteBody(BaseModel):
    password: str | None = None
    totp_code: str | None = None
    successor_user_id: str | None = None


def _norm_email(email: str) -> str:
    return str(email).strip().lower()


def _locale(value: str) -> str:
    return value if value in SUPPORTED_LOCALES else DEFAULT_LOCALE


def _allowed_default_routes(ctx: AuthContext) -> set[str]:
    routes = {"tasks"}
    if ctx.org:
        routes.update(
            {
                "library/audio",
                "library/transcripts",
                "library/summaries",
                "skills",
                "org",
            }
        )
        if ctx.membership and ctx.membership.role == "org_admin":
            routes.add("stats")
    if ctx.user.is_instance_admin and not ctx.impersonating:
        routes.update(f"instance/{tab}" for tab in INSTANCE_TABS)
        routes.update(f"security/{tab}" for tab in SECURITY_TABS)
    return routes


def _default_route(value: str) -> str:
    if value == LEGACY_DEFAULT_ROUTE:
        value = DEFAULT_ROUTE
    if value == LEGACY_INSTANCE_ROUTE:
        value = "instance/stats"
    return value if value in DEFAULT_ROUTES else DEFAULT_ROUTE


def seed_default_tariff(db: Session) -> Tariff:
    existing = db.scalar(select(Tariff).limit(1))
    if existing is not None:
        return existing
    now = utcnow()
    tariff = Tariff(
        id=new_id(),
        name=DEFAULT_TARIFF_NAME,
        unlimited=True,
        available_on_signup=True,
        archived_at=None,
        price_per_audio_sec=Decimal("0"),
        price_per_summarize_job=Decimal("0"),
        price_per_1k_summary_chars=Decimal("0"),
        audio_retention_days=0,
        api_enabled=True,
        signup_credit=Decimal("0.00"),
        max_upload_bytes=MAX_UPLOAD_BYTES_CAP,
        created_at=now,
        updated_at=now,
    )
    db.add(tariff)
    db.flush()
    return tariff


def create_session(db: Session, user_id: str) -> str:
    raw = new_session_token()
    now = utcnow()
    ttl_sec = session_ttl_sec_from_db(db)
    db.add(
        AuthSession(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_secret(raw),
            impersonate_user_id=None,
            expires_at=now + timedelta(seconds=ttl_sec),
            created_at=now,
            last_seen_at=now,
        )
    )
    return raw


def invalidate_user_sessions(db: Session, user_id: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def revoke_user_tokens(db: Session, user_id: str) -> None:
    now = utcnow()
    tokens = db.scalars(select(ApiToken).where(ApiToken.user_id == user_id, ApiToken.revoked_at.is_(None)))
    for token in tokens:
        token.revoked_at = now


def revoke_user_auth(db: Session, user_id: str) -> None:
    invalidate_user_sessions(db, user_id)
    revoke_user_tokens(db, user_id)


def _public_base_url(db: Session) -> str | None:
    settings = get_instance_settings(db)
    value = (settings.public_base_url or "").strip()
    return value or None


def _sso_login_redirect(public_base: str, org_id: str, code: ErrorCode) -> RedirectResponse:
    query = urlencode({"error": code.value})
    return RedirectResponse(f"{public_base.rstrip('/')}/sso/{org_id}?{query}", status_code=302)


def _me_payload(ctx: AuthContext, db: Session) -> dict:
    role = ctx.membership.role if ctx.membership else ("instance_admin" if ctx.user.is_instance_admin else None)
    usage = None
    if ctx.org is not None:
        from app.models import UsageEvent

        total = db.scalar(
            select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(UsageEvent.org_id == ctx.org.id)
        )
        usage = {"total_amount": str(total)}
    enrollment_required = mfa_enrollment_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
    )
    from app.datetime_format import resolve_date_time_prefs
    from app.services.transcribe_models import aggregate_instance_models, resolve_transcribe_models
    from app.services.user_agreement import (
        agreement_active,
        agreement_text,
        member_legal_documents,
        user_agreement_required,
    )

    settings = get_instance_settings(db)
    agreement_pending = user_agreement_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
        settings=settings,
    )
    agreement_payload = None
    legal_documents = None
    if ctx.membership is not None and ctx.org is not None:
        legal_documents = member_legal_documents(ctx.user, settings, ctx.locale)
        if agreement_active(settings):
            agreement_payload = {
                "version": settings.user_agreement_version,
                "text": agreement_text(settings, ctx.locale),
            }
    return {
        "user": user_public(ctx.user, role),
        "org": org_public(ctx.org, usage=usage, public_base_url=_public_base_url(db)) if ctx.org else None,
        "impersonating": ctx.impersonating,
        "actor": user_public(ctx.actor) if ctx.impersonating else None,
        "date_time_prefs": resolve_date_time_prefs(ctx.user, settings),
        "transcribe_prefs": resolve_transcribe_models(ctx.user, settings),
        "transcribe_models": aggregate_instance_models(db),
        "must_change_password": ctx.user.must_change_password
        or (
            ctx.org is not None
            and ctx.org.password_ttl_days > 0
            and ctx.user.password_changed_at is not None
            and utcnow()
            >= as_utc(ctx.user.password_changed_at) + timedelta(days=ctx.org.password_ttl_days)
        ),
        "mfa_enabled": totp_enabled(ctx.user),
        "mfa_required": org_mfa_required(user=ctx.user, org=ctx.org, membership=ctx.membership),
        "mfa_enrollment_required": enrollment_required,
        "user_agreement_required": agreement_pending,
        "user_agreement": agreement_payload,
        "user_agreement_version": settings.user_agreement_version if agreement_active(settings) else None,
        "legal_documents": legal_documents,
    }


@router.post("/setup")
def setup(body: SetupBody, request: Request, response: Response, db: Session = Depends(get_session, scope="function")) -> dict:
    locale = _locale(body.locale)
    limits = get_rate_limits(db)
    enforce_setup(client_ip(request), limits, locale)
    settings = get_instance_settings(db)
    if settings.bootstrap_done:
        abort(locale, ErrorCode.setup_already_done)
    from app.config import get_settings as cfg

    if not session_secret_configured():
        abort(locale, ErrorCode.secrets_misconfigured)
    if not cfg().INSTANCE_BOOTSTRAP_TOKEN or body.bootstrap_token != cfg().INSTANCE_BOOTSTRAP_TOKEN:
        abort(locale, ErrorCode.bootstrap_invalid)
    email = _norm_email(body.email)
    if db.scalar(select(User).where(User.email == email)):
        abort(locale, ErrorCode.email_taken)
    now = utcnow()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(body.password),
        auth_provider="local",
        locale=locale,
        password_changed_at=now,
        must_change_password=False,
        is_instance_admin=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    seed_default_tariff(db)
    settings.bootstrap_done = True
    settings.instance_admin_user_id = user.id
    settings.allow_new_orgs = True
    write_audit(db, "instance.setup", actor_id=user.id, payload={"email": email})
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    return {"status": "ok", "user": user_public(user, "instance_admin")}


@router.post("/auth/signup")
def signup(body: SignupBody, request: Request, response: Response, db: Session = Depends(get_session, scope="function")) -> dict:
    locale = _locale(body.locale)
    settings = get_instance_settings(db)
    if not settings.bootstrap_done:
        abort(locale, ErrorCode.not_found)
    if not settings.allow_new_orgs:
        abort(locale, ErrorCode.signup_disabled)
    signup_tariffs_exist = db.scalar(
        select(Tariff).where(Tariff.archived_at.is_(None), Tariff.available_on_signup.is_(True)).limit(1)
    )
    if signup_tariffs_exist is None:
        abort(locale, ErrorCode.signup_disabled)
    email = _norm_email(body.email)
    limits = get_rate_limits(db)
    enforce_signup(email, client_ip(request), limits, locale)
    tariff = db.get(Tariff, body.tariff_id)
    if (
        tariff is None
        or tariff.archived_at is not None
        or not tariff.available_on_signup
    ):
        abort(locale, ErrorCode.tariff_not_available)
    if db.scalar(select(User).where(User.email == email)):
        abort(locale, ErrorCode.email_taken)
    from app.services.user_agreement import accept_all_pending_documents, any_document_active

    if any_document_active(settings) and not body.accept_legal_documents:
        abort(locale, ErrorCode.validation_error)
    now = utcnow()
    user = User(
        id=new_id(),
        email=email,
        password_hash=hash_password(body.password),
        auth_provider="local",
        locale=locale,
        password_changed_at=now,
        must_change_password=False,
        is_instance_admin=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    org_name = email.split("@", 1)[0]
    org = Organization(
        id=new_id(),
        name=org_name,
        is_personal=True,
        tariff_id=tariff.id,
        password_ttl_days=0,
        balance=signup_balance(tariff),
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    db.flush()
    db.add(Membership(id=new_id(), user_id=user.id, org_id=org.id, role="org_admin"))
    if any_document_active(settings):
        accept_all_pending_documents(user, settings)
        user.updated_at = utcnow()
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    return {"status": "ok", "user": user_public(user, "org_admin")}


def _tariff_org_count(db: Session, tariff_id: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff_id)) or 0
    )


@router.get("/auth/signup-tariffs")
def signup_tariffs(request: Request, db: Session = Depends(get_session, scope="function")) -> dict:
    locale = locale_from_request(request)
    settings = get_instance_settings(db)
    if not settings.bootstrap_done or not settings.allow_new_orgs:
        return {"items": []}
    rows = db.scalars(
        select(Tariff).where(Tariff.archived_at.is_(None), Tariff.available_on_signup.is_(True))
    ).all()
    return {"items": [tariff_public(row, _tariff_org_count(db, row.id)) for row in rows]}


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_session, scope="function")) -> dict:
    settings = get_instance_settings(db)
    return {"bootstrap_done": bool(settings.bootstrap_done)}


def _login_membership_org(db: Session, user: User) -> tuple[Membership | None, Organization | None]:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    if membership is None:
        return None, None
    org = db.get(Organization, membership.org_id)
    return membership, org


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_session, scope="function")) -> dict:
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
        return {"status": "mfa_required", "challenge_id": challenge_id}
    raw = create_session(db, user.id)
    issue_auth_cookies(response, raw, max_age=session_ttl_sec_from_db(db))
    return {"status": "ok"}


@router.get("/auth/sso/{org_id}/info")
def sso_info(org_id: str, request: Request, db: Session = Depends(get_session, scope="function")) -> dict:
    locale = locale_from_request(request)
    org = db.get(Organization, org_id)
    if org is None:
        abort(locale, ErrorCode.not_found)
    return {
        "org_id": org.id,
        "org_name": org.name,
        **org_sso_public(org, public_base_url=_public_base_url(db)),
    }


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
    public_base = _public_base_url(db)
    if not public_base:
        abort(locale, ErrorCode.sso_misconfigured)
    try:
        state, nonce, code_challenge = make_oauth_state(org_id)
        url = build_authorization_url(
            org=org,
            public_base_url=public_base,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
        )
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
    public_base = _public_base_url(db)

    def fail(error_code: ErrorCode) -> RedirectResponse:
        if public_base:
            return _sso_login_redirect(public_base, org_id, error_code)
        abort(locale, error_code)

    org = db.get(Organization, org_id)
    if org is None:
        return fail(ErrorCode.not_found)
    if not sso_configured(org) or not org.sso_enabled:
        return fail(ErrorCode.sso_disabled)
    if not public_base or not code or not state:
        return fail(ErrorCode.sso_misconfigured)
    try:
        nonce, code_verifier = verify_oauth_state(state, org_id)
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
    redirect = RedirectResponse(f"{public_base.rstrip('/')}/app", status_code=302)
    issue_auth_cookies(redirect, raw, max_age=session_ttl_sec_from_db(db))
    return redirect


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext | None = Depends(optional_auth),
) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_secret(token)))
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.post("/auth/password/change")
def change_password(
    body: PasswordChangeBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
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
    return {"status": "ok"}


@router.post("/auth/password/reset/request")
def reset_request(body: ResetRequestBody, request: Request, db: Session = Depends(get_session, scope="function")) -> dict:
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
            return {"status": "ok"}
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
            return {"status": "ok"}
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
    return {"status": "ok"}


@router.post("/auth/password/reset/confirm")
def reset_confirm(body: ResetConfirmBody, request: Request, db: Session = Depends(get_session, scope="function")) -> dict:
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
    return {"status": "ok"}


@router.post("/auth/mfa/verify")
def mfa_verify(
    body: MfaVerifyBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
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
    return {"status": "ok"}


@router.post("/auth/mfa/recover")
def mfa_recover(
    body: MfaRecoverBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
) -> dict:
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
    return {"status": "ok"}


@router.get("/auth/mfa/status")
def mfa_status(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    return {
        "enabled": totp_enabled(ctx.user),
        "required": org_mfa_required(user=ctx.user, org=ctx.org, membership=ctx.membership),
        "enrollment_required": mfa_enrollment_required(
            user=ctx.user,
            org=ctx.org,
            membership=ctx.membership,
        ),
    }


@router.post("/auth/mfa/setup/start")
def mfa_setup_start(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    if ctx.impersonating or not hub_local_auth_applies(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    secret, uri = start_totp_setup(db, ctx.user)
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/auth/agreement/accept")
def accept_user_agreement(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
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
    return _me_payload(ctx, db)


@router.post("/auth/mfa/setup/confirm")
def mfa_setup_confirm(
    body: MfaConfirmBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    if ctx.impersonating or not hub_local_auth_applies(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.forbidden)
    codes = confirm_totp_setup(db, ctx.user, body.code)
    if not codes:
        ctx.raise_error(ErrorCode.invalid_totp)
    write_audit(db, "auth.mfa.enable", ctx, {})
    return {"status": "ok", "recovery_codes": codes}


@router.post("/auth/mfa/disable")
def mfa_disable(
    body: MfaDisableBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
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
    return {"status": "ok"}


@router.get("/me")
def me(db: Session = Depends(get_session, scope="function"), ctx: AuthContext = Depends(require_auth)) -> dict:
    return _me_payload(ctx, db)


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


@router.patch("/me")
def patch_me(
    body: MePatchBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
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
    if "show_only_my_items" in data and data["show_only_my_items"] is not None:
        ctx.user.show_only_my_items = bool(data["show_only_my_items"])
        ctx.user.updated_at = utcnow()
    return _me_payload(ctx, db)


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


@router.get("/me/account-delete")
def account_delete_preview_route(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    if ctx.via_api_token or ctx.impersonating or ctx.user.is_instance_admin:
        ctx.raise_error(ErrorCode.forbidden)
    from app.services.account_delete import account_delete_preview

    return account_delete_preview(db, ctx.user, ctx.membership, ctx.org)


@router.post("/me/account-delete")
def account_delete(
    body: AccountDeleteBody,
    response: Response,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
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
    return result


@router.post("/auth/tokens")
def create_token(
    body: TokenCreateBody,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    if ctx.via_api_token or ctx.impersonating:
        ctx.raise_error(ErrorCode.forbidden)
    if ctx.user.must_change_password:
        ctx.raise_error(ErrorCode.must_change_password)
    if mfa_enrollment_required(user=ctx.user, org=ctx.org, membership=ctx.membership):
        ctx.raise_error(ErrorCode.mfa_enrollment_required)
    from app.services.user_agreement import user_agreement_required

    if user_agreement_required(
        user=ctx.user,
        org=ctx.org,
        membership=ctx.membership,
        settings=get_instance_settings(db),
    ):
        ctx.raise_error(ErrorCode.user_agreement_required)
    from app.services.billing import org_api_enabled

    if not org_api_enabled(ctx.org):
        ctx.raise_error(ErrorCode.api_disabled)
    if totp_enabled(ctx.user):
        if not body.totp_code:
            ctx.raise_error(ErrorCode.mfa_step_up_required)
        if not verify_user_totp(ctx.user, body.totp_code, db):
            ctx.raise_error(ErrorCode.invalid_totp)
    raw = new_api_token()
    now = utcnow()
    row = ApiToken(
        id=new_id(),
        user_id=ctx.user.id,
        name=body.name.strip(),
        token_hash=hash_secret(raw),
        prefix=raw[:10],
        created_at=now,
    )
    db.add(row)
    db.flush()
    payload = token_public(row)
    payload["token"] = raw
    return payload


@router.get("/auth/tokens")
def list_tokens(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    rows = db.scalars(select(ApiToken).where(ApiToken.user_id == ctx.user.id).order_by(ApiToken.created_at.desc()))
    from app.services.billing import org_api_enabled

    blocked = not org_api_enabled(ctx.org)
    return {"items": [token_public(row, blocked_by_tariff=blocked) for row in rows]}


@router.delete("/auth/tokens/{token_id}")
def revoke_token(
    token_id: str,
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    row = db.get(ApiToken, token_id)
    if row is None or row.user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    row.revoked_at = utcnow()
    return {"status": "ok"}

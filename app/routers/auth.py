"""Setup, login, signup, пароли, API-токены, /me (ТЗ §3–4, §12)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.constants import (
    COOKIE_NAME,
    DEFAULT_LOCALE,
    DEFAULT_ROUTE,
    DEFAULT_ROUTES,
    DEFAULT_TARIFF_NAME,
    LEGACY_DEFAULT_ROUTE,
    MAX_UPLOAD_BYTES_CAP,
    PASSWORD_RESET_TTL_SEC,
    SESSION_TTL_SEC,
    SUPPORTED_LOCALES,
)
from app.cookies import clear_session_cookie, set_session_cookie
from app.db import get_session
from app.deps import AuthContext, abort, get_instance_settings, locale_from_request, optional_auth, require_auth
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
from app.services.mail import send_mail, smtp_configured
from app.rate_limit import (
    client_ip,
    enforce_login,
    enforce_reset_confirm,
    enforce_reset_request,
    enforce_setup,
    enforce_signup,
    get_rate_limits,
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


class MePatchBody(BaseModel):
    locale: str | None = None
    default_route: str | None = None


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
        routes.add("instance")
    return routes


def _default_route(value: str) -> str:
    if value == LEGACY_DEFAULT_ROUTE:
        value = DEFAULT_ROUTE
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
    db.add(
        AuthSession(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_secret(raw),
            impersonate_user_id=None,
            expires_at=now + timedelta(seconds=SESSION_TTL_SEC),
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


def _me_payload(ctx: AuthContext, db: Session) -> dict:
    role = ctx.membership.role if ctx.membership else ("instance_admin" if ctx.user.is_instance_admin else None)
    usage = None
    if ctx.org is not None:
        from app.models import UsageEvent

        total = db.scalar(
            select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(UsageEvent.org_id == ctx.org.id)
        )
        usage = {"total_amount": str(total)}
    return {
        "user": user_public(ctx.user, role),
        "org": org_public(ctx.org, usage=usage) if ctx.org else None,
        "impersonating": ctx.impersonating,
        "actor": user_public(ctx.actor) if ctx.impersonating else None,
        "must_change_password": ctx.user.must_change_password
        or (
            ctx.org is not None
            and ctx.org.password_ttl_days > 0
            and ctx.user.password_changed_at is not None
            and utcnow()
            >= as_utc(ctx.user.password_changed_at) + timedelta(days=ctx.org.password_ttl_days)
        ),
    }


@router.post("/setup")
def setup(body: SetupBody, request: Request, response: Response, db: Session = Depends(get_session)) -> dict:
    locale = _locale(body.locale)
    limits = get_rate_limits(db)
    enforce_setup(client_ip(request), limits, locale)
    settings = get_instance_settings(db)
    if settings.bootstrap_done:
        abort(locale, ErrorCode.setup_already_done)
    from app.config import get_settings as cfg

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
    set_session_cookie(response, raw)
    return {"status": "ok", "user": user_public(user, "instance_admin")}


@router.post("/auth/signup")
def signup(body: SignupBody, request: Request, response: Response, db: Session = Depends(get_session)) -> dict:
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
    raw = create_session(db, user.id)
    set_session_cookie(response, raw)
    return {"status": "ok", "user": user_public(user, "org_admin")}


@router.get("/auth/signup-tariffs")
def signup_tariffs(request: Request, db: Session = Depends(get_session)) -> dict:
    locale = locale_from_request(request)
    settings = get_instance_settings(db)
    if not settings.bootstrap_done or not settings.allow_new_orgs:
        return {"items": []}
    rows = db.scalars(
        select(Tariff).where(Tariff.archived_at.is_(None), Tariff.available_on_signup.is_(True))
    ).all()
    return {"items": [tariff_public(row) for row in rows]}


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_session)) -> dict:
    settings = get_instance_settings(db)
    return {"bootstrap_done": bool(settings.bootstrap_done)}


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_session)) -> dict:
    locale = locale_from_request(request)
    email = _norm_email(body.email)
    limits = get_rate_limits(db)
    enforce_login(email, client_ip(request), limits, locale)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.disabled_at is not None or not user.password_hash:
        abort(locale, ErrorCode.invalid_credentials)
    if not verify_password(body.password, user.password_hash):
        abort(locale, ErrorCode.invalid_credentials)
    raw = create_session(db, user.id)
    set_session_cookie(response, raw)
    return {"status": "ok"}


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    ctx: AuthContext | None = Depends(optional_auth),
) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_secret(token)))
    clear_session_cookie(response)
    return {"status": "ok"}


@router.post("/auth/password/change")
def change_password(
    body: PasswordChangeBody,
    response: Response,
    db: Session = Depends(get_session),
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
    invalidate_user_sessions(db, user.id)
    raw = create_session(db, user.id)
    set_session_cookie(response, raw)
    return {"status": "ok"}


@router.post("/auth/password/reset/request")
def reset_request(body: ResetRequestBody, request: Request, db: Session = Depends(get_session)) -> dict:
    locale = locale_from_request(request)
    settings = get_instance_settings(db)
    if not smtp_configured(settings):
        abort(locale, ErrorCode.recovery_disabled)
    email = _norm_email(body.email)
    limits = get_rate_limits(db)
    enforce_reset_request(email, client_ip(request), limits, locale)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.disabled_at is None:
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
def reset_confirm(body: ResetConfirmBody, request: Request, db: Session = Depends(get_session)) -> dict:
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
    invalidate_user_sessions(db, user.id)
    return {"status": "ok"}


@router.get("/me")
def me(db: Session = Depends(get_session), ctx: AuthContext = Depends(require_auth)) -> dict:
    return _me_payload(ctx, db)


@router.patch("/me")
def patch_me(
    body: MePatchBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    if body.locale:
        ctx.user.locale = _locale(body.locale)
        ctx.user.updated_at = utcnow()
    if body.default_route is not None:
        route = _default_route(body.default_route)
        if route not in _allowed_default_routes(ctx):
            ctx.raise_error(ErrorCode.validation_error)
        ctx.user.default_route = route
        ctx.user.updated_at = utcnow()
    return _me_payload(ctx, db)


@router.post("/auth/tokens")
def create_token(
    body: TokenCreateBody,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    if ctx.user.must_change_password:
        ctx.raise_error(ErrorCode.must_change_password)
    from app.services.billing import org_api_enabled

    if not org_api_enabled(ctx.org):
        ctx.raise_error(ErrorCode.api_disabled)
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
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    rows = db.scalars(select(ApiToken).where(ApiToken.user_id == ctx.user.id).order_by(ApiToken.created_at.desc()))
    from app.services.billing import org_api_enabled

    blocked = not org_api_enabled(ctx.org)
    return {"items": [token_public(row, blocked_by_tariff=blocked) for row in rows]}


@router.delete("/auth/tokens/{token_id}")
def revoke_token(
    token_id: str,
    db: Session = Depends(get_session),
    ctx: AuthContext = Depends(require_auth),
) -> dict:
    row = db.get(ApiToken, token_id)
    if row is None or row.user_id != ctx.user.id:
        ctx.raise_error(ErrorCode.not_found)
    row.revoked_at = utcnow()
    return {"status": "ok"}

"""Зависимости FastAPI: сессия БД, локаль, текущий пользователь."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.constants import COOKIE_NAME, DEFAULT_SESSION_TTL_HOURS, MAX_SESSION_TTL_HOURS, MIN_SESSION_TTL_HOURS
from app.db import get_session
from app.errors import ApiError, ErrorCode
from app.i18n import negotiate_locale, t
from app.models import InstanceSettings, Membership, Organization, Session as AuthSession, Tariff, User
from app.security import hash_secret
from app.timeutil import utcnow, as_utc

ALLOWED_WHEN_MUST_CHANGE = {
    ("POST", "/api/v1/auth/password/change"),
    ("POST", "/api/v1/auth/logout"),
    ("DELETE", "/api/v1/impersonate"),
    ("GET", "/api/v1/me"),
    ("PATCH", "/api/v1/me"),
}


@dataclass
class AuthContext:
    user: User
    actor: User
    org: Organization | None
    membership: Membership | None
    session: AuthSession | None
    via_api_token: bool
    locale: str
    impersonating: bool

    @property
    def is_instance_admin(self) -> bool:
        return self.actor.is_instance_admin and not self.impersonating

    @property
    def is_org_admin(self) -> bool:
        return self.membership is not None and self.membership.role == "org_admin"

    @property
    def is_org_member(self) -> bool:
        return self.membership is not None

    def raise_error(self, code: ErrorCode, status_code: int | None = None) -> None:
        raise ApiError(code, t(self.locale, code.value), status_code)

    def require_org(self) -> tuple[Organization, Membership]:
        if self.org is None or self.membership is None:
            self.raise_error(ErrorCode.forbidden)
        return self.org, self.membership

    def require_org_admin(self) -> tuple[Organization, Membership]:
        org, membership = self.require_org()
        if membership.role != "org_admin":
            self.raise_error(ErrorCode.forbidden)
        return org, membership

    def require_instance_admin(self) -> None:
        if not self.is_instance_admin:
            self.raise_error(ErrorCode.forbidden)


def locale_from_request(request: Request, user: User | None = None) -> str:
    header = request.headers.get("accept-language")
    return negotiate_locale(header, user.locale if user else None)


def abort(locale: str, code: ErrorCode, status_code: int | None = None) -> None:
    raise ApiError(code, t(locale, code.value), status_code)


def _password_expired(user: User, org: Organization | None) -> bool:
    if org is None or org.password_ttl_days <= 0 or user.password_changed_at is None:
        return False
    deadline = as_utc(user.password_changed_at) + timedelta(days=org.password_ttl_days)
    return utcnow() >= deadline


def load_org_bundle(db: Session, user: User) -> tuple[Organization | None, Membership | None]:
    membership = db.scalar(
        select(Membership)
        .options(joinedload(Membership.org).joinedload(Organization.tariff))
        .where(Membership.user_id == user.id)
    )
    if membership is None:
        return None, None
    return membership.org, membership


def _effective_user(db: Session, session_row: AuthSession, login_user: User) -> User:
    if not session_row.impersonate_user_id:
        return login_user
    target = db.get(User, session_row.impersonate_user_id)
    if target is None or target.disabled_at is not None:
        session_row.impersonate_user_id = None
        db.flush()
        return login_user
    return target


def resolve_auth(request: Request, db: Session = Depends(get_session)) -> AuthContext | None:
    locale = locale_from_request(request)
    token = request.cookies.get(COOKIE_NAME)
    authorization = request.headers.get("authorization") or ""

    if authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        if raw:
            from app.models import ApiToken

            token_hash = hash_secret(raw)
            api_token = db.scalar(
                select(ApiToken).where(
                    ApiToken.token_hash == token_hash,
                    ApiToken.revoked_at.is_(None),
                )
            )
            if api_token is None:
                abort(locale, ErrorCode.unauthorized)
            user = db.get(User, api_token.user_id)
            if user is None or user.disabled_at is not None:
                abort(locale, ErrorCode.unauthorized)
            locale = locale_from_request(request, user)
            org, membership = load_org_bundle(db, user)
            if user.must_change_password or _password_expired(user, org):
                abort(locale, ErrorCode.must_change_password)
            from app.services.billing import org_api_enabled

            if not org_api_enabled(org):
                abort(locale, ErrorCode.api_disabled)
            from app.rate_limit import enforce_bearer_api, get_rate_limits

            enforce_bearer_api(request, user.id, get_rate_limits(db), locale)
            return AuthContext(
                user=user,
                actor=user,
                org=org,
                membership=membership,
                session=None,
                via_api_token=True,
                locale=locale,
                impersonating=False,
            )

    if token:
        session_row = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_secret(token),
                AuthSession.expires_at > utcnow(),
            )
        )
        if session_row is None:
            return None
        login_user = db.get(User, session_row.user_id)
        if login_user is None or login_user.disabled_at is not None:
            return None
        effective = _effective_user(db, session_row, login_user)
        locale = locale_from_request(request, effective)
        org, membership = load_org_bundle(db, effective)
        now = utcnow()
        session_row.last_seen_at = now
        session_row.expires_at = now + timedelta(seconds=session_ttl_sec(get_instance_settings(db)))
        return AuthContext(
            user=effective,
            actor=login_user,
            org=org,
            membership=membership,
            session=session_row,
            via_api_token=False,
            locale=locale,
            impersonating=session_row.impersonate_user_id is not None,
        )
    return None


def require_auth(
    request: Request,
    db: Session = Depends(get_session),
) -> AuthContext:
    locale = locale_from_request(request)
    ctx = resolve_auth(request, db)
    if ctx is None:
        abort(locale, ErrorCode.unauthorized)
    must_change = ctx.user.must_change_password or _password_expired(ctx.user, ctx.org)
    if must_change and not ctx.is_instance_admin:
        path = request.url.path.rstrip("/") or "/"
        if (request.method, path) not in ALLOWED_WHEN_MUST_CHANGE and not path.startswith(
            "/api/v1/auth/password"
        ):
            if path != "/api/v1/me":
                abort(ctx.locale, ErrorCode.must_change_password)
    return ctx


def optional_auth(
    request: Request,
    db: Session = Depends(get_session),
) -> AuthContext | None:
    return resolve_auth(request, db)


_cached_session_ttl_sec: int | None = None


def normalize_session_ttl_hours(value: int) -> int:
    hours = int(value)
    if hours < MIN_SESSION_TTL_HOURS or hours > MAX_SESSION_TTL_HOURS:
        raise ValueError("session_ttl_hours out of range")
    return hours


def session_ttl_sec(settings: InstanceSettings) -> int:
    hours = settings.session_ttl_hours
    if hours is None:
        hours = DEFAULT_SESSION_TTL_HOURS
    return normalize_session_ttl_hours(hours) * 3600


def session_ttl_sec_from_db(db: Session) -> int:
    return session_ttl_sec(get_instance_settings(db))


def invalidate_session_ttl_cache() -> None:
    global _cached_session_ttl_sec
    _cached_session_ttl_sec = None


def cached_session_ttl_sec() -> int:
    global _cached_session_ttl_sec
    if _cached_session_ttl_sec is None:
        from app.db import SessionLocal

        with SessionLocal() as db:
            _cached_session_ttl_sec = session_ttl_sec_from_db(db)
    return _cached_session_ttl_sec


def get_instance_settings(db: Session):
    row = db.get(InstanceSettings, 1)
    if row is None:
        from app.services.import_platforms import default_allowed_extractors

        row = InstanceSettings(
            id=1,
            bootstrap_done=False,
            allow_new_orgs=True,
            asr_model="whisper",
            diarization_model="pyannote",
            import_enabled=True,
            import_allowed_extractors_json=default_allowed_extractors(),
            session_ttl_hours=DEFAULT_SESSION_TTL_HOURS,
        )
        db.add(row)
        db.flush()
    return row


def tariff_of(org: Organization) -> Tariff:
    return org.tariff

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
from app.routers.auth._body import SetupBody, SignupBody
from app.routers.auth._helpers import _locale, _norm_email
from app.routers.auth._router import router
from app.security import hash_password, hash_secret, new_api_token, new_reset_token, verify_password
from app.services.audit import write_audit
from app.services.auth_helpers import create_session, me_payload, me_with_csrf, public_base_url, revoke_user_auth, seed_default_tariff, sso_login_redirect
from app.timeutil import utcnow

from app.services.secrets_bootstrap import session_secret_configured
from app.rate_limit import client_ip, enforce_setup, enforce_signup, get_rate_limits
from app.schemas.auth_api import AuthUserBootstrapResponse, SetupStatusResponse, SignupTariffListResponse
from app.schemas.me import UserPublic
from app.schemas.org_api import TariffPublic
from app.services.billing import signup_balance
from app.cookies import issue_auth_cookies

@router.post("/setup", response_model=AuthUserBootstrapResponse)
def setup(body: SetupBody, request: Request, response: Response, db: Session = Depends(get_session, scope="function")) -> AuthUserBootstrapResponse:
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
    return AuthUserBootstrapResponse(status="ok", user=UserPublic.model_validate(user_public(user, "instance_admin")))


@router.post("/auth/signup", response_model=AuthUserBootstrapResponse)
def signup(body: SignupBody, request: Request, response: Response, db: Session = Depends(get_session, scope="function")) -> AuthUserBootstrapResponse:
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
    return AuthUserBootstrapResponse(status="ok", user=UserPublic.model_validate(user_public(user, "org_admin")))


def _tariff_org_count(db: Session, tariff_id: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Organization).where(Organization.tariff_id == tariff_id)) or 0
    )


@router.get("/auth/signup-tariffs", response_model=SignupTariffListResponse)
def signup_tariffs(request: Request, db: Session = Depends(get_session, scope="function")) -> SignupTariffListResponse:
    locale = locale_from_request(request)
    settings = get_instance_settings(db)
    if not settings.bootstrap_done or not settings.allow_new_orgs:
        return SignupTariffListResponse(items=[])
    rows = db.scalars(
        select(Tariff).where(Tariff.archived_at.is_(None), Tariff.available_on_signup.is_(True))
    ).all()
    return SignupTariffListResponse(
        items=[TariffPublic.model_validate(tariff_public(row, _tariff_org_count(db, row.id))) for row in rows]
    )


@router.get("/setup/status", response_model=SetupStatusResponse)
def setup_status(db: Session = Depends(get_session, scope="function")) -> SetupStatusResponse:
    settings = get_instance_settings(db)
    return SetupStatusResponse(bootstrap_done=bool(settings.bootstrap_done))

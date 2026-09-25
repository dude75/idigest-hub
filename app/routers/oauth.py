"""OAuth 2.1 authorization server endpoints (well-known, DCR, authorize, token)."""

from __future__ import annotations

import base64
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Form, Request
from starlette.responses import Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.cookies import issue_auth_cookies
from app.db import get_session
from app.deps import get_instance_settings, resolve_auth
from app.routers.auth import create_session, session_ttl_sec_from_db
from app.services.oauth_scopes import SUPPORTED_SCOPES
from app.services.oauth_provider import (
    authenticate_login_for_oauth,
    authorization_server_metadata,
    exchange_authorization_code,
    issue_authorization_code,
    jwks_document,
    mcp_resource_url,
    oauth_provider_enabled,
    provider_ready,
    public_base_url,
    refresh_access_token,
    register_client,
    user_oauth_blocked,
    validate_authorize_params,
)
from app.errors import ApiError, ErrorCode, error_payload
from app.i18n import t
from app.rate_limit import (
    client_ip as rate_limit_client_ip,
    enforce_oauth_register,
    enforce_oauth_token,
    get_rate_limits,
)
from app.services.oauth_pages import (
    oauth_blocked_page,
    oauth_client_redirect_page,
    oauth_consent_page,
    oauth_login_page,
    oauth_locale,
    oauth_message_page,
)
from app.services.oauth_scopes import scopes_to_string
from app.services.sso import begin_org_sso_login, sso_configured

log = logging.getLogger("app")

router = APIRouter(include_in_schema=False)

HUB_AUTH_MODE = "hub_auth_mode"
_OAUTH_ORG_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _oauth_disabled() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "oauth_disabled"})


def _oauth_rate_limited(exc: ApiError) -> JSONResponse:
    headers = dict(exc.headers or {})
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(ErrorCode.rate_limited, t("en", ErrorCode.rate_limited.value)),
        headers=headers,
    )


@router.get("/.well-known/oauth-authorization-server")
def well_known_authorization_server(db: Session = Depends(get_session, scope="function")) -> JSONResponse:
    if not oauth_provider_enabled():
        return _oauth_disabled()
    metadata = authorization_server_metadata(db)
    if metadata is None:
        return JSONResponse(status_code=503, content={"error": "oauth_misconfigured"})
    return JSONResponse(metadata)


@router.get("/.well-known/jwks.json")
def well_known_jwks() -> JSONResponse:
    if not oauth_provider_enabled():
        return _oauth_disabled()
    return JSONResponse(jwks_document())


@router.get("/.well-known/oauth-protected-resource/mcp")
def oauth_protected_resource_metadata(db: Session = Depends(get_session, scope="function")) -> JSONResponse:
    if not provider_ready(db):
        return JSONResponse(status_code=404, content={"error": "oauth_disabled"})
    resource = mcp_resource_url(db=db)
    issuer = public_base_url(db)
    assert resource and issuer
    return JSONResponse(
        {
            "resource": resource,
            "authorization_servers": [issuer],
            "scopes_supported": sorted(SUPPORTED_SCOPES),
            "bearer_methods_supported": ["header"],
        }
    )


@router.post("/oauth/register")
async def oauth_dynamic_client_registration(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> JSONResponse:
    if not provider_ready(db):
        return JSONResponse(status_code=503, content={"error": "oauth_misconfigured"})
    try:
        enforce_oauth_register(rate_limit_client_ip(request), get_rate_limits(db), "en")
    except ApiError as exc:
        return _oauth_rate_limited(exc)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_client_metadata"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"error": "invalid_client_metadata"})
    try:
        client, raw_secret = register_client(db, body)
        db.commit()
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    payload: dict[str, Any] = {
        "client_id": client.client_id,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris_json,
        "grant_types": client.grant_types_json,
        "response_types": client.response_types_json,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
        "client_id_issued_at": int(client.created_at.timestamp()),
    }
    if raw_secret:
        payload["client_secret"] = raw_secret
    return JSONResponse(status_code=201, content=payload)


def _authorize_query(request: Request) -> dict[str, str]:
    return {key: value for key, value in request.query_params.items()}


@router.get("/oauth/authorize")
def oauth_authorize_get(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    locale = oauth_locale(request)
    if not provider_ready(db):
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=t(locale, "oauth_provider_unconfigured"),
            status_code=503,
        )
    params = _authorize_query(request)
    try:
        client, scopes, resource = validate_authorize_params(
            db,
            client_id=params.get("client_id", ""),
            redirect_uri=params.get("redirect_uri", ""),
            response_type=params.get("response_type", ""),
            scope=params.get("scope"),
            code_challenge=params.get("code_challenge", ""),
            code_challenge_method=params.get("code_challenge_method", ""),
            resource=params.get("resource"),
        )
    except ValueError as exc:
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=str(exc),
            status_code=400,
        )

    ctx = resolve_auth(request, db)
    if ctx is None or ctx.session is None or ctx.impersonating:
        return _login_html(request, db, _oauth_authorize_params(params))
    blocked = user_oauth_blocked(ctx.user, db)
    if blocked:
        return oauth_blocked_page(request, blocked, user=ctx.user)

    scope_str = scopes_to_string(scopes)
    hidden = _encode_oauth_params(
        {
            "client_id": params["client_id"],
            "redirect_uri": params["redirect_uri"],
            "response_type": "code",
            "scope": scope_str,
            "code_challenge": params["code_challenge"],
            "code_challenge_method": params["code_challenge_method"],
            "resource": resource,
            "state": params.get("state", ""),
        }
    )
    return oauth_consent_page(
        request,
        client_name=client.client_name,
        scopes=scopes,
        hidden_params=hidden,
    )


def _encode_oauth_params(params: dict[str, str]) -> str:
    raw = urlencode(params)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_oauth_params(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        if raw.startswith("client_id="):
            decoded = raw
        else:
            padded = raw + "=" * (-len(raw) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return {}
    return {k: v[0] for k, v in parse_qs(decoded, keep_blank_values=True).items()}


@router.post("/oauth/authorize")
def oauth_authorize_confirm(
    request: Request,
    oauth_params: str = Form(""),
    confirm: str = Form(""),
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    locale = oauth_locale(request)
    if not provider_ready(db) or confirm != "1":
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=t(locale, "oauth_invalid_request"),
            status_code=400,
        )

    parsed = _decode_oauth_params(oauth_params)
    try:
        client, scopes, resource = validate_authorize_params(
            db,
            client_id=parsed.get("client_id", ""),
            redirect_uri=parsed.get("redirect_uri", ""),
            response_type=parsed.get("response_type", ""),
            scope=parsed.get("scope"),
            code_challenge=parsed.get("code_challenge", ""),
            code_challenge_method=parsed.get("code_challenge_method", ""),
            resource=parsed.get("resource"),
        )
    except ValueError as exc:
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=str(exc),
            status_code=400,
        )

    ctx = resolve_auth(request, db)
    if ctx is None or ctx.session is None or ctx.impersonating:
        return oauth_message_page(
            request,
            title_key="oauth_title_sign_in",
            message=t(locale, "oauth_sign_in_required"),
            status_code=401,
        )
    blocked = user_oauth_blocked(ctx.user, db)
    if blocked:
        return oauth_blocked_page(request, blocked, user=ctx.user)

    code = issue_authorization_code(
        db,
        client=client,
        user_id=ctx.user.id,
        redirect_uri=parsed["redirect_uri"],
        scopes=scopes,
        resource=resource,
        code_challenge=parsed["code_challenge"],
        code_challenge_method=parsed["code_challenge_method"],
    )
    db.commit()
    query = urlencode({"code": code, "state": parsed.get("state", "")})
    separator = "&" if "?" in parsed["redirect_uri"] else "?"
    redirect_url = f"{parsed['redirect_uri']}{separator}{query}"
    log.info("oauth authorize: redirecting to client %s", parsed["redirect_uri"])
    return oauth_client_redirect_page(request, redirect_url)


def _oauth_authorize_params(params: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in params.items() if key != HUB_AUTH_MODE}


def _login_auth_mode(params: dict[str, str]) -> str:
    mode = (params.get(HUB_AUTH_MODE) or "email").strip().lower()
    return mode if mode in ("email", "sso") else "email"


def _login_prefill_org_id(db: Session, params: dict[str, str]) -> str:
    login_hint = (params.get("login_hint") or "").strip().lower()
    if not login_hint:
        return ""
    from sqlalchemy import select

    from app.models import Membership, Organization, User

    user = db.scalar(select(User).where(User.email == login_hint))
    if user is None:
        return ""
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    if membership is None:
        return ""
    org = db.get(Organization, membership.org_id)
    if org is None or not sso_configured(org) or not org.sso_enabled:
        return ""
    return org.id


def _validate_oauth_authorize_params(db: Session, params: dict[str, str]) -> None:
    validate_authorize_params(
        db,
        client_id=params.get("client_id", ""),
        redirect_uri=params.get("redirect_uri", ""),
        response_type=params.get("response_type", ""),
        scope=params.get("scope"),
        code_challenge=params.get("code_challenge", ""),
        code_challenge_method=params.get("code_challenge_method", ""),
        resource=params.get("resource"),
    )


def _login_html(
    request: Request,
    db: Session,
    params: dict[str, str],
    *,
    auth_mode: str | None = None,
    prefill_org_id: str | None = None,
    error_message: str | None = None,
) -> HTMLResponse:
    authorize_params = _oauth_authorize_params(params)
    mode = auth_mode or _login_auth_mode(params)
    org_hint = prefill_org_id if prefill_org_id is not None else _login_prefill_org_id(db, authorize_params)
    if org_hint and mode == "email" and (params.get("login_hint") or "").strip():
        mode = "sso"
    hidden = _encode_oauth_params(authorize_params)
    return oauth_login_page(
        request,
        hidden_params=hidden,
        authorize_params=authorize_params,
        auth_mode=mode,
        prefill_org_id=org_hint,
        error_message=error_message,
    )


def _begin_oauth_sso(
    request: Request,
    db: Session,
    *,
    org_id: str,
    oauth_params: str,
) -> Response:
    locale = oauth_locale(request)
    if not provider_ready(db):
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=t(locale, "oauth_provider_unconfigured"),
            status_code=503,
        )
    params = _decode_oauth_params(oauth_params)
    try:
        _validate_oauth_authorize_params(db, params)
    except ValueError as exc:
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=str(exc),
            status_code=400,
        )
    from app.models import Organization

    org = db.get(Organization, org_id)
    if org is None:
        return _login_html(
            request,
            db,
            params,
            auth_mode="sso",
            prefill_org_id=org_id,
            error_message=t(locale, "oauth_org_id_invalid"),
        )
    settings = get_instance_settings(db)
    public_base = (settings.public_base_url or "").strip().rstrip("/")
    if not public_base:
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=t(locale, "oauth_provider_unconfigured"),
            status_code=503,
        )
    try:
        idp_url = begin_org_sso_login(
            org=org,
            public_base_url=public_base,
            oauth_authorize_query=urlencode(params),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "sso_disabled":
            message = t(locale, "oauth_sso_disabled")
        elif code == "sso_misconfigured":
            message = t(locale, "oauth_sso_not_configured")
        else:
            message = t(locale, "oauth_invalid_request")
        return _login_html(
            request,
            db,
            params,
            auth_mode="sso",
            prefill_org_id=org_id,
            error_message=message,
        )
    except Exception:
        return _login_html(
            request,
            db,
            params,
            auth_mode="sso",
            prefill_org_id=org_id,
            error_message=t(locale, "oauth_sso_not_configured"),
        )
    return RedirectResponse(idp_url, status_code=302)


@router.get("/oauth/sso/start")
def oauth_sso_start_get(
    request: Request,
    org_id: str = "",
    oauth_params: str = "",
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    org_id = org_id.strip()
    if not _OAUTH_ORG_ID_RE.match(org_id):
        locale = oauth_locale(request)
        params = _decode_oauth_params(oauth_params)
        return _login_html(
            request,
            db,
            params,
            auth_mode="sso",
            prefill_org_id=org_id,
            error_message=t(locale, "oauth_org_id_invalid"),
        )
    return _begin_oauth_sso(request, db, org_id=org_id, oauth_params=oauth_params)


@router.post("/oauth/sso")
def oauth_sso_start_post(
    request: Request,
    org_id: str = Form(""),
    oauth_params: str = Form(""),
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    org_id = org_id.strip()
    if not _OAUTH_ORG_ID_RE.match(org_id):
        locale = oauth_locale(request)
        params = _decode_oauth_params(oauth_params)
        return _login_html(
            request,
            db,
            params,
            auth_mode="sso",
            prefill_org_id=org_id,
            error_message=t(locale, "oauth_org_id_invalid"),
        )
    return _begin_oauth_sso(request, db, org_id=org_id, oauth_params=oauth_params)


@router.post("/oauth/login")
def oauth_login(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    oauth_params: str = Form(""),
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    locale = oauth_locale(request)
    if not provider_ready(db):
        return oauth_message_page(
            request,
            title_key="oauth_title_error",
            message=t(locale, "oauth_provider_unconfigured"),
            status_code=503,
        )
    params = _decode_oauth_params(oauth_params)
    user = authenticate_login_for_oauth(db, email=email, password=password)
    if user is None:
        return _login_html(
            request,
            db,
            params,
            auth_mode="email",
            error_message=t(locale, "invalid_credentials"),
        )
    raw = create_session(db, user.id)
    db.commit()
    query = urlencode(params)
    redirect = RedirectResponse(f"/oauth/authorize?{query}", status_code=303)
    issue_auth_cookies(redirect, raw, max_age=session_ttl_sec_from_db(db))
    return redirect


@router.post("/oauth/token")
async def oauth_token(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> JSONResponse:
    if not provider_ready(db):
        return JSONResponse(status_code=503, content={"error": "oauth_misconfigured"})
    try:
        enforce_oauth_token(rate_limit_client_ip(request), get_rate_limits(db), "en")
    except ApiError as exc:
        return _oauth_rate_limited(exc)
    form = await request.form()
    grant_type = (form.get("grant_type") or "").strip()
    client_id = (form.get("client_id") or "").strip()
    client_secret = (form.get("client_secret") or "").strip() or None
    try:
        if grant_type == "authorization_code":
            result = exchange_authorization_code(
                db,
                code=(form.get("code") or "").strip(),
                client_id=client_id,
                redirect_uri=(form.get("redirect_uri") or "").strip(),
                code_verifier=(form.get("code_verifier") or "").strip(),
                client_secret=client_secret,
            )
        elif grant_type == "refresh_token":
            result = refresh_access_token(
                db,
                refresh_token=(form.get("refresh_token") or "").strip(),
                client_id=client_id,
                client_secret=client_secret,
                resource=(form.get("resource") or "").strip() or None,
            )
        else:
            return JSONResponse(status_code=400, content={"error": "unsupported_grant_type"})
        db.commit()
    except ValueError as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return JSONResponse(result)

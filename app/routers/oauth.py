"""OAuth 2.1 authorization server endpoints (well-known, DCR, authorize, token)."""

from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Form, Request
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
from app.services.oauth_scopes import scopes_to_string
from app.services.sso import sso_login_url

log = logging.getLogger("app")

router = APIRouter(include_in_schema=False)


def _oauth_disabled() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "oauth_disabled"})


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
    if not provider_ready(db):
        return HTMLResponse("OAuth provider is not configured.", status_code=503)
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
        return HTMLResponse(f"Authorization error: {exc}", status_code=400)

    ctx = resolve_auth(request, db)
    if ctx is None or ctx.session is None or ctx.impersonating:
        return _login_html(db, params)
    blocked = user_oauth_blocked(ctx.user, db)
    if blocked:
        return HTMLResponse(f"Complete account setup before authorizing apps ({blocked}).", status_code=403)

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
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Authorize</title></head>
<body>
  <p><strong>{client.client_name}</strong> requests access to idigest with scopes:</p>
  <ul><li>{scope_str}</li></ul>
  <form method="post" action="/oauth/authorize">
    <input type="hidden" name="confirm" value="1"/>
    <input type="hidden" name="oauth_params" value="{hidden}"/>
    <button type="submit">Allow</button>
  </form>
</body></html>"""
    return HTMLResponse(html)


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
            decoded = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8")
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
    if not provider_ready(db) or confirm != "1":
        return HTMLResponse("Invalid request.", status_code=400)

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
        return HTMLResponse(f"Authorization error: {exc}", status_code=400)

    ctx = resolve_auth(request, db)
    if ctx is None or ctx.session is None or ctx.impersonating:
        return HTMLResponse("Sign in required.", status_code=401)
    if user_oauth_blocked(ctx.user, db):
        return HTMLResponse("Account not ready for API access.", status_code=403)

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
    return RedirectResponse(f"{parsed['redirect_uri']}{separator}{query}", status_code=302)


def _login_html(db: Session, params: dict[str, str]) -> HTMLResponse:
    settings = get_instance_settings(db)
    base = (settings.public_base_url or "").strip().rstrip("/")
    sso_link = ""
    from sqlalchemy import select
    from app.models import Membership, Organization

    # Show SSO link for first org with SSO (best-effort v1).
    membership = None
    if params.get("login_hint"):
        from app.models import User

        user = db.scalar(select(User).where(User.email == params["login_hint"].strip().lower()))
        if user:
            membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    org = db.get(Organization, membership.org_id) if membership else None
    if org and base:
        url = sso_login_url(base, org.id)
        if url:
            sso_link = f'<p><a href="{url}">Sign in with SSO</a></p>'
    hidden = _encode_oauth_params(params)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Sign in</title></head>
<body>
  <p>Sign in to idigest to authorize the application.</p>
  {sso_link}
  <form method="post" action="/oauth/login">
    <input type="hidden" name="oauth_params" value="{hidden}"/>
    <label>Email <input name="email" type="email" required/></label><br/>
    <label>Password <input name="password" type="password" required/></label><br/>
    <button type="submit">Sign in</button>
  </form>
</body></html>"""
    return HTMLResponse(html)


@router.post("/oauth/login")
def oauth_login(
    email: str = Form(""),
    password: str = Form(""),
    oauth_params: str = Form(""),
    db: Session = Depends(get_session, scope="function"),
) -> Response:
    if not provider_ready(db):
        return HTMLResponse("OAuth not configured.", status_code=503)
    params = _decode_oauth_params(oauth_params)
    user = authenticate_login_for_oauth(db, email=email, password=password)
    if user is None:
        return _login_html(db, params)
    raw = create_session(db, user.id)
    db.commit()
    query = urlencode(params)
    redirect = RedirectResponse(f"/oauth/authorize?{query}", status_code=302)
    issue_auth_cookies(redirect, raw, max_age=session_ttl_sec_from_db(db))
    return redirect


@router.post("/oauth/token")
async def oauth_token(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> JSONResponse:
    if not provider_ready(db):
        return JSONResponse(status_code=503, content={"error": "oauth_misconfigured"})
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

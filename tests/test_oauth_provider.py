"""OAuth 2.1 authorization server (MCP integration)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login, setup_admin, signup

MCP_RESOURCE = "https://hub.test/mcp"
REDIRECT_URI = "https://owui.test/oauth/clients/test/callback"


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _enable_oauth(client, monkeypatch):
    setup_admin(client)
    monkeypatch.setenv("OAUTH_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("OAUTH_MCP_RESOURCE_URL", MCP_RESOURCE)
    from app.config import get_settings

    get_settings.cache_clear()
    patched = client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.test"})
    assert patched.status_code == 200, patched.text


def _register_client(client) -> str:
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "Open WebUI Test",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


def _org_user_session(client) -> tuple[str, str]:
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    assert tariffs
    email = "oauth-user@example.com"
    password = "oauthpass1"
    signup(client, email, password, tariffs[0]["id"])
    login(client, email, password)
    return email, password


def test_oauth_disabled_by_default(client):
    assert client.get("/.well-known/oauth-authorization-server").status_code == 404


def test_oauth_mcp_scopes_supported(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    from app.services.oauth_scopes import SCOPE_SUMMARIES_READ, SUPPORTED_SCOPES, validate_requested_scopes

    meta = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert SCOPE_SUMMARIES_READ in meta["scopes_supported"]
    assert meta["scopes_supported"] == sorted(SUPPORTED_SCOPES)
    granted = validate_requested_scopes(frozenset({"summaries:read", "skills:read", "tasks:write"}))
    assert granted == frozenset({"summaries:read", "skills:read", "tasks:write"})
    assert validate_requested_scopes(frozenset()) == SUPPORTED_SCOPES


def test_oauth_consent_lists_granted_scopes(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    _org_user_session(client)
    client_id = _register_client(client)
    _, challenge = _pkce_pair()
    from app.i18n import t
    from app.services.oauth_scopes import SCOPE_ORDER, SCOPE_TRANSCRIPTS_READ, scope_label_key

    all_labels = [t("en", scope_label_key(scope)) for scope in SCOPE_ORDER]
    omitted = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        },
    )
    assert omitted.status_code == 200
    for label in all_labels:
        assert label in omitted.text

    transcripts_only = t("en", scope_label_key(SCOPE_TRANSCRIPTS_READ))
    narrowed = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE_TRANSCRIPTS_READ,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        },
    )
    assert narrowed.status_code == 200
    assert transcripts_only in narrowed.text
    for label in all_labels:
        if label != transcripts_only:
            assert label not in narrowed.text


def test_oauth_login_post_rejects_bad_password(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    _org_user_session(client)
    client_id = _register_client(client)
    verifier, challenge = _pkce_pair()
    authorize = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "transcripts:read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 200
    from app.routers.oauth import _encode_oauth_params

    oauth_flat = {
        key: values[0]
        for key, values in parse_qs(urlparse(str(authorize.request.url)).query).items()
    }
    login = client.post(
        "/oauth/login",
        data={
            "email": "nobody@example.com",
            "password": "wrongpass1",
            "oauth_params": _encode_oauth_params(oauth_flat),
        },
        follow_redirects=False,
    )
    assert login.status_code == 200
    assert "oauth-page" in login.text
    assert "alert-error" in login.text


def test_oauth_unknown_path_styled_html(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    response = client.get("/oauth/not-a-real-endpoint")
    assert response.status_code == 404
    assert "auth-layout" in response.text
    assert "alert-error" in response.text


def test_oauth_unexpected_error_page_markup():
    from starlette.requests import Request

    from app.services.oauth_pages import oauth_unexpected_error_page

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/oauth/login",
            "headers": [(b"accept-language", b"en")],
            "query_string": b"",
            "scheme": "https",
            "server": ("test", 443),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
        }
    )
    response = oauth_unexpected_error_page(request)
    assert response.status_code == 500
    assert "auth-layout" in response.body.decode()
    assert "alert-error" in response.body.decode()
    assert "simulated" not in response.body.decode()


def test_mcp_protected_resource_metadata(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    monkeypatch.delenv("OAUTH_MCP_RESOURCE_URL", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == "https://hub.test/mcp"
    assert body["authorization_servers"] == ["https://hub.test"]


def _oauth_access_token(client, monkeypatch, *, scope: str | None) -> str:
    _enable_oauth(client, monkeypatch)
    client_id = _register_client(client)
    _org_user_session(client)
    verifier, challenge = _pkce_pair()
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": MCP_RESOURCE,
        "state": "xyz",
    }
    if scope is not None:
        params["scope"] = scope
    authorize = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert authorize.status_code == 200
    from app.routers.oauth import _encode_oauth_params

    oauth_query = dict(parse_qs(urlparse(str(authorize.request.url)).query))
    oauth_flat = {key: values[0] for key, values in oauth_query.items()}
    confirm = client.post(
        "/oauth/authorize",
        data={"confirm": "1", "oauth_params": _encode_oauth_params(oauth_flat)},
        follow_redirects=False,
    )
    assert confirm.status_code == 200
    import re

    match = re.search(rf'href="({re.escape(REDIRECT_URI)}\?[^"]+)"', confirm.text)
    assert match is not None, confirm.text[:500]
    code = parse_qs(urlparse(match.group(1)).query)["code"][0]
    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert token.status_code == 200, token.text
    return token.json()["access_token"]


def test_oauth_omitted_scope_grants_full_library(client, monkeypatch):
    from app.services.oauth_scopes import SCOPE_AUDIO_READ, SCOPE_TASKS_WRITE, normalize_scopes
    from app.services.oauth_provider import verify_access_token
    from app.services.hub_mcp_token_verifier import HubMcpTokenVerifier

    access = _oauth_access_token(client, monkeypatch, scope=None)
    import app.db as hub_db

    with hub_db.SessionLocal() as session:
        payload = verify_access_token(session, access)
        assert payload is not None
        granted = normalize_scopes(payload.get("scope"))
        assert SCOPE_AUDIO_READ in granted
        assert SCOPE_TASKS_WRITE in granted

    import asyncio

    verified = asyncio.run(HubMcpTokenVerifier().verify_token(access))
    assert verified is not None
    assert SCOPE_AUDIO_READ in verified.scopes
    assert SCOPE_TASKS_WRITE in verified.scopes


def test_oauth_pkce_flow_and_transcripts(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    metadata = client.get("/.well-known/oauth-authorization-server")
    assert metadata.status_code == 200
    assert metadata.json()["issuer"] == "https://hub.test"

    client_id = _register_client(client)
    _org_user_session(client)

    verifier, challenge = _pkce_pair()
    authorize = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "transcripts:read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 200
    assert "Allow" in authorize.text

    from app.routers.oauth import _encode_oauth_params

    oauth_query = dict(parse_qs(urlparse(str(authorize.request.url)).query))
    oauth_flat = {key: values[0] for key, values in oauth_query.items()}
    confirm = client.post(
        "/oauth/authorize",
        data={"confirm": "1", "oauth_params": _encode_oauth_params(oauth_flat)},
        follow_redirects=False,
    )
    assert confirm.status_code == 200
    import re

    match = re.search(rf'href="({re.escape(REDIRECT_URI)}\?[^"]+)"', confirm.text)
    assert match is not None, confirm.text[:500]
    location = match.group(1)
    code = parse_qs(urlparse(location).query)["code"][0]

    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert token.status_code == 200, token.text
    access = token.json()["access_token"]

    transcripts = client.get("/api/v1/transcripts", headers={"Authorization": f"Bearer {access}"})
    assert transcripts.status_code == 200

    no_scope = client.post(
        "/oauth/register",
        json={
            "client_name": "Other",
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
        },
    )
    assert no_scope.status_code == 201


def test_mcp_server_sees_session_local_after_engine_init(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    import app.db as db_module
    from app.services import mcp_integration

    mcp_integration._mcp_server = None
    mcp_integration._mcp_starlette = None
    db_module.get_engine()
    assert db_module.SessionLocal is not None
    mcp_integration.get_mcp_server()
    mcp_integration._mcp_server = None
    mcp_integration._mcp_starlette = None


def test_mcp_http_routes_registered_when_oauth_enabled(client, monkeypatch, tmp_path):
    _enable_oauth(client, monkeypatch)
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()
    mcp_paths = sorted(
        r.path for r in app.router.routes if getattr(r, "path", None) in ("/mcp", "/mcp/")
    )
    assert mcp_paths == ["/mcp", "/mcp/"]


def test_oauth_authorize_blocked_instance_admin_without_org(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    client_id = _register_client(client)
    verifier, challenge = _pkce_pair()
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "transcripts:read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        },
    )
    assert response.status_code == 403
    assert "organization admins and members" in response.text or "администраторам и участникам" in response.text


def test_oauth_authorize_blocked_api_disabled_styled(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    from tests.test_billing import create_tariff

    no_api = create_tariff(client, name="NoAPI-OAuth", api_enabled=False, signup_credit="1.00")
    email = "noapi-oauth@example.com"
    signup(client, email, "passpass1", no_api["id"])
    login(client, email, "passpass1")
    client_id = _register_client(client)
    verifier, challenge = _pkce_pair()
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "transcripts:read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        },
    )
    assert response.status_code == 403
    assert "oauth-page" in response.text
    assert "auth-layout" in response.text
    assert "auth-topbar" in response.text
    assert "github-link" in response.text
    assert "api_disabled" not in response.text
    assert "Cannot authorize" in response.text or "Нельзя выдать доступ" in response.text


def _authorize_login_page(client, monkeypatch) -> tuple[str, str, dict[str, str]]:
    from tests.conftest import logout

    _enable_oauth(client, monkeypatch)
    client_id = _register_client(client)
    logout(client)
    verifier, challenge = _pkce_pair()
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "transcripts:read",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": MCP_RESOURCE,
        "state": "abc",
    }
    authorize = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert authorize.status_code == 200, authorize.text
    assert "auth-segment" in authorize.text
    assert "Continue with SSO" in authorize.text or "Продолжить через SSO" in authorize.text
    from app.routers.oauth import _encode_oauth_params

    return client_id, verifier, {**params, "oauth_params": _encode_oauth_params(params)}


def _configure_sso_on_hub_test(client) -> str:
    org_id = client.get("/api/v1/me").json()["org"]["id"]
    patched = client.patch(
        "/api/v1/org/sso",
        json={
            "issuer": "https://keycloak.example/realms/demo",
            "client_id": "hub",
            "client_secret": "secret",
            "enabled": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["org_id"] == org_id
    return org_id


def test_oauth_login_page_sso_tab_and_mode_links(client, monkeypatch):
    _client_id, _verifier, ctx = _authorize_login_page(client, monkeypatch)
    sso = client.get(
        "/oauth/authorize",
        params={
            "client_id": ctx["client_id"],
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "transcripts:read",
            "code_challenge": ctx["code_challenge"],
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
            "hub_auth_mode": "sso",
        },
    )
    assert sso.status_code == 200
    assert 'name="org_id"' in sso.text
    assert 'action="/oauth/sso"' in sso.text
    assert 'action="/oauth/login" class="stack auth-panel auth-panel-hidden"' in sso.text
    assert 'action="/oauth/sso" class="stack auth-panel"' in sso.text


def test_oauth_sso_flow_returns_to_consent(client, monkeypatch):
    from tests.conftest import logout
    from urllib.parse import parse_qs, urlparse

    from app.services import sso as sso_service

    _enable_oauth(client, monkeypatch)
    client_id = _register_client(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "sso-oauth@example.com", "ssopass12", tariffs[0]["id"])
    login(client, "sso-oauth@example.com", "ssopass12")
    org_id = _configure_sso_on_hub_test(client)
    logout(client)

    verifier, challenge = _pkce_pair()
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "transcripts:read",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": MCP_RESOURCE,
        "state": "sso-state",
    }
    login_page = client.get("/oauth/authorize", params=params, follow_redirects=False)
    assert login_page.status_code == 200
    from app.routers.oauth import _encode_oauth_params

    oauth_params = _encode_oauth_params(params)

    monkeypatch.setattr(
        sso_service,
        "fetch_oidc_config",
        lambda issuer: {"authorization_endpoint": "https://keycloak.example/authorize"},
    )
    start = client.post(
        "/oauth/sso",
        data={"org_id": org_id, "oauth_params": oauth_params},
        follow_redirects=False,
    )
    assert start.status_code == 200, start.text
    assert "keycloak.example/authorize" in start.text

    monkeypatch.setattr("app.routers.auth.exchange_code", lambda **kwargs: {"id_token": "token"})
    monkeypatch.setattr(
        "app.routers.auth.validate_id_token",
        lambda **kwargs: {"sub": "kc-oauth", "email": "sso-oauth@example.com"},
    )
    import html as html_module
    import re

    idp_match = re.search(r'href="(https://keycloak\.example/authorize[^"]+)"', start.text)
    assert idp_match is not None, start.text[:500]
    idp_url = html_module.unescape(idp_match.group(1))
    state = parse_qs(urlparse(idp_url).query)["state"][0]
    callback = client.get(
        f"/api/v1/auth/sso/{org_id}/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code == 302, callback.text
    assert callback.headers["location"].startswith("/oauth/authorize?")
    assert "hub_auth_mode=sso" in callback.headers["location"]

    consent = client.get(callback.headers["location"], follow_redirects=False)
    assert consent.status_code == 200, consent.text
    assert "Allow" in consent.text


def test_oauth_sso_callback_redirects_to_app_without_authorize_query(client, monkeypatch):
    from app.services import sso as sso_service
    from tests.conftest import setup_admin

    setup_admin(client)
    patched = client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.example"})
    assert patched.status_code == 200
    from tests.conftest import default_tariff_id, login_ready, logout, signup

    tariff_id = default_tariff_id(client)
    signup(client, "plain-sso@example.com", "plainpass1", tariff_id)
    login_ready(client, "plain-sso@example.com", "plainpass1")
    org_id = client.get("/api/v1/me").json()["org"]["id"]
    client.patch(
        "/api/v1/org/sso",
        json={
            "issuer": "https://keycloak.example/realms/demo",
            "client_id": "hub",
            "client_secret": "secret",
            "enabled": True,
        },
    )
    logout(client)

    monkeypatch.setattr("app.routers.auth.exchange_code", lambda **kwargs: {"id_token": "token"})
    monkeypatch.setattr(
        "app.routers.auth.validate_id_token",
        lambda **kwargs: {"sub": "kc-plain", "email": "plain-sso@example.com"},
    )
    state, _nonce, _challenge = sso_service.make_oauth_state(org_id)
    callback = client.get(
        f"/api/v1/auth/sso/{org_id}/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/app"


def test_pat_still_works(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    created = client.post("/api/v1/auth/tokens", json={"name": "test"})
    assert created.status_code == 200, created.text
    raw = created.json()["token"]
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {raw}"})
    assert me.status_code == 200

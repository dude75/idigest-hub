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


def test_pat_still_works(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    created = client.post("/api/v1/auth/tokens", json={"name": "test"})
    assert created.status_code == 200, created.text
    raw = created.json()["token"]
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {raw}"})
    assert me.status_code == 200

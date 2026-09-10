"""SSO (OIDC / Keycloak) per organization."""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from conftest import (
    default_tariff_id,
    err_code,
    login,
    login_ready,
    logout,
    me,
    open_db,
    setup_admin,
    signup,
)


def _configure_public_url(client, url: str = "https://hub.example") -> None:
    response = client.patch("/api/v1/instance/settings", json={"public_base_url": url})
    assert response.status_code == 200, response.text


def _configure_sso(client, *, enabled: bool = False) -> str:
    org_id = me(client)["org"]["id"]
    body = {
        "issuer": "https://keycloak.example/realms/demo",
        "client_id": "hub",
        "client_secret": "secret",
        "enabled": enabled,
    }
    response = client.patch("/api/v1/org/sso", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configured"] is True
    assert payload["enabled"] is enabled
    assert payload["org_id"] == org_id
    assert payload["callback_url"] == f"https://hub.example/api/v1/auth/sso/{org_id}/callback"
    assert payload["login_url"] == f"https://hub.example/sso/{org_id}"
    return org_id


def _create_member(client, email: str = "member@example.com", password: str = "memberpass1") -> None:
    response = client.post(
        "/api/v1/org/users",
        json={"email": email, "password": password, "role": "org_member"},
    )
    assert response.status_code == 200, response.text


def test_password_login_blocked_for_member_when_sso_configured(client):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    _configure_sso(client, enabled=False)
    _create_member(client)
    logout(client)

    response = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "memberpass1"})
    assert response.status_code == 403
    assert err_code(response) == "sso_login_required"


def test_password_login_allowed_for_org_admin_when_sso_configured(client):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    _configure_sso(client, enabled=False)
    logout(client)

    login(client, "orgadmin@example.com", "orgadminpass1")


def test_sso_start_requires_enabled(client):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    org_id = _configure_sso(client, enabled=False)
    logout(client)

    response = client.get(f"/api/v1/auth/sso/{org_id}/start", follow_redirects=False)
    assert response.status_code == 403
    assert err_code(response) == "sso_disabled"


def test_sso_callback_provisions_member(client, monkeypatch):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    org_id = _configure_sso(client, enabled=True)
    logout(client)

    from app.services import sso as sso_service

    monkeypatch.setattr("app.routers.auth.exchange_code", lambda **kwargs: {"id_token": "token"})
    monkeypatch.setattr(
        "app.routers.auth.validate_id_token",
        lambda **kwargs: {"sub": "kc-1", "email": "newbie@example.com"},
    )

    state, _nonce = sso_service.make_oauth_state(org_id)
    query = urlencode({"code": "abc", "state": state})
    response = client.get(
        f"/api/v1/auth/sso/{org_id}/callback?{query}",
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    assert response.headers["location"] == "https://hub.example/app"

    payload = me(client)
    assert payload["user"]["email"] == "newbie@example.com"
    assert payload["user"]["role"] == "org_member"
    assert payload["user"]["auth_provider"] == "oidc"


def test_sso_callback_merges_existing_member(client, monkeypatch):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    org_id = _configure_sso(client, enabled=True)
    _create_member(client, email="member@example.com")
    logout(client)

    from app.services import sso as sso_service

    monkeypatch.setattr("app.routers.auth.exchange_code", lambda **kwargs: {"id_token": "token"})
    monkeypatch.setattr(
        "app.routers.auth.validate_id_token",
        lambda **kwargs: {"sub": "kc-member", "email": "member@example.com"},
    )

    state, _nonce = sso_service.make_oauth_state(org_id)
    query = urlencode({"code": "abc", "state": state})
    response = client.get(
        f"/api/v1/auth/sso/{org_id}/callback?{query}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    payload = me(client)
    assert payload["user"]["email"] == "member@example.com"
    assert payload["user"]["auth_provider"] == "oidc"


def _mock_validate_id_token_jwt(monkeypatch, *, claims: dict):
    from app.services import sso as sso_service

    monkeypatch.setattr(
        sso_service,
        "fetch_oidc_config",
        lambda issuer: {"issuer": issuer, "jwks_uri": "https://keycloak.example/jwks"},
    )

    class FakeSigningKey:
        key = "fake"

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    monkeypatch.setattr(sso_service, "PyJWKClient", lambda jwks_uri: FakeJWKClient())
    monkeypatch.setattr(sso_service.jwt, "decode", lambda *args, **kwargs: claims)


def test_validate_id_token_requires_nonce(monkeypatch):
    from app.services import sso as sso_service

    org = SimpleNamespace(
        sso_issuer="https://keycloak.example/realms/demo",
        sso_client_id="hub",
    )
    _mock_validate_id_token_jwt(
        monkeypatch,
        claims={"sub": "user-1", "exp": 9999999999, "iat": 1},
    )

    with pytest.raises(ValueError, match="nonce mismatch"):
        sso_service.validate_id_token(org=org, id_token="token", nonce="expected-nonce")


def test_validate_id_token_rejects_nonce_mismatch(monkeypatch):
    from app.services import sso as sso_service

    org = SimpleNamespace(
        sso_issuer="https://keycloak.example/realms/demo",
        sso_client_id="hub",
    )
    _mock_validate_id_token_jwt(
        monkeypatch,
        claims={"sub": "user-1", "exp": 9999999999, "iat": 1, "nonce": "other-nonce"},
    )

    with pytest.raises(ValueError, match="nonce mismatch"):
        sso_service.validate_id_token(org=org, id_token="token", nonce="expected-nonce")


def test_validate_id_token_accepts_matching_nonce(monkeypatch):
    from app.services import sso as sso_service

    org = SimpleNamespace(
        sso_issuer="https://keycloak.example/realms/demo",
        sso_client_id="hub",
    )
    _mock_validate_id_token_jwt(
        monkeypatch,
        claims={
            "sub": "user-1",
            "email": "member@example.com",
            "exp": 9999999999,
            "iat": 1,
            "nonce": "expected-nonce",
        },
    )

    claims = sso_service.validate_id_token(org=org, id_token="token", nonce="expected-nonce")
    assert claims["sub"] == "user-1"
    assert claims["nonce"] == "expected-nonce"


def test_sso_info_public(client):
    setup_admin(client)
    _configure_public_url(client)
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    org_id = _configure_sso(client, enabled=True)
    logout(client)

    response = client.get(f"/api/v1/auth/sso/{org_id}/info")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["org_name"]
    assert payload["enabled"] is True
    assert payload["login_url"] == f"https://hub.example/sso/{org_id}"

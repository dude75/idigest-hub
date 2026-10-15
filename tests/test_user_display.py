"""Profile names and SSO name sync."""

from __future__ import annotations

from urllib.parse import urlencode

from conftest import default_tariff_id, login_ready, logout, me, setup_admin, signup

from app.services.user_display import names_from_claims, user_display_name
from app.models import User


def test_names_from_claims_given_family():
    first, last = names_from_claims({"given_name": " Ivan ", "family_name": "Petrov"})
    assert first == "Ivan"
    assert last == "Petrov"


def test_names_from_claims_full_name():
    first, last = names_from_claims({"name": "Anna Maria Schmidt"})
    assert first == "Anna"
    assert last == "Maria Schmidt"


def test_user_display_name_falls_back_to_email():
    user = User(email="a@b.co", first_name=None, last_name=None)
    assert user_display_name(user) == "a@b.co"


def test_patch_me_sets_names_and_override(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "user@example.com", "userpass12", tariff_id)
    login_ready(client, "user@example.com", "userpass12")

    patched = client.patch("/api/v1/me", json={"first_name": "Test", "last_name": "User"})
    assert patched.status_code == 200, patched.text
    body = patched.json()["user"]
    assert body["first_name"] == "Test"
    assert body["last_name"] == "User"
    assert body["display_name"] == "Test User"

    payload = me(client)
    assert payload["user"]["display_name"] == "Test User"


def test_sso_callback_applies_names_until_profile_override(client, monkeypatch):
    setup_admin(client)
    client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.example"})
    tariff_id = default_tariff_id(client)
    signup(client, "orgadmin@example.com", "orgadminpass1", tariff_id)
    login_ready(client, "orgadmin@example.com", "orgadminpass1")
    org_id = me(client)["org"]["id"]
    body = {
        "issuer": "https://keycloak.example/realms/demo",
        "client_id": "hub",
        "client_secret": "secret",
        "enabled": True,
    }
    assert client.patch("/api/v1/org/sso", json=body).status_code == 200
    logout(client)

    from app.services import sso as sso_service

    claims = {
        "sub": "kc-1",
        "email": "newbie@example.com",
        "given_name": "New",
        "family_name": "Bie",
    }
    monkeypatch.setattr("app.routers.auth.session.exchange_code", lambda **kwargs: {"id_token": "token"})
    monkeypatch.setattr("app.routers.auth.session.validate_id_token", lambda **kwargs: claims)

    state, _nonce, _challenge = sso_service.make_oauth_state(org_id)
    query = urlencode({"code": "abc", "state": state})
    response = client.get(f"/api/v1/auth/sso/{org_id}/callback?{query}", follow_redirects=False)
    assert response.status_code == 302

    payload = me(client)
    assert payload["user"]["display_name"] == "New Bie"

    client.patch("/api/v1/me", json={"first_name": "Custom", "last_name": "Name"})
    logout(client)

    claims["given_name"] = "Other"
    claims["family_name"] = "Person"
    monkeypatch.setattr("app.routers.auth.session.validate_id_token", lambda **kwargs: claims)
    state, _nonce, _challenge = sso_service.make_oauth_state(org_id)
    query = urlencode({"code": "abc", "state": state})
    client.get(f"/api/v1/auth/sso/{org_id}/callback?{query}", follow_redirects=False)

    payload = me(client)
    assert payload["user"]["display_name"] == "Custom Name"

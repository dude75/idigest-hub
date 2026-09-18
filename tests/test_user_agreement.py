"""User agreement gate for org members."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    default_tariff_id,
    err_code,
    login,
    login_ready,
    logout,
    me,
    setup_admin,
    signup,
)


def _set_agreement(client: TestClient, *, en: str = "Terms EN", ru: str = "Terms RU") -> dict:
    response = client.patch(
        "/api/v1/instance/settings",
        json={"user_agreement_text_en": en, "user_agreement_text_ru": ru},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_user_agreement_blocks_org_member_until_accepted(client: TestClient):
    setup_admin(client)
    _set_agreement(client)
    tariff_id = default_tariff_id(client)
    signup(client, "member@example.com", "memberpass1", tariff_id)
    logout(client)

    login(client, "member@example.com", "memberpass1")
    payload = me(client)
    assert payload["user_agreement_required"] is True
    assert payload["user_agreement"]["text"] == "Terms EN"

    blocked = client.get("/api/v1/audios")
    assert blocked.status_code == 403
    assert err_code(blocked) == "user_agreement_required"

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["user_agreement_required"] is False

    allowed = client.get("/api/v1/audios")
    assert allowed.status_code == 200, allowed.text


def test_instance_admin_without_org_not_blocked(client: TestClient):
    setup_admin(client)
    _set_agreement(client)
    payload = me(client)
    assert payload["user_agreement_required"] is False


def test_agreement_version_bump_requires_reacceptance(client: TestClient):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    settings = _set_agreement(client)
    assert settings["user_agreement_version"] == 1
    logout(client)

    login_ready(client, "owner@example.com", "ownerpass12")
    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    updated = client.patch("/api/v1/instance/settings", json={"user_agreement_text_en": "Terms EN v2"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["user_agreement_version"] == 2
    logout(client)

    login(client, "owner@example.com", "ownerpass12")
    assert me(client)["user_agreement_required"] is True

    accepted = client.post("/api/v1/auth/agreement/accept")
    assert accepted.status_code == 200, accepted.text
    assert me(client)["user_agreement_required"] is False


def test_agreement_locale_ru(client: TestClient):
    setup_admin(client)
    _set_agreement(client)
    tariff_id = default_tariff_id(client)
    signup(client, "ru@example.com", "rupass1234", tariff_id)
    logout(client)

    login(client, "ru@example.com", "rupass1234")
    client.patch("/api/v1/me", json={"locale": "ru"})
    payload = me(client)
    assert payload["user_agreement_required"] is True
    assert payload["user_agreement"]["text"] == "Terms RU"


def test_bearer_token_blocked_until_agreement_accepted(client: TestClient):
    setup_admin(client)
    _set_agreement(client)
    tariff_id = default_tariff_id(client)
    signup(client, "api@example.com", "apipass1234", tariff_id)
    logout(client)

    login_ready(client, "api@example.com", "apipass1234")
    assert me(client)["user_agreement_required"] is True

    token_resp = client.post("/api/v1/auth/tokens", json={"name": "cli"})
    assert token_resp.status_code == 403
    assert err_code(token_resp) == "user_agreement_required"

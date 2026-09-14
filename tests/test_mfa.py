"""TOTP 2FA for local users."""

from __future__ import annotations

import pyotp
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


def _enable_mfa(client: TestClient) -> tuple[str, list[str]]:
    start = client.post("/api/v1/auth/mfa/setup/start")
    assert start.status_code == 200, start.text
    secret = start.json()["secret"]
    code = pyotp.TOTP(secret).now()
    confirm = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": code})
    assert confirm.status_code == 200, confirm.text
    return secret, confirm.json()["recovery_codes"]


def _login_mfa(client: TestClient, email: str, password: str, *, secret: str | None = None, recovery: str | None = None):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "mfa_required"
    challenge_id = body["challenge_id"]
    if recovery:
        verify = client.post(
            "/api/v1/auth/mfa/recover",
            json={"challenge_id": challenge_id, "recovery_code": recovery},
        )
    else:
        assert secret is not None
        verify = client.post(
            "/api/v1/auth/mfa/verify",
            json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
        )
    assert verify.status_code == 200, verify.text


def test_mfa_login_and_token_step_up(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)
    logout(client)

    _login_mfa(client, ADMIN_EMAIL, ADMIN_PASSWORD, secret=secret)
    assert me(client)["mfa_enabled"] is True

    blocked = client.post("/api/v1/auth/tokens", json={"name": "cli"})
    assert blocked.status_code == 403
    assert err_code(blocked) == "mfa_step_up_required"

    created = client.post(
        "/api/v1/auth/tokens",
        json={"name": "cli", "totp_code": pyotp.TOTP(secret).now()},
    )
    assert created.status_code == 200, created.text
    raw = created.json()["token"]

    chained = client.post(
        "/api/v1/auth/tokens",
        json={"name": "chain"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert chained.status_code == 403


def test_mfa_recovery_code_login(client):
    setup_admin(client)
    secret, codes = _enable_mfa(client)
    logout(client)

    _login_mfa(client, ADMIN_EMAIL, ADMIN_PASSWORD, recovery=codes[0])
    assert me(client)["mfa_enabled"] is True

    _login_mfa(client, ADMIN_EMAIL, ADMIN_PASSWORD, secret=secret)
    bad = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    challenge_id = bad.json()["challenge_id"]
    used = client.post(
        "/api/v1/auth/mfa/recover",
        json={"challenge_id": challenge_id, "recovery_code": codes[0]},
    )
    assert used.status_code == 401


def test_org_mfa_required_enrollment(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")

    enabled = client.patch("/api/v1/org/settings", json={"mfa_required": True})
    assert enabled.status_code == 200, enabled.text
    logout(client)

    login(client, "owner@example.com", "ownerpass12")
    payload = me(client)
    assert payload["mfa_enrollment_required"] is True

    blocked = client.get("/api/v1/org/users")
    assert blocked.status_code == 403
    assert err_code(blocked) == "mfa_enrollment_required"

    secret, _ = _enable_mfa(client)
    payload = me(client)
    assert payload["mfa_enrollment_required"] is False
    assert payload["mfa_enabled"] is True

    logout(client)
    _login_mfa(client, "owner@example.com", "ownerpass12", secret=secret)


def test_org_mfa_required_blocked_when_sso_enabled(client):
    setup_admin(client)
    client.patch("/api/v1/instance/settings", json={"public_base_url": "https://hub.example"})
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")

    client.patch(
        "/api/v1/org/sso",
        json={
            "issuer": "https://kc.example/realms/hub",
            "client_id": "hub",
            "client_secret": "secret",
            "enabled": True,
        },
    )
    denied = client.patch("/api/v1/org/settings", json={"mfa_required": True})
    assert denied.status_code == 400


def test_org_admin_can_reset_member_mfa(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")
    client.patch("/api/v1/org/settings", json={"mfa_required": True})
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass12", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]
    logout(client)

    login_ready(client, "member@example.com", "memberpass12")
    _enable_mfa(client)
    logout(client)

    login(client, "owner@example.com", "ownerpass12")
    reset = client.post(f"/api/v1/org/users/{member_id}/reset-mfa")
    assert reset.status_code == 200, reset.text
    assert reset.json()["mfa_enabled"] is False
    logout(client)

    login(client, "member@example.com", "memberpass12")
    payload = me(client)
    assert payload["mfa_enabled"] is False
    assert payload["mfa_enrollment_required"] is True
    logout(client)

    stale = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "memberpass12"})
    assert stale.status_code == 200, stale.text
    assert stale.json()["status"] == "ok"


def test_mfa_disable_blocked_when_org_requires(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")
    client.patch("/api/v1/org/settings", json={"mfa_required": True})
    secret, _ = _enable_mfa(client)

    disable = client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": "ownerpass12", "code": pyotp.TOTP(secret).now()},
    )
    assert disable.status_code == 403


"""TOTP 2FA for local users."""

from __future__ import annotations

from datetime import timedelta

import pyotp
from fastapi.testclient import TestClient

from app.rate_limit import reset_rate_limiter
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
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


def _enable_mfa(client: TestClient) -> tuple[str, list[str]]:
    start = client.post("/api/v1/auth/mfa/setup/start")
    assert start.status_code == 200, start.text
    secret = start.json()["secret"]
    code = pyotp.TOTP(secret).now()
    confirm = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": code})
    assert confirm.status_code == 200, confirm.text
    return secret, confirm.json()["recovery_codes"]


def _start_mfa_login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "mfa_required"
    return body["challenge_id"]


def _login_mfa(client: TestClient, email: str, password: str, *, secret: str | None = None, recovery: str | None = None):
    challenge_id = _start_mfa_login(client, email, password)
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
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass12", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]
    login_ready(client, "member@example.com", "memberpass12")
    logout(client)
    login(client, "owner@example.com", "ownerpass12")
    client.patch("/api/v1/org/settings", json={"mfa_required": True})
    owner_secret, _ = _enable_mfa(client)
    logout(client)

    login(client, "member@example.com", "memberpass12")
    _enable_mfa(client)
    logout(client)

    _login_mfa(client, "owner@example.com", "ownerpass12", secret=owner_secret)
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


def test_mfa_disable_success_when_not_required(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)

    disable = client.post(
        "/api/v1/auth/mfa/disable",
        json={"password": ADMIN_PASSWORD, "code": pyotp.TOTP(secret).now()},
    )
    assert disable.status_code == 200, disable.text
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert me(client)["mfa_enabled"] is False


def test_mfa_status_endpoint(client):
    setup_admin(client)
    status = client.get("/api/v1/auth/mfa/status")
    assert status.status_code == 200, status.text
    payload = status.json()
    assert payload == {"enabled": False, "required": False, "enrollment_required": False}

    secret, _ = _enable_mfa(client)
    assert secret
    status = client.get("/api/v1/auth/mfa/status")
    assert status.json()["enabled"] is True


def test_mfa_enrollment_allows_password_change(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass12", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    client.patch("/api/v1/org/settings", json={"mfa_required": True})
    logout(client)

    login(client, "member@example.com", "memberpass12")
    assert me(client)["mfa_enrollment_required"] is True
    changed = client.post("/api/v1/auth/password/change", json={"new_password": "memberpass12"})
    assert changed.status_code == 200, changed.text
    _enable_mfa(client)
    assert me(client)["mfa_enrollment_required"] is False


def test_mfa_verify_invalid_totp(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)
    logout(client)

    challenge_id = _start_mfa_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    bad = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": "000000"},
    )
    assert bad.status_code == 401
    assert err_code(bad) == "invalid_totp"

    ok = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
    )
    assert ok.status_code == 200, ok.text


def test_mfa_verify_invalid_challenge(client):
    setup_admin(client)
    _enable_mfa(client)
    logout(client)

    bad = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": "not-a-real-challenge", "code": "123456"},
    )
    assert bad.status_code == 401
    assert err_code(bad) == "mfa_challenge_invalid"


def test_mfa_challenge_expired(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)
    logout(client)

    challenge_id = _start_mfa_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    db = open_db()
    try:
        from sqlalchemy import select

        from app.models import MfaChallenge
        from app.security import hash_secret
        from app.timeutil import utcnow

        row = db.scalar(select(MfaChallenge).where(MfaChallenge.token_hash == hash_secret(challenge_id)))
        assert row is not None
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    expired = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
    )
    assert expired.status_code == 401
    assert err_code(expired) == "mfa_challenge_invalid"


def test_mfa_challenge_single_use(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)
    logout(client)

    challenge_id = _start_mfa_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    first = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
    )
    assert first.status_code == 200, first.text

    reused = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()},
    )
    assert reused.status_code == 401
    assert err_code(reused) == "mfa_challenge_invalid"


def test_mfa_verify_rate_limited(client):
    setup_admin(client)
    _enable_mfa(client)
    logout(client)

    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_login_email = 2
        row.rate_limit_login_ip = 0
        row.rate_limit_login_global = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    challenge_id = _start_mfa_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/mfa/verify",
            json={"challenge_id": challenge_id, "code": "000000"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/mfa/verify",
        json={"challenge_id": challenge_id, "code": "000000"},
    )
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"


def test_mfa_setup_confirm_invalid_code(client):
    setup_admin(client)
    start = client.post("/api/v1/auth/mfa/setup/start")
    assert start.status_code == 200, start.text
    secret = start.json()["secret"]

    bad = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": "000000"})
    assert bad.status_code == 401
    assert err_code(bad) == "invalid_totp"

    ok = client.post(
        "/api/v1/auth/mfa/setup/confirm",
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert ok.status_code == 200, ok.text


def test_mfa_token_step_up_invalid_totp(client):
    setup_admin(client)
    secret, _ = _enable_mfa(client)
    logout(client)
    _login_mfa(client, ADMIN_EMAIL, ADMIN_PASSWORD, secret=secret)

    bad = client.post(
        "/api/v1/auth/tokens",
        json={"name": "cli", "totp_code": "000000"},
    )
    assert bad.status_code == 401
    assert err_code(bad) == "invalid_totp"

    created = client.post(
        "/api/v1/auth/tokens",
        json={"name": "cli", "totp_code": pyotp.TOTP(secret).now()},
    )
    assert created.status_code == 200, created.text


def test_org_reset_mfa_requires_totp_configured(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "owner@example.com", "ownerpass12", tariff_id)
    login_ready(client, "owner@example.com", "ownerpass12")
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass12", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]

    reset = client.post(f"/api/v1/org/users/{member_id}/reset-mfa")
    assert reset.status_code == 400
    assert err_code(reset) == "validation_error"


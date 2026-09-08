"""Rate limiting tests."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.rate_limit import MAX_BUCKETS, _hit, reset_rate_limiter
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, err_code, login, open_db, setup_admin


def test_login_rate_limit_by_email(client: TestClient):
    setup_admin(client)
    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_login_email = 3
        row.rate_limit_login_global = 0
        row.rate_limit_login_ip = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass1"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpass1"},
    )
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"
    assert blocked.headers.get("retry-after")


def test_rate_limit_disabled(client: TestClient):
    setup_admin(client)
    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_enabled = False
        row.rate_limit_login_email = 1
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass1"},
        )
        assert response.status_code == 401


def test_bearer_api_rate_limit(client: TestClient):
    setup_admin(client)
    token_response = client.post("/api/v1/auth/tokens", json={"name": "ci"})
    assert token_response.status_code == 200, token_response.text
    raw = token_response.json()["token"]

    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_api_user = 2
        row.rate_limit_api_global = 0
        row.rate_limit_api_ip = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    headers = {"Authorization": f"Bearer {raw}"}
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    blocked = client.get("/api/v1/me", headers=headers)
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"


def test_cookie_session_not_api_rate_limited(client: TestClient):
    setup_admin(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_api_user = 1
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    assert client.get("/api/v1/me").status_code == 200
    assert client.get("/api/v1/me").status_code == 200


def test_instance_settings_patch_rate_limits(client: TestClient):
    setup_admin(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.patch(
        "/api/v1/instance/settings",
        json={"rate_limit_login_email": 42, "rate_limit_login_ip": 0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rate_limit_login_email"] == 42
    assert payload["rate_limit_login_ip"] == 0


def test_bucket_expires():
    reset_rate_limiter()
    allowed, _ = _hit("test:key", 1, 0.05)
    assert allowed
    time.sleep(0.06)
    allowed, _ = _hit("test:key", 1, 0.05)
    assert allowed


def test_max_buckets_eviction():
    reset_rate_limiter()
    from app import rate_limit as rl

    original = rl.MAX_BUCKETS
    rl.MAX_BUCKETS = 5
    try:
        for index in range(6):
            allowed, _ = _hit(f"fill:{index}", 100, 3600.0)
            assert allowed
        assert len(rl._buckets) <= 5
    finally:
        rl.MAX_BUCKETS = original
        reset_rate_limiter()

"""Rate limiting tests."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.rate_limit import MAX_BUCKETS, _hit, reset_rate_limiter
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, err_code, login, open_db, setup_admin


def test_login_rate_limit_by_ip_with_trusted_proxy(client: TestClient, monkeypatch):
    setup_admin(client)
    monkeypatch.setenv("TRUSTED_PROXIES", "testclient")
    from app.config import get_settings
    from app.proxy import reset_trusted_proxy_cache

    get_settings.cache_clear()
    reset_trusted_proxy_cache()

    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_login_ip = 2
        row.rate_limit_login_email = 0
        row.rate_limit_login_global = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    headers = {"X-Forwarded-For": "203.0.113.50"}
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass1"},
            headers=headers,
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "wrongpass1"},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"


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


def test_cookie_session_not_bearer_api_rate_limited(client: TestClient):
    """Cookie sessions skip Bearer general limits; write limits are tested in test_abuse.py."""
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


def test_instance_settings_patch_session_ttl(client: TestClient):
    setup_admin(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    response = client.get("/api/v1/instance/settings")
    assert response.status_code == 200, response.text
    assert response.json()["session_ttl_hours"] == 24

    response = client.patch("/api/v1/instance/settings", json={"session_ttl_hours": 8})
    assert response.status_code == 200, response.text
    assert response.json()["session_ttl_hours"] == 8

    bad = client.patch("/api/v1/instance/settings", json={"session_ttl_hours": 0})
    assert bad.status_code == 400
    assert err_code(bad) == "validation_error"


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

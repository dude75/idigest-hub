"""Security hardening: secrets, OpenAPI, CSRF, upload magic bytes."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import reset_engine
from app.main import create_app
from app.services.secrets_bootstrap import SecretsConfigError, validate_secrets_config
from tests.conftest import (
    SAMPLE_MP3_BYTES,
    SAMPLE_WAV_BYTES,
    err_code,
    open_db,
    setup_admin,
    signup,
)


def test_setup_rejects_empty_session_secret(client, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "")
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/setup",
        json={"email": "admin@example.com", "password": "adminpass1", "bootstrap_token": "boot"},
    )
    assert response.status_code == 503
    assert err_code(response) == "secrets_misconfigured"


def test_validate_secrets_config_after_bootstrap(client, monkeypatch):
    setup_admin(client)
    db = open_db()
    try:
        monkeypatch.setenv("SESSION_SECRET", "")
        get_settings.cache_clear()
        with pytest.raises(SecretsConfigError):
            validate_secrets_config(db)
    finally:
        db.close()


def test_openapi_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("INSTANCE_BOOTSTRAP_TOKEN", "boot")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("OPENAPI_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hub.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("DISPATCH_POLL_SEC", "3600")
    get_settings.cache_clear()
    reset_engine()
    from app.rate_limit import reset_rate_limiter
    from app.services.storage import reset_storage

    reset_storage()
    reset_rate_limiter()
    application = create_app()
    with TestClient(application) as test_client:
        assert test_client.get("/docs").status_code == 404
        assert test_client.get("/openapi.json").status_code == 404
        assert test_client.get("/api/v1/health").status_code == 200


def test_csrf_blocks_cookie_mutation_without_header(client):
    setup_admin(client)
    response = client._csrf_original_post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert err_code(response) == "csrf_invalid"


def test_csrf_blocks_wrong_token(client):
    setup_admin(client)
    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "bad-token"})
    assert response.status_code == 403
    assert err_code(response) == "csrf_invalid"


def test_csrf_not_required_for_bearer_api(client):
    setup_admin(client)
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    client.post("/api/v1/auth/logout")
    assert signup(client, "api@example.com", "apipass12", tariff_id).status_code == 200
    token_resp = client.post("/api/v1/auth/tokens", json={"name": "integration"})
    assert token_resp.status_code == 200, token_resp.text
    raw_token = token_resp.json()["token"]

    response = client.post(
        "/api/v1/audios",
        headers={"Authorization": f"Bearer {raw_token}", "X-CSRF-Token": "wrong"},
        files={"file": ("clip.wav", BytesIO(SAMPLE_WAV_BYTES), "audio/wav")},
    )
    assert response.status_code == 200, response.text


def test_upload_rejects_wrong_magic_bytes(client):
    setup_admin(client)
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    client.post("/api/v1/auth/logout")
    assert signup(client, "magic@example.com", "magicpass1", tariff_id).status_code == 200

    response = client.post(
        "/api/v1/audios",
        files={"file": ("fake.mp3", BytesIO(b"MZ" + b"\x00" * 64), "audio/mpeg")},
    )
    assert response.status_code == 400
    assert err_code(response) == "invalid_file"


def test_auth_cookies_include_csrf(client):
    setup_admin(client)
    assert client.cookies.get("hub_session")
    assert client.cookies.get("hub_csrf")


def test_csrf_exempt_login(client):
    setup_admin(client)
    client.post("/api/v1/auth/logout")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpass1"},
    )
    assert response.status_code == 200, response.text
    assert client.cookies.get("hub_csrf")


def test_csrf_backfilled_for_legacy_session(client):
    setup_admin(client)
    client.cookies.pop("hub_csrf", None)
    assert client.cookies.get("hub_session")
    assert client.cookies.get("hub_csrf") is None

    me = client.get("/api/v1/me")
    assert me.status_code == 200, me.text
    assert client.cookies.get("hub_csrf")

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200, response.text

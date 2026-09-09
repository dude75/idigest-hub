"""Abuse-resistance: cross-org isolation, privilege boundaries, write rate limits."""

from __future__ import annotations

from io import BytesIO

from app.rate_limit import reset_rate_limiter

from tests.conftest import (
    default_tariff_id,
    err_code,
    login,
    logout,
    open_db,
    setup_admin,
    signup,
    upload_audio,
)


def _set_write_limits(*, upload_user: int = 2, tasks_user: int = 2) -> None:
    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_enabled = True
        row.rate_limit_api_tasks_user = upload_user
        row.rate_limit_api_tasks_ip = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()


def test_cross_org_audio_isolation(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)

    assert signup(client, "alice@example.com", "alicepass1", tariff_id).status_code == 200
    uploaded = upload_audio(client)
    assert uploaded.status_code == 200, uploaded.text
    audio_id = uploaded.json()["id"]
    logout(client)

    assert signup(client, "bob@example.com", "bobpass1", tariff_id).status_code == 200
    assert client.get(f"/api/v1/audios/{audio_id}").status_code == 404
    assert client.get(f"/api/v1/audios/{audio_id}/file").status_code == 404
    assert client.post("/api/v1/tasks/transcribe", json={"audio_id": audio_id}).status_code == 404
    assert client.delete(f"/api/v1/audios/{audio_id}").status_code == 404


def test_org_user_cannot_reach_instance_admin_apis(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "outsider@example.com", "outsiderp1", tariff_id).status_code == 200

    for path in (
        "/api/v1/workers",
        "/api/v1/orgs",
        "/api/v1/instance/settings",
        "/api/v1/instance/stats",
    ):
        response = client.get(path)
        assert response.status_code == 403, path
        assert err_code(response) == "forbidden"


def test_setup_replay_rejected(client):
    setup_admin(client)
    response = client.post(
        "/api/v1/setup",
        json={"email": "hacker@evil.com", "password": "hackpass1", "bootstrap_token": "wrong"},
    )
    assert response.status_code == 409
    assert err_code(response) == "setup_already_done"


def test_invalid_upload_extension_rejected(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "uploader@example.com", "uploadpass1", tariff_id).status_code == 200

    response = client.post(
        "/api/v1/audios",
        files={"file": ("malware.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert err_code(response) == "invalid_file"


def test_cookie_upload_rate_limited(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "flooder@example.com", "floodpass1", tariff_id).status_code == 200
    _set_write_limits(upload_user=2)

    payload = b"RIFF" + b"\x00" * 64
    for index in range(2):
        response = upload_audio(client, name=f"clip{index}.wav", data=payload)
        assert response.status_code == 200, response.text

    blocked = upload_audio(client, name="clip3.wav", data=payload)
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"
    assert blocked.headers.get("retry-after")


def test_cookie_task_create_rate_limited(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "tasker@example.com", "taskpass12", tariff_id).status_code == 200
    _set_write_limits(tasks_user=2)

    for _ in range(2):
        response = client.post("/api/v1/tasks/transcribe", json={"audio_id": "00000000-0000-0000-0000-000000000001"})
        assert response.status_code == 404

    blocked = client.post(
        "/api/v1/tasks/transcribe",
        json={"audio_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert blocked.status_code == 429
    assert err_code(blocked) == "rate_limited"


def test_cookie_session_reads_not_write_rate_limited(client):
    """GET /me stays unlimited; only upload/task POSTs are throttled."""
    setup_admin(client)
    login(client, "admin@example.com", "adminpass1")
    _set_write_limits(upload_user=1)

    assert client.get("/api/v1/me").status_code == 200
    assert client.get("/api/v1/me").status_code == 200

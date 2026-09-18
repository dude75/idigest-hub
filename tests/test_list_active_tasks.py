"""Regression: all queued/running tasks appear in GET /tasks active section."""

from __future__ import annotations

from tests.conftest import (
    default_tariff_id,
    login_ready,
    logout,
    open_db,
    setup_admin,
    signup,
)
from app.models import Task, new_id
from app.timeutil import utcnow


def _allow_import_url(url: str, *, settings_allowed):
    return url.strip()


def test_list_shows_all_active_import_tasks(client, monkeypatch):
    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)
    monkeypatch.setattr("app.services.import_runner.import_slots_available", lambda: False)

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "listact@example.com", "listactpass1", tariff_id).status_code == 200
    login_ready(client, "listact@example.com", "listactpass1")

    created_ids: list[str] = []
    for i in range(5):
        response = client.post(
            "/api/v1/tasks/import",
            json={"url": f"https://www.youtube.com/watch?v=dQw4w9WgXcQ{i}"},
        )
        assert response.status_code == 202, response.text
        created_ids.append(response.json()["task_id"])

    listed = client.get("/api/v1/tasks")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    active_ids = {item["task_id"] for item in payload["active"]}
    assert set(created_ids).issubset(active_ids)
    assert len(payload["active"]) >= len(created_ids)


def test_list_active_import_tasks_with_many_done(client, monkeypatch):
    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)
    monkeypatch.setattr("app.services.import_runner.import_slots_available", lambda: False)

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "manydone@example.com", "manydonepass1", tariff_id).status_code == 200
    login_ready(client, "manydone@example.com", "manydonepass1")

    me = client.get("/api/v1/me").json()
    org_id = me["org"]["id"]
    user_id = me["user"]["id"]
    now = utcnow()
    db = open_db()
    try:
        for _ in range(200):
            db.add(
                Task(
                    id=new_id(),
                    type="transcribe",
                    status="success",
                    org_id=org_id,
                    user_id=user_id,
                    queued_at=now,
                    created_at=now,
                    updated_at=now,
                    snap_unlimited=True,
                    snap_price_per_audio_sec=0,
                    snap_price_per_summarize_job=0,
                    snap_price_per_1k_summary_chars=0,
                    snap_max_upload_bytes=1,
                )
            )
        db.commit()
    finally:
        db.close()

    created_ids: list[str] = []
    for i in range(5):
        response = client.post(
            "/api/v1/tasks/import",
            json={"url": f"https://www.youtube.com/watch?v=done{i}"},
        )
        assert response.status_code == 202, response.text
        created_ids.append(response.json()["task_id"])

    listed = client.get("/api/v1/tasks?done_limit=10&done_offset=0")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    active_ids = {item["task_id"] for item in payload["active"]}
    assert set(created_ids).issubset(active_ids)
    assert len(payload["active"]) >= len(created_ids)
    assert payload["done_total"] == 200
    assert len(payload["done"]) == 10


def test_list_tasks_schedules_full_tick_when_active(client, monkeypatch, spy_locked_tick_job):
    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)
    monkeypatch.setattr("app.services.import_runner.import_slots_available", lambda: False)

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "listtick@example.com", "listtickpass1", tariff_id).status_code == 200
    login_ready(client, "listtick@example.com", "listtickpass1")

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=listtick1"},
    )
    assert created.status_code == 202, created.text
    spy_locked_tick_job.clear()

    listed = client.get("/api/v1/tasks")
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["active"]) == 1
    assert any(call["task_id"] is None and call["refresh_health"] is False for call in spy_locked_tick_job)

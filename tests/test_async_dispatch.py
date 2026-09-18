"""Regression tests for non-blocking task create/poll dispatch."""

from __future__ import annotations

import pytest

from tests.conftest import (
    add_worker,
    default_tariff_id,
    get_task_row,
    login_ready,
    logout,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
    wait_task,
)


def _org_user_with_audio(client, fake_workers=None, *, seed=True):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client)
    if seed:
        seed_node_health(worker["id"])
    logout(client)
    assert signup(client, "async@example.com", "asyncpass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    return {"audio": audio.json(), "tariff_id": tariff_id, "worker": worker}


def test_create_transcribe_returns_202_without_worker_assignment(client, fake_workers):
    """POST returns queued immediately; worker dispatch runs in BackgroundTasks."""
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queue_full"

    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["status"] == "queued"
    row = get_task_row(body["task_id"])
    assert row.meta_json.get("stage") == "queue_full"


def _allow_import_url(url: str, *, settings_allowed):
    return url.strip()


def test_create_import_returns_queued_import_task(client, monkeypatch):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "importfast@example.com", "importfastpass1", tariff_id).status_code == 200
    login_ready(client, "importfast@example.com", "importfastpass1")
    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)
    monkeypatch.setattr("app.services.import_runner.import_slots_available", lambda: False)

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["type"] == "import"
    assert body["status"] == "queued"
    assert body["meta"].get("stage") == "queued"


def test_get_task_schedules_locked_tick_job_for_queued_transcribe(
    client, fake_workers, spy_locked_tick_job
):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queue_full"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    task_id = created.json()["task_id"]
    spy_locked_tick_job.clear()

    polled = client.get(f"/api/v1/tasks/{task_id}")
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "queued"
    assert any(
        call["task_id"] == task_id and call["refresh_health"] is True for call in spy_locked_tick_job
    )


def test_get_import_task_schedules_tick_without_worker_health(client, monkeypatch, spy_locked_tick_job):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "importpoll@example.com", "importpollpass1", tariff_id).status_code == 200
    login_ready(client, "importpoll@example.com", "importpollpass1")
    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)
    monkeypatch.setattr("app.services.import_runner.import_slots_available", lambda: False)

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    spy_locked_tick_job.clear()

    polled = client.get(f"/api/v1/tasks/{task_id}")
    assert polled.status_code == 200, polled.text
    assert polled.json()["type"] == "import"
    assert any(
        call["task_id"] == task_id and call["refresh_health"] is False for call in spy_locked_tick_job
    )


def test_get_task_poll_eventually_dispatches_transcribe(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "success"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    task_id = created.json()["task_id"]

    finished = wait_task(client, task_id, status="success")
    assert finished["transcript_id"]

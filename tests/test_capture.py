"""Meeting capture tasks and org Jitsi host maps."""

from __future__ import annotations

import pytest

from tests.conftest import (
    add_worker,
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    seed_node_health,
    setup_admin,
    signup,
    wait_task,
)


@pytest.fixture(autouse=True)
def _reset_capture_runner():
    from app.services.capture_runner import reset_capture_runner

    reset_capture_runner()
    yield
    reset_capture_runner()


def _enable_capture(client) -> None:
    response = client.patch("/api/v1/instance/settings", json={"capture_enabled": True})
    assert response.status_code == 200, response.text


def _map_jitsi_host(client, worker_id: str, host: str = "meet.example.com") -> None:
    response = client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": host, "worker_id": worker_id}]},
    )
    assert response.status_code == 200, response.text


def test_normalize_host_accepts_meeting_url():
    from app.services.capture_meeting import normalize_host

    assert normalize_host("https://meet.realweb.ru/") == "meet.realweb.ru"
    assert normalize_host("meet.realweb.ru/MyRoom") == "meet.realweb.ru"
    assert normalize_host("www.meet.example.com") == "meet.example.com"


def test_capture_platforms(client):
    setup_admin(client)
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capplat@example.com", "capplatpass1", tariff_id).status_code == 200
    login_ready(client, "capplat@example.com", "capplatpass1")
    response = client.get("/api/v1/capture/platforms")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert any(item["id"] == "jitsi" for item in body["connectors"])
    assert body["jitsi_hosts"] == []


def test_capture_disabled(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capoff@example.com", "capoffpass1", tariff_id).status_code == 200
    login_ready(client, "capoff@example.com", "capoffpass1")
    response = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.example.com/room1"},
    )
    assert response.status_code == 403
    assert err_code(response) == "capture_disabled"


def test_capture_meeting_host_not_configured(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capnohost@example.com", "capnohostpass1", tariff_id).status_code == 200
    login_ready(client, "capnohost@example.com", "capnohostpass1")
    response = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.example.com/room1"},
    )
    assert response.status_code == 400
    assert err_code(response) == "meeting_host_not_configured"


def test_capture_uses_org_bot_display_name(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capbot@example.com", "capbotpass1", tariff_id).status_code == 200
    login_ready(client, "capbot@example.com", "capbotpass1")
    mapped = client.put(
        "/api/v1/org/capture/jitsi",
        json={
            "bot_display_name": "Realweb Recorder",
            "items": [{"host": "meet.example.com", "worker_id": worker["id"]}],
        },
    )
    assert mapped.status_code == 200, mapped.text

    created = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.example.com/room1"},
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    wait_task(client, task_id, status={"success"})
    assert fake_workers.last_capture_display_name == "Realweb Recorder"


def test_capture_success(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capsuccess@example.com", "capsuccesspass1", tariff_id).status_code == 200
    login_ready(client, "capsuccess@example.com", "capsuccesspass1")
    _map_jitsi_host(client, worker["id"])

    created = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.example.com/room1", "pin": "1234"},
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]

    body = wait_task(client, task_id, status={"success"})
    assert body["audio_id"]
    audio = client.get(f"/api/v1/audios/{body['audio_id']}")
    assert audio.status_code == 200
    payload = audio.json()
    assert payload["source_url"] == "https://meet.example.com/room1"
    assert payload["filename"].endswith(".mp3")


def test_org_capture_jitsi_crud(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caporg@example.com", "caporgpass1", tariff_id).status_code == 200
    login_ready(client, "caporg@example.com", "caporgpass1")

    listed = client.get("/api/v1/org/capture/jitsi")
    assert listed.status_code == 200
    body = listed.json()
    assert body["allowed"] is True
    assert body["items"] == []
    assert len(body["workers"]) == 1
    assert body["workers"][0]["id"] == worker["id"]

    _map_jitsi_host(client, worker["id"], host="jitsi.example.com")
    listed = client.get("/api/v1/org/capture/jitsi")
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["host"] == "jitsi.example.com"

    logout(client)
    login_ready(client, "caporg@example.com", "caporgpass1")
    cleared = client.put("/api/v1/org/capture/jitsi", json={"items": []})
    assert cleared.status_code == 200
    assert cleared.json()["items"] == []


def test_org_capture_jitsi_rejects_invalid_worker(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capbad@example.com", "capbadpass1", tariff_id).status_code == 200
    login_ready(client, "capbad@example.com", "capbadpass1")
    response = client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": "https://meet.realweb.ru/", "worker_id": "not-a-worker"}]},
    )
    assert response.status_code == 400
    assert err_code(response) == "invalid_capture_worker"


def test_import_meeting_url_creates_capture_via_import_endpoint(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capmeet@example.com", "capmeetpass1", tariff_id).status_code == 200
    login_ready(client, "capmeet@example.com", "capmeetpass1")
    _map_jitsi_host(client, worker["id"], host="meet.realweb.ru")
    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://meet.realweb.ru/some-room"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["type"] == "capture"


def test_import_meeting_url_without_capture_enabled(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capoff2@example.com", "capoff2pass1", tariff_id).status_code == 200
    login_ready(client, "capoff2@example.com", "capoff2pass1")
    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://meet.realweb.ru/some-room"},
    )
    assert response.status_code == 403
    assert err_code(response) == "capture_disabled"

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


def test_capture_storage_filename_uses_meeting_room():
    from app.services.capture_meeting import capture_storage_filename

    assert capture_storage_filename({"meeting_room": "Weekly Standup"}, ".mp3") == "Weekly Standup.mp3"
    assert (
        capture_storage_filename({"meeting_url": "https://meet.example.com/My%20Room"}, ".mp3")
        == "My Room.mp3"
    )


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
    assert payload["filename"] == "room1.mp3"


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

    host_id = listed.json()["items"][0]["id"]
    with_app_id = client.put(
        "/api/v1/org/capture/jitsi",
        json={
            "items": [
                {
                    "id": host_id,
                    "host": "jitsi.example.com",
                    "worker_id": worker["id"],
                    "jwt_app_id": "miSpy",
                }
            ]
        },
    )
    assert with_app_id.status_code == 200, with_app_id.text
    assert with_app_id.json()["items"][0]["jwt_app_id"] == "miSpy"

    cleared_app_id = client.put(
        "/api/v1/org/capture/jitsi",
        json={
            "items": [
                {
                    "id": host_id,
                    "host": "jitsi.example.com",
                    "worker_id": worker["id"],
                    "jwt_app_id": "",
                }
            ]
        },
    )
    assert cleared_app_id.status_code == 200, cleared_app_id.text
    assert cleared_app_id.json()["items"][0]["jwt_app_id"] is None

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


@pytest.mark.asyncio
async def test_recover_capture_without_worker_task_requeues(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caprec1@example.com", "caprec1pass1", tariff_id).status_code == 200
    user = login_ready(client, "caprec1@example.com", "caprec1pass1")
    _map_jitsi_host(client, worker["id"])

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.dispatcher import recover_orphaned_tasks
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        assert org is not None
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={"meeting_url": "https://meet.example.com/room1", "stage": "queued"},
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        await recover_orphaned_tasks(db)
        db.expire_all()
        recovered = db.get(Task, task.id)
        assert recovered is not None
        assert recovered.status == "queued"
        assert recovered.worker_id is None
        assert recovered.worker_task_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recover_capture_worker_still_running_keeps_worker_task(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caprec2@example.com", "caprec2pass1", tariff_id).status_code == 200
    user = login_ready(client, "caprec2@example.com", "caprec2pass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.dispatcher import recover_orphaned_tasks
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        assert org is not None
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            worker_task_id=fake_workers.capture_worker_task_id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "meeting_url": "https://meet.example.com/room1",
                "stage": "capturing",
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        fake_workers.capture_poll_mode = "capturing"
        await recover_orphaned_tasks(db)
        db.expire_all()
        recovered = db.get(Task, task.id)
        assert recovered is not None
        assert recovered.status == "running"
        assert recovered.worker_id == worker["id"]
        assert recovered.worker_task_id == fake_workers.capture_worker_task_id
        assert recovered.meta_json["stage"] == "capturing"
    finally:
        db.close()
        fake_workers.capture_poll_mode = "success"


@pytest.mark.asyncio
async def test_capture_stop_calls_worker_without_local_thread(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capstop@example.com", "capstoppass1", tariff_id).status_code == 200
    user = login_ready(client, "capstop@example.com", "capstoppass1")
    _map_jitsi_host(client, worker["id"])

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        assert org is not None
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            worker_task_id=fake_workers.capture_worker_task_id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "meeting_url": "https://meet.example.com/room1",
                "stage": "capturing",
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()
        hub_task_id = task.id
    finally:
        db.close()

    from app.services.capture_runner import reset_capture_runner

    reset_capture_runner()
    fake_workers.capture_stop_calls.clear()

    response = client.post(f"/api/v1/tasks/{hub_task_id}/stop")
    assert response.status_code == 202, response.text
    assert fake_workers.capture_worker_task_id in fake_workers.capture_stop_calls
    body = response.json()
    assert body["meta"]["stop_requested"] is True


@pytest.mark.asyncio
async def test_recover_capture_honors_stop_requested(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caprec3@example.com", "caprec3pass1", tariff_id).status_code == 200
    user = login_ready(client, "caprec3@example.com", "caprec3pass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.dispatcher import recover_orphaned_tasks
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            worker_task_id=fake_workers.capture_worker_task_id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "meeting_url": "https://meet.example.com/room1",
                "stage": "capturing",
                "stop_requested": True,
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        fake_workers.capture_stop_calls.clear()
        fake_workers.capture_poll_mode = "capturing"
        await recover_orphaned_tasks(db)
        assert fake_workers.capture_worker_task_id in fake_workers.capture_stop_calls
        db.expire_all()
        recovered = db.get(Task, task.id)
        assert recovered is not None
        assert recovered.meta_json["stage"] == "finalizing"
    finally:
        db.close()
        fake_workers.capture_poll_mode = "success"


@pytest.mark.asyncio
async def test_recover_capture_dispatched_without_worker_id_fails(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caplost@example.com", "caplostpass1", tariff_id).status_code == 200
    user = login_ready(client, "caplost@example.com", "caplostpass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.dispatcher import recover_orphaned_tasks
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={"meeting_url": "https://meet.example.com/room1", "stage": "capturing"},
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        await recover_orphaned_tasks(db)
        db.expire_all()
        recovered = db.get(Task, task.id)
        assert recovered is not None
        assert recovered.status == "error"
        assert recovered.error_code == "pipeline_error"
    finally:
        db.close()


def test_maybe_start_capture_resumes_running_task(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "caprun@example.com", "caprunpass1", tariff_id).status_code == 200
    user = login_ready(client, "caprun@example.com", "caprunpass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.capture_runner import _bg_threads, maybe_start_capture, reset_capture_runner
        from app.timeutil import utcnow

        reset_capture_runner()
        org = db.get(Organization, user["org"]["id"])
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            worker_task_id=fake_workers.capture_worker_task_id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "meeting_url": "https://meet.example.com/room1",
                "stage": "finalizing",
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        maybe_start_capture(db, task)
        assert task.id in _bg_threads
    finally:
        db.close()
        reset_capture_runner()


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

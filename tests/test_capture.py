"""Meeting capture tasks and org Jitsi host maps."""

from __future__ import annotations

import pytest

from tests.conftest import (
    add_worker,
    default_tariff_id,
    err_code,
    get_task_row,
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


def _map_jitsi_host(client, host: str = "meet.example.com") -> None:
    response = client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": host}]},
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


def test_instance_settings_lists_worker_connectors(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(
        worker["id"],
        {
            "status": "ok",
            "version": "x",
            "connectors": {
                "jitsi": {"status": "loaded", "label": "Jitsi Meet"},
                "telemost": {"status": "loaded", "label": "Yandex Telemost"},
                "zoom": {"status": "unavailable", "label": "Zoom", "reason": "disabled"},
            },
            "workers": {"max": 4, "active": 0, "available": 4},
        },
    )
    response = client.get("/api/v1/instance/settings")
    assert response.status_code == 200, response.text
    connectors = response.json()["capture_connectors"]
    ids = {item["id"] for item in connectors}
    assert ids == {"jitsi", "telemost", "zoom"}
    telemost = next(item for item in connectors if item["id"] == "telemost")
    assert telemost["label"] == "Yandex Telemost"
    assert telemost["enabled"] is False

    patched = client.patch(
        "/api/v1/instance/settings",
        json={"capture_allowed_connectors": ["jitsi", "telemost"]},
    )
    assert patched.status_code == 200, patched.text
    enabled = {item["id"] for item in patched.json()["capture_connectors"] if item["enabled"]}
    assert enabled == {"jitsi", "telemost"}


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


def test_org_capture_jitsi_allowed_follows_capture_enabled(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capallow@example.com", "capallowpass1", tariff_id).status_code == 200
    login_ready(client, "capallow@example.com", "capallowpass1")

    enabled = client.get("/api/v1/org/capture/jitsi")
    assert enabled.status_code == 200
    assert enabled.json()["allowed"] is True

    login_ready(client, "admin@example.com", "adminpass1")
    off = client.patch("/api/v1/instance/settings", json={"capture_enabled": False})
    assert off.status_code == 200, off.text

    login_ready(client, "capallow@example.com", "capallowpass1")
    disabled = client.get("/api/v1/org/capture/jitsi")
    assert disabled.status_code == 200
    assert disabled.json()["allowed"] is False


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


def test_meet_jitsi_public_url_parsing():
    from app.services.capture_meeting import parse_meeting_room

    host, room = parse_meeting_room("https://meet.jit.si/IncorrectToysSpellAbove")
    assert host == "meet.jit.si"
    assert room == "IncorrectToysSpellAbove"


def test_meet_jitsi_skips_org_jwt(client, fake_workers):
    from tests.conftest import me, open_db

    from app.models import Organization
    from app.services.capture_meeting import resolve_capture_target

    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "jwtskip@example.com", "jwtskippass1", tariff_id).status_code == 200
    login_ready(client, "jwtskip@example.com", "jwtskippass1")
    put = client.put(
        "/api/v1/org/capture/jitsi",
        json={
            "items": [
                {
                    "host": "meet.jit.si",
                    "jwt_secret": "test-secret",
                    "jwt_app_id": "chat",
                }
            ]
        },
    )
    assert put.status_code == 200, put.text

    org_id = me(client)["org"]["id"]
    db = open_db()
    try:
        org = db.get(Organization, org_id)
        assert org is not None

        target = resolve_capture_target(
            db,
            org=org,
            meeting_url="https://meet.jit.si/IncorrectToysSpellAbove",
            pin="",
            settings_allowed=["jitsi"],
        )
        assert target.jwt is None
    finally:
        db.close()


def test_capture_meet_jitsi_requires_org_host_map(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "jitorg@example.com", "jitorgpass1", tariff_id).status_code == 200
    login_ready(client, "jitorg@example.com", "jitorgpass1")
    _map_jitsi_host(client, host="meet.jit.si")
    response = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.jit.si/IncorrectToysSpellAbove"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["meta"]["meeting_host"] == "meet.jit.si"
    assert body["meta"]["meeting_room"] == "IncorrectToysSpellAbove"


def test_bind_capture_worker_after_worker_id_cleared(client, fake_workers):
    from tests.conftest import open_db

    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap2", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "rebind@example.com", "rebindpass1", tariff_id).status_code == 200
    login_ready(client, "rebind@example.com", "rebindpass1")
    _map_jitsi_host(client, host="meet.jit.si")
    created = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.jit.si/RoomName"},
    )
    assert created.status_code == 202
    task_id = created.json()["task_id"]

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Task
        from app.services.capture_runner import _bind_capture_worker

        task = db.get(Task, task_id)
        assert task is not None
        task.worker_id = None
        db.commit()
        node = _bind_capture_worker(db, task, get_instance_settings(db))
        assert node is not None
        assert node.id == worker["id"]
        assert task.meta_json["meeting_host"] == "meet.jit.si"
    finally:
        db.close()


def test_resolve_jitsi_picks_any_jitsi_capture_worker(client, fake_workers):
    from tests.conftest import open_db

    from app.models import Organization
    from app.services.capture_meeting import resolve_capture_target

    setup_admin(client)
    worker_a = add_worker(client, type="capture", name="cap-a", base_url="http://capture-a.test")
    worker_b = add_worker(client, type="capture", name="cap-b", base_url="http://capture-b.test")
    seed_node_health(worker_a["id"])
    seed_node_health(worker_b["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "jitsipool@example.com", "jitsipoolpass1", tariff_id).status_code == 200
    user = login_ready(client, "jitsipool@example.com", "jitsipoolpass1")
    _map_jitsi_host(client, host="meet.example.com")
    db = open_db()
    try:
        org = db.get(Organization, user["org"]["id"])
        assert org is not None
        target = resolve_capture_target(
            db,
            org=org,
            meeting_url="https://meet.example.com/room-pool",
            pin="",
            settings_allowed=["jitsi"],
        )
        assert target.worker.id in {worker_a["id"], worker_b["id"]}
    finally:
        db.close()


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


def test_resolve_capture_bot_display_name_precedence():
    from app.models import Organization, User
    from app.services.capture_meeting import (
        DEFAULT_CAPTURE_BOT_DISPLAY_NAME,
        resolve_capture_bot_display_name,
    )

    org = Organization(capture_bot_display_name="Org Bot")
    user = User(capture_bot_display_name="User Bot")
    assert resolve_capture_bot_display_name(user=user, org=org) == "User Bot"
    assert resolve_capture_bot_display_name(user=user, org=org, override="Once") == "Once"
    user.capture_bot_display_name = None
    assert resolve_capture_bot_display_name(user=user, org=org) == "Org Bot"
    org.capture_bot_display_name = None
    assert resolve_capture_bot_display_name(user=user, org=org) == DEFAULT_CAPTURE_BOT_DISPLAY_NAME


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
            "items": [{"host": "meet.example.com"}],
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


def test_capture_user_bot_display_name_overrides_org(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capuserbot@example.com", "capuserbotpass1", tariff_id).status_code == 200
    login_ready(client, "capuserbot@example.com", "capuserbotpass1")
    mapped = client.put(
        "/api/v1/org/capture/jitsi",
        json={
            "bot_display_name": "Org Default Bot",
            "items": [{"host": "meet.example.com"}],
        },
    )
    assert mapped.status_code == 200, mapped.text
    patched = client.patch("/api/v1/me", json={"capture_bot_display_name": "Personal Bot"})
    assert patched.status_code == 200, patched.text
    prefs = patched.json()["capture_prefs"]
    assert prefs["bot_display_name"] == "Personal Bot"
    assert prefs["source"] == "user"
    assert prefs["capture_enabled"] is True

    created = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://meet.example.com/room1"},
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    wait_task(client, task_id, status={"success"})
    assert fake_workers.last_capture_display_name == "Personal Bot"


def test_capture_request_bot_display_name_override(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capreqbot@example.com", "capreqbotpass1", tariff_id).status_code == 200
    login_ready(client, "capreqbot@example.com", "capreqbotpass1")
    _map_jitsi_host(client)
    client.patch("/api/v1/me", json={"capture_bot_display_name": "Profile Bot"})

    created = client.post(
        "/api/v1/tasks/capture",
        json={
            "meeting_url": "https://meet.example.com/room1",
            "bot_display_name": "One-off Bot",
        },
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    wait_task(client, task_id, status={"success"})
    assert fake_workers.last_capture_display_name == "One-off Bot"


def test_parse_telemost_meeting_url():
    from app.services.capture_meeting import parse_telemost_meeting

    host, meeting_id = parse_telemost_meeting("https://telemost.yandex.ru/j/50")
    assert host == "telemost.yandex.ru"
    assert meeting_id == "50"


def test_capture_telemost_success(client, fake_workers):
    setup_admin(client)
    fake_workers.health = {
        "status": "ok",
        "version": "x",
        "connectors": {
            "jitsi": {"status": "loaded", "label": "Jitsi Meet"},
            "telemost": {"status": "loaded", "label": "Yandex Telemost"},
        },
        "workers": {"max": 4, "active": 0, "available": 4},
    }
    worker = add_worker(
        client,
        type="capture",
        name="cap",
        base_url="http://capture.test",
        capture_connectors=["jitsi", "telemost"],
    )
    seed_node_health(worker["id"], dict(fake_workers.health))
    client.patch(
        "/api/v1/instance/settings",
        json={"capture_enabled": True, "capture_allowed_connectors": ["jitsi", "telemost"]},
    )
    tariff_id = default_tariff_id(client)
    assert signup(client, "captele@example.com", "captelepass1", tariff_id).status_code == 200
    login_ready(client, "captele@example.com", "captelepass1")

    created = client.post(
        "/api/v1/tasks/capture",
        json={"meeting_url": "https://telemost.yandex.ru/j/50"},
    )
    assert created.status_code == 202, created.text
    body = created.json()
    task_id = body["task_id"]
    wait_task(client, task_id, status={"success"})
    row = get_task_row(task_id)
    assert row is not None
    meta = row.meta_json or {}
    assert meta.get("connector") == "telemost"
    assert meta.get("meeting_url") == "https://telemost.yandex.ru/j/50"
    assert meta.get("pin") in ("", None)


def test_capture_success(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capsuccess@example.com", "capsuccesspass1", tariff_id).status_code == 200
    login_ready(client, "capsuccess@example.com", "capsuccesspass1")
    _map_jitsi_host(client)

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

    _map_jitsi_host(client, host="jitsi.example.com")
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


def test_org_capture_jitsi_rejects_empty_host(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capbad@example.com", "capbadpass1", tariff_id).status_code == 200
    login_ready(client, "capbad@example.com", "capbadpass1")
    response = client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": "   "}]},
    )
    assert response.status_code == 400
    assert err_code(response) == "validation_error"


def test_import_meeting_url_creates_capture_via_import_endpoint(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capmeet@example.com", "capmeetpass1", tariff_id).status_code == 200
    login_ready(client, "capmeet@example.com", "capmeetpass1")
    _map_jitsi_host(client, host="meet.realweb.ru")
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
    _map_jitsi_host(client)

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
    _map_jitsi_host(client)

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


def test_capture_salvages_audio_when_worker_reports_canceled_with_artifact(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capsalv@example.com", "capsalvpass1", tariff_id).status_code == 200
    user = login_ready(client, "capsalv@example.com", "capsalvpass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.services.capture_runner import maybe_start_capture, reset_capture_runner
        from app.timeutil import utcnow

        reset_capture_runner()
        fake_workers.capture_delete_calls.clear()
        fake_workers.capture_poll_mode = "canceled_artifact"
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
                "stop_requested": True,
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()
        hub_task_id = task.id
        maybe_start_capture(db, task)
        db.commit()
    finally:
        db.close()

    body = wait_task(client, hub_task_id, status={"success"})
    assert body["audio_id"]
    assert fake_workers.capture_worker_task_id in fake_workers.capture_delete_calls
    fake_workers.capture_poll_mode = "success"


def test_retry_capture_forbidden(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    _enable_capture(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "capretry@example.com", "capretrypass1", tariff_id).status_code == 200
    user = login_ready(client, "capretry@example.com", "capretrypass1")

    from tests.conftest import open_db

    db = open_db()
    try:
        from app.deps import get_instance_settings
        from app.models import Organization, Task, new_id
        from app.services.billing import snapshot_fields
        from app.timeutil import utcnow

        org = db.get(Organization, user["org"]["id"])
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="error",
            error_code="canceled",
            org_id=org.id,
            user_id=user["user"]["id"],
            worker_id=worker["id"],
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={"meeting_url": "https://meet.example.com/room1", "stage": "done"},
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()
        hub_task_id = task.id
    finally:
        db.close()

    blocked = client.post(f"/api/v1/tasks/{hub_task_id}/retry")
    assert blocked.status_code == 400
    assert err_code(blocked) == "validation_error"


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

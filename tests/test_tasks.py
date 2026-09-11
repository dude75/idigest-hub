import pytest

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    LOADED_ENGINES,
    add_worker,
    default_tariff_id,
    err_code,
    get_task_row,
    login,
    login_ready,
    logout,
    me,
    open_db,
    seed_node_health,
    set_task_queued_at_past,
    setup_admin,
    signup,
    upload_audio,
)


def _org_user_with_audio(client, fake_workers=None, *, seed=True, email="user@example.com"):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client)
    if seed:
        seed_node_health(worker["id"])
    logout(client)
    assert signup(client, email, "userpass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    return {"tariff_id": tariff_id, "worker": worker, "audio": audio.json(), "me": me(client)}


def test_transcribe_queued_then_success_with_transcript(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queued"
    fake_workers.poll_mode = "success"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["status"] in {"queued", "running"}
    polled = client.get(f"/api/v1/tasks/{body['task_id']}")
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "success"
    assert polled.json()["meta"]["audio_duration_sec"] == fake_workers.audio_duration_sec
    transcript = client.get(f"/api/v1/transcripts/{polled.json()['transcript_id']}")
    assert transcript.status_code == 200, transcript.text
    assert transcript.json()["utterances"] == fake_workers.transcript


def test_queue_full_stays_queued_without_dispatch_timeout(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queue_full"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]
    row = get_task_row(task_id)
    assert row.retry_without_timeout is True
    set_task_queued_at_past(task_id)
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "queued"
    assert later.json().get("error") is None


def test_engines_unavailable_stays_queued_without_dispatch_timeout(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    add_worker(client)
    fake_workers.health = {
        "status": "ok",
        "version": "x",
        "engines": {**LOADED_ENGINES, "whisper": "unavailable"},
    }
    logout(client)
    assert signup(client, "wait@example.com", "waitpass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]
    row = get_task_row(task_id)
    assert row.retry_without_timeout is True
    set_task_queued_at_past(task_id)
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200
    assert later.json()["status"] == "queued"


def test_empty_pool_times_out_after_queued_at_in_past(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "empty@example.com", "emptypass", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]
    set_task_queued_at_past(task_id)
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "error"
    assert later.json()["error"]["code"] == "dispatch_timeout"


def test_worker_404_redispatches_same_hub_task_without_second_transcript(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queued"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    assert get_task_row(task_id).worker_task_id == "w1"
    fake_workers.poll_mode = "404"
    fake_workers.transcribe_mode = "success"
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "success"
    assert later.json()["task_id"] == task_id
    assert fake_workers.post_count == 2
    listed = client.get("/api/v1/transcripts")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_network_error_keeps_worker_task_and_does_not_open_second_node(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    first = add_worker(client, name="a", base_url="http://w1.test")
    second = add_worker(client, name="b", base_url="http://w2.test")
    seed_node_health(first["id"])
    seed_node_health(second["id"])
    logout(client)
    assert signup(client, "net@example.com", "netpass12", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    fake_workers.transcribe_mode = "queued"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    assigned = get_task_row(task_id)
    assert assigned.worker_task_id == "w1"
    first_node = assigned.worker_id
    assert fake_workers.post_count == 1
    fake_workers.poll_mode = "network"
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "running"
    after = get_task_row(task_id)
    assert after.worker_task_id == "w1"
    assert after.worker_id == first_node
    assert fake_workers.post_count == 1
    assert set(fake_workers.nodes_posted) == {first_node}


def test_cancel_only_queued_without_worker_task(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "can@example.com", "canpass12", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    queued = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    canceled = client.delete(f"/api/v1/tasks/{queued.json()['task_id']}")
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "error"
    assert canceled.json()["error"]["code"] == "canceled"

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)
    login(client, "can@example.com", "canpass12")
    fake_workers.transcribe_mode = "queued"
    running = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert running.status_code == 202, running.text
    assert running.json()["status"] == "running"
    blocked = client.delete(f"/api/v1/tasks/{running.json()['task_id']}")
    assert blocked.status_code == 409
    assert err_code(blocked) == "task_running"


def test_wipe_source_while_queued_cancels_without_charge(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "wipeq@example.com", "wipepass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]
    wiped = client.delete(f"/api/v1/audios/{audio.json()['id']}")
    assert wiped.status_code == 200, wiped.text
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "error"
    assert later.json()["error"]["code"] == "canceled"
    org = client.get("/api/v1/org").json()
    assert org["balance"] == "0.00"
    assert org["usage"]["total_amount"] in {"0", "0.00"}


def test_wipe_source_while_running_charges_but_skips_library(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queued"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "running"
    task_id = created.json()["task_id"]
    wiped = client.delete(f"/api/v1/audios/{ctx['audio']['id']}")
    assert wiped.status_code == 200, wiped.text
    row = get_task_row(task_id)
    assert row.skip_persist is True
    fake_workers.poll_mode = "success"
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "error"
    assert later.json()["error"]["code"] == "source_deleted"
    assert later.json()["transcript_id"] is None
    listed = client.get("/api/v1/transcripts")
    assert listed.json()["items"] == []
    org = client.get("/api/v1/org").json()
    assert "usage" in org


def test_copy_skill_works(client):
    setup_admin(client)
    base = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert base.status_code == 200, base.text
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "skill@example.com", "skillpass", tariff_id).status_code == 200
    copied = client.post(f"/api/v1/skills/{base.json()['id']}/copy")
    assert copied.status_code == 200, copied.text
    assert copied.json()["scope"] == "self"
    assert copied.json()["name"] == "Minutes"
    assert copied.json()["body"] == "Sum it up"
    assert copied.json()["id"] != base.json()["id"]
    catalog = client.get("/api/v1/skills")
    assert catalog.status_code == 200
    scopes = {item["id"]: item["scope"] for item in catalog.json()["items"]}
    assert scopes[copied.json()["id"]] == "self"


def test_several_transcripts_on_one_audio(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "success"
    first = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    second = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["status"] == "success"
    assert second.json()["status"] == "success"
    assert first.json()["transcript_id"] != second.json()["transcript_id"]
    detail = client.get(f"/api/v1/audios/{ctx['audio']['id']}")
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["transcripts"]) == 2


def test_impersonate_artifacts_owned_by_impersonated_user(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)
    assert signup(client, "target@example.com", "targetpass", tariff_id).status_code == 200
    target_id = me(client)["user"]["id"]
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    impersonate = client.post("/api/v1/impersonate", json={"user_id": target_id})
    assert impersonate.status_code == 200, impersonate.text
    who = me(client)
    assert who["impersonating"] is True
    assert who["user"]["id"] == target_id
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    assert audio.json()["owner_user_id"] == target_id
    fake_workers.transcribe_mode = "success"
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    assert task.json()["status"] == "success"
    transcript = client.get(f"/api/v1/transcripts/{task.json()['transcript_id']}")
    assert transcript.status_code == 200
    assert transcript.json()["owner_user_id"] == target_id
    assert transcript.json()["owner_user_id"] != who["actor"]["id"]


def test_worker_error_codes_mapped_not_raw(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "error"
    fake_workers.error_code = "totally_unknown_worker_code"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "error"
    assert created.json()["error"]["code"] == "pipeline_error"

    fake_workers.error_code = "ffmpeg_timeout"
    again = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert again.status_code == 202, again.text
    assert again.json()["error"]["code"] == "pipeline_error"


def test_dispatch_uses_snap_asr_model_after_settings_change(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "asr@example.com", "asrpass12", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]
    assert get_task_row(task_id).snap_asr_model == "whisper"

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    patched = client.patch("/api/v1/instance/settings", json={"asr_model": "gigaam"})
    assert patched.status_code == 200, patched.text
    add_worker(client)
    logout(client)
    login(client, "asr@example.com", "asrpass12")
    fake_workers.transcribe_mode = "success"
    later = client.get(f"/api/v1/tasks/{task_id}")
    assert later.status_code == 200, later.text
    assert later.json()["status"] == "success"
    assert fake_workers.asr_models_seen == ["whisper"]
    assert get_task_row(task_id).snap_asr_model == "whisper"


def test_list_tasks_scoped_by_role(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)

    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    member = client.post(
        "/api/v1/org/users",
        json={"email": "mem@example.com", "password": "mempass12", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    fake_workers.transcribe_mode = "success"
    lead_audio = upload_audio(client)
    assert lead_audio.status_code == 200, lead_audio.text
    lead_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": lead_audio.json()["id"]})
    assert lead_task.status_code == 202, lead_task.text
    lead_id = lead_task.json()["task_id"]

    logout(client)
    login_ready(client, "mem@example.com", "mempass12")
    mem_audio = upload_audio(client)
    assert mem_audio.status_code == 200, mem_audio.text
    mem_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": mem_audio.json()["id"]})
    assert mem_task.status_code == 202, mem_task.text
    mem_id = mem_task.json()["task_id"]

    member_list = client.get("/api/v1/tasks")
    assert member_list.status_code == 200, member_list.text
    assert {item["task_id"] for item in member_list.json()["items"]} == {mem_id}
    assert member_list.json()["items"][0]["owner_email"] == "mem@example.com"

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    admin_list = client.get("/api/v1/tasks")
    assert admin_list.status_code == 200, admin_list.text
    assert {item["task_id"] for item in admin_list.json()["items"]} == {lead_id, mem_id}

    logout(client)
    assert signup(client, "other@example.com", "otherpass", tariff_id).status_code == 200
    other_audio = upload_audio(client)
    assert other_audio.status_code == 200, other_audio.text
    other_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": other_audio.json()["id"]})
    assert other_task.status_code == 202, other_task.text
    other_id = other_task.json()["task_id"]
    other_list = client.get("/api/v1/tasks")
    assert {item["task_id"] for item in other_list.json()["items"]} == {other_id}

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    inst_list = client.get("/api/v1/tasks")
    assert inst_list.status_code == 200, inst_list.text
    assert {item["task_id"] for item in inst_list.json()["items"]} == {lead_id, mem_id, other_id}
    hidden = client.get(f"/api/v1/tasks/{lead_id}")
    assert hidden.status_code == 200

    logout(client)
    login_ready(client, "mem@example.com", "mempass12")
    denied = client.get(f"/api/v1/tasks/{lead_id}")
    assert denied.status_code == 404


def test_list_tasks_admin_filters(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)

    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    lead_org = me(client)["org"]["id"]
    member = client.post(
        "/api/v1/org/users",
        json={"email": "mem@example.com", "password": "mempass12", "role": "org_member"},
    )
    assert member.status_code == 200, member.text
    mem_user_id = member.json()["id"]
    fake_workers.transcribe_mode = "success"
    lead_audio = upload_audio(client)
    assert lead_audio.status_code == 200, lead_audio.text
    lead_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": lead_audio.json()["id"]})
    assert lead_task.status_code == 202, lead_task.text
    lead_id = lead_task.json()["task_id"]
    lead_user_id = lead_task.json()["user_id"]

    logout(client)
    login_ready(client, "mem@example.com", "mempass12")
    mem_audio = upload_audio(client)
    mem_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": mem_audio.json()["id"]})
    mem_id = mem_task.json()["task_id"]
    scoped = client.get(f"/api/v1/tasks?user_id={lead_user_id}")
    assert {item["task_id"] for item in scoped.json()["items"]} == {mem_id}

    logout(client)
    login_ready(client, "lead@example.com", "leadpass1")
    all_org = client.get("/api/v1/tasks")
    assert {item["task_id"] for item in all_org.json()["items"]} == {lead_id, mem_id}
    by_mem = client.get(f"/api/v1/tasks?user_id={mem_user_id}")
    assert {item["task_id"] for item in by_mem.json()["items"]} == {mem_id}

    logout(client)
    assert signup(client, "other@example.com", "otherpass", tariff_id).status_code == 200
    other_org = me(client)["org"]["id"]
    other_audio = upload_audio(client)
    other_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": other_audio.json()["id"]})
    other_id = other_task.json()["task_id"]
    other_user_id = other_task.json()["user_id"]
    ignored_org = client.get(f"/api/v1/tasks?org_id={lead_org}")
    assert {item["task_id"] for item in ignored_org.json()["items"]} == {other_id}

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    inst_all = client.get("/api/v1/tasks")
    assert {item["task_id"] for item in inst_all.json()["items"]} == {lead_id, mem_id, other_id}
    by_org = client.get(f"/api/v1/tasks?org_id={lead_org}")
    assert {item["task_id"] for item in by_org.json()["items"]} == {lead_id, mem_id}
    by_org_user = client.get(f"/api/v1/tasks?org_id={lead_org}&user_id={mem_user_id}")
    assert {item["task_id"] for item in by_org_user.json()["items"]} == {mem_id}
    by_user = client.get(f"/api/v1/tasks?user_id={other_user_id}")
    assert {item["task_id"] for item in by_user.json()["items"]} == {other_id}
    other_org_list = client.get(f"/api/v1/tasks?org_id={other_org}")
    assert {item["task_id"] for item in other_org_list.json()["items"]} == {other_id}


@pytest.mark.asyncio
async def test_recover_import_running_after_restart(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "recover@example.com", "recoverpass", tariff_id).status_code == 200
    user = me(client)

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
            type="import",
            status="running",
            org_id=org.id,
            user_id=user["user"]["id"],
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "stage": "downloading",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()

        await recover_orphaned_tasks(db)
        db.expire_all()
        recovered = db.get(Task, task.id)
        assert recovered is not None
        assert recovered.status == "queued"
        assert recovered.meta_json["stage"] == "queued"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recover_transcribe_unreachable_requeues(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queued"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    assert get_task_row(task_id).status == "running"

    db = open_db()
    try:
        from app.services.dispatcher import recover_orphaned_tasks

        fake_workers.poll_mode = "network"
        await recover_orphaned_tasks(db)
        db.expire_all()
        from app.models import Task

        recovered = db.get(Task, task_id)
        assert recovered is not None
        assert recovered.status == "queued"
        assert recovered.worker_id is None
        assert recovered.worker_task_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recover_transcribe_worker_still_running_keeps_status(client, fake_workers):
    ctx = _org_user_with_audio(client)
    fake_workers.transcribe_mode = "queued"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]
    before = get_task_row(task_id)

    db = open_db()
    try:
        from app.services.dispatcher import recover_orphaned_tasks

        fake_workers.poll_mode = "running"
        await recover_orphaned_tasks(db)
        db.expire_all()
        from app.models import Task

        recovered = db.get(Task, task_id)
        assert recovered is not None
        assert recovered.status == "running"
        assert recovered.worker_id == before.worker_id
        assert recovered.worker_task_id == before.worker_task_id
    finally:
        db.close()


import json

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    add_worker,
    get_task_row,
    login,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
    wait_task,
)


def test_delete_impact_reports_lost_pair(client):
    setup_admin(client)
    keeper = add_worker(client, name="keeper", asr_models=["parakeet"], diarization_models=["nemo"])
    doomed = add_worker(client, name="doomed", asr_models=["whisper"], diarization_models=["pyannote"])

    impact = client.get(f"/api/v1/workers/{doomed['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["blocking"] is True
    assert {"asr_model": "whisper", "diarization_model": "pyannote"} in body["lost_model_pairs"]
    assert body["remaining_transcribe_workers"] == 1
    assert keeper["id"] != doomed["id"]


def test_delete_impact_no_loss_when_disabled_worker(client):
    setup_admin(client)
    add_worker(client, name="main", asr_models=["whisper"], diarization_models=["pyannote"])
    spare = add_worker(client, name="spare", asr_models=["parakeet"], diarization_models=["nemo"])
    patched = client.patch(
        f"/api/v1/workers/{spare['id']}",
        json={
            "type": "transcribe",
            "name": "spare",
            "base_url": spare["base_url"],
            "weight": 1,
            "enabled": False,
            "asr_models": ["parakeet"],
            "diarization_models": ["nemo"],
        },
    )
    assert patched.status_code == 200, patched.text

    impact = client.get(f"/api/v1/workers/{spare['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["lost_model_pairs"] == []
    assert body["blocking"] is False


def test_delete_impact_affected_user_and_task(client, fake_workers):
    fake_workers.transcribe_mode = "queue_full"
    setup_admin(client)
    doomed = add_worker(client, name="only-combo", asr_models=["parakeet"], diarization_models=["pyannote"])
    add_worker(client, name="other", asr_models=["whisper"], diarization_models=["nemo"])
    client.patch("/api/v1/instance/settings", json={"asr_model": "whisper", "diarization_model": "nemo"})

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "impact@example.com", "impactpass12", tariff_id).status_code == 200
    login(client, "impact@example.com", "impactpass12")
    client.patch("/api/v1/me", json={"asr_model": "parakeet", "diarization_model": "pyannote"})
    audio = upload_audio(client)
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    impact = client.get(f"/api/v1/workers/{doomed['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["affected_users_count"] >= 1
    assert body["affected_tasks_count"] >= 1
    assert any(user["email"] == "impact@example.com" for user in body["affected_users"])


def test_change_impact_reports_lost_pair(client):
    setup_admin(client)
    worker = add_worker(client, name="combo", asr_models=["parakeet", "whisper"], diarization_models=["pyannote"])
    add_worker(client, name="other", asr_models=["whisper"], diarization_models=["nemo"])

    impact = client.post(
        f"/api/v1/workers/{worker['id']}/change-impact",
        json={
            "type": "transcribe",
            "name": "combo",
            "base_url": worker["base_url"],
            "weight": 1,
            "enabled": True,
            "asr_models": ["whisper"],
            "diarization_models": ["pyannote"],
        },
    )
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["action"] == "change"
    assert {"asr_model": "parakeet", "diarization_model": "pyannote"} in body["lost_model_pairs"]


def test_change_impact_disable_matches_delete(client):
    setup_admin(client)
    worker = add_worker(client, name="combo", asr_models=["parakeet"], diarization_models=["pyannote"])
    add_worker(client, name="other", asr_models=["whisper"], diarization_models=["nemo"])

    change = client.post(
        f"/api/v1/workers/{worker['id']}/change-impact",
        json={
            "type": "transcribe",
            "name": "combo",
            "base_url": worker["base_url"],
            "weight": 1,
            "enabled": False,
            "asr_models": ["parakeet"],
            "diarization_models": ["pyannote"],
        },
    )
    delete = client.get(f"/api/v1/workers/{worker['id']}/delete-impact")
    assert change.status_code == 200, change.text
    assert delete.status_code == 200, delete.text
    assert change.json()["lost_model_pairs"] == delete.json()["lost_model_pairs"]


def test_delete_impact_suggests_replacement(client):
    setup_admin(client)
    add_worker(client, name="keeper", asr_models=["whisper"], diarization_models=["nemo"])
    doomed = add_worker(client, name="doomed", asr_models=["parakeet"], diarization_models=["pyannote"])

    impact = client.get(f"/api/v1/workers/{doomed['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["can_remediate"] is True
    assert body["suggested_replacement"] == {"asr_model": "whisper", "diarization_model": "nemo"}
    assert {"asr_model": "whisper", "diarization_model": "nemo"} in body["available_pairs"]


def test_delete_with_remediation_updates_user_and_task(client, fake_workers):
    fake_workers.transcribe_mode = "queue_full"
    setup_admin(client)
    doomed = add_worker(client, name="only-combo", asr_models=["parakeet"], diarization_models=["pyannote"])
    add_worker(client, name="other", asr_models=["whisper"], diarization_models=["nemo"])

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "impact@example.com", "impactpass12", tariff_id).status_code == 200
    login(client, "impact@example.com", "impactpass12")
    client.patch("/api/v1/me", json={"asr_model": "parakeet", "diarization_model": "pyannote"})
    audio = upload_audio(client)
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    task_id = task.json()["task_id"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    deleted = client.request(
        "DELETE",
        f"/api/v1/workers/{doomed['id']}",
        content=json.dumps({"remediation": {"asr_model": "whisper", "diarization_model": "nemo"}}),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": client.cookies.get("hub_csrf") or "",
        },
    )
    assert deleted.status_code == 200, deleted.text
    remediation = deleted.json()["remediation"]
    assert remediation["users_updated"] >= 1
    assert remediation["tasks_updated"] >= 1

    login(client, "impact@example.com", "impactpass12")
    me = client.get("/api/v1/me").json()
    assert me["user"]["asr_model"] == "whisper"
    assert me["user"]["diarization_model"] == "nemo"

    row = get_task_row(task_id)
    assert row.snap_asr_model == "whisper"
    assert row.snap_diarization_model == "nemo"


def test_patch_with_remediation_updates_entities(client, fake_workers):
    fake_workers.transcribe_mode = "queue_full"
    setup_admin(client)
    worker = add_worker(client, name="combo", asr_models=["parakeet", "whisper"], diarization_models=["pyannote"])
    add_worker(client, name="other", asr_models=["whisper"], diarization_models=["nemo"])

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "patch@example.com", "patchpass12", tariff_id).status_code == 200
    login(client, "patch@example.com", "patchpass12")
    client.patch("/api/v1/me", json={"asr_model": "parakeet", "diarization_model": "pyannote"})
    audio = upload_audio(client)
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    task_id = task.json()["task_id"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    patched = client.patch(
        f"/api/v1/workers/{worker['id']}",
        json={
            "type": "transcribe",
            "name": "combo",
            "base_url": worker["base_url"],
            "weight": 1,
            "enabled": True,
            "asr_models": ["whisper"],
            "diarization_models": ["pyannote"],
            "remediation": {"asr_model": "whisper", "diarization_model": "nemo"},
        },
    )
    assert patched.status_code == 200, patched.text
    remediation = patched.json()["remediation"]
    assert remediation["users_updated"] >= 1
    assert remediation["tasks_updated"] >= 1

    login(client, "patch@example.com", "patchpass12")
    me = client.get("/api/v1/me").json()
    assert me["user"]["asr_model"] == "whisper"
    assert me["user"]["diarization_model"] == "nemo"

    row = get_task_row(task_id)
    assert row.snap_asr_model == "whisper"
    assert row.snap_diarization_model == "nemo"


def test_delete_impact_last_summarize_worker(client):
    setup_admin(client)
    worker = add_worker(client, type="summarize", name="sum-1")
    impact = client.get(f"/api/v1/workers/{worker['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["last_enabled_worker"] is True
    assert body["blocking"] is True


def _seed_summarize_worker(client, *, name: str, base_url: str, model: str) -> dict:
    worker = add_worker(client, type="summarize", name=name, base_url=base_url)
    seed_node_health(worker["id"], {"status": "ok", "version": "x", "model": model}, ready_http=200)
    return worker


def test_delete_impact_summarize_model_can_remediate(client):
    setup_admin(client)
    doomed = _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    _seed_summarize_worker(client, name="sum-b", base_url="http://sum-b.test", model="llm-b")
    client.patch("/api/v1/instance/settings", json={"summarize_model": "llm-a"})

    impact = client.get(f"/api/v1/workers/{doomed['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["can_remediate"] is True
    assert body["suggested_summarize_replacement"] == {"summarize_model": "llm-b"}
    assert {"summarize_model": "llm-b"} in body["available_summarize_models"]
    assert "llm-a" in body["lost_summarize_models"]


def test_delete_summarize_worker_with_remediation_updates_user_and_task(client, fake_workers):
    fake_workers.summarize_mode = "queue_full"
    setup_admin(client)
    transcribe_worker = add_worker(client, name="asr")
    seed_node_health(transcribe_worker["id"])
    doomed = _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    _seed_summarize_worker(client, name="sum-b", base_url="http://sum-b.test", model="llm-b")
    client.patch("/api/v1/instance/settings", json={"summarize_model": "llm-a"})
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert skill.status_code == 200, skill.text

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "sumimpact@example.com", "sumimpactpass1", tariff_id).status_code == 200
    login(client, "sumimpact@example.com", "sumimpactpass1")
    client.patch("/api/v1/me", json={"summarize_model": "llm-a"})
    fake_workers.transcribe_mode = "success"
    audio = upload_audio(client)
    transcribed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert transcribed.status_code == 202, transcribed.text
    transcript_id = wait_task(client, transcribed.json()["task_id"], status="success")["transcript_id"]
    task = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": transcript_id, "skill_ids": [skill.json()["id"]]},
    )
    assert task.status_code == 202, task.text
    task_id = task.json()["task_id"]

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    deleted = client.request(
        "DELETE",
        f"/api/v1/workers/{doomed['id']}",
        content=json.dumps({"remediation": {"summarize_model": "llm-b"}}),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": client.cookies.get("hub_csrf") or "",
        },
    )
    assert deleted.status_code == 200, deleted.text
    remediation = deleted.json()["remediation"]
    assert remediation["users_updated"] >= 1
    assert remediation["tasks_updated"] >= 1

    login(client, "sumimpact@example.com", "sumimpactpass1")
    me = client.get("/api/v1/me").json()
    assert me["user"]["summarize_model"] == "llm-b"

    row = get_task_row(task_id)
    assert row.snap_summarize_model == "llm-b"


def test_delete_impact_capture_can_remediate(client, fake_workers):
    setup_admin(client)
    doomed = add_worker(client, type="capture", name="cap-a", base_url="http://capture-a.test")
    keeper = add_worker(client, type="capture", name="cap-b", base_url="http://capture-b.test")
    seed_node_health(doomed["id"])
    seed_node_health(keeper["id"])
    client.patch("/api/v1/instance/settings", json={"capture_enabled": True})
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "capimpact@example.com", "capimpactpass1", tariff_id).status_code == 200
    login(client, "capimpact@example.com", "capimpactpass1")
    assert client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": "meet.example.com", "worker_id": doomed["id"]}]},
    ).status_code == 200

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    impact = client.get(f"/api/v1/workers/{doomed['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["blocking"] is True
    assert body["can_remediate"] is True
    assert body["suggested_capture_worker"]["id"] == keeper["id"]
    assert {item["id"] for item in body["available_capture_workers"]} == {keeper["id"]}


def test_delete_capture_worker_with_remediation_reassigns_jitsi_host(client, fake_workers):
    setup_admin(client)
    doomed = add_worker(client, type="capture", name="cap-a", base_url="http://capture-a.test")
    keeper = add_worker(client, type="capture", name="cap-b", base_url="http://capture-b.test")
    seed_node_health(doomed["id"])
    seed_node_health(keeper["id"])
    client.patch("/api/v1/instance/settings", json={"capture_enabled": True})
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "capremed@example.com", "capremedpass1", tariff_id).status_code == 200
    login(client, "capremed@example.com", "capremedpass1")
    assert client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": "meet.example.com", "worker_id": doomed["id"]}]},
    ).status_code == 200

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    deleted = client.request(
        "DELETE",
        f"/api/v1/workers/{doomed['id']}",
        content=json.dumps({"remediation": {"capture_worker_id": keeper["id"]}}),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": client.cookies.get("hub_csrf") or "",
        },
    )
    assert deleted.status_code == 200, deleted.text
    remediation = deleted.json()["remediation"]
    assert remediation["jitsi_hosts_updated"] == 1

    login(client, "capremed@example.com", "capremedpass1")
    hosts = client.get("/api/v1/org/capture/jitsi").json()["items"]
    assert len(hosts) == 1
    assert hosts[0]["host"] == "meet.example.com"
    assert hosts[0]["worker_id"] == keeper["id"]


def test_delete_capture_worker_removes_jitsi_host_map(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap", base_url="http://capture.test")
    seed_node_health(worker["id"])
    client.patch("/api/v1/instance/settings", json={"capture_enabled": True})
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "delcap@example.com", "delcappass12", tariff_id).status_code == 200
    login(client, "delcap@example.com", "delcappass12")
    mapped = client.put(
        "/api/v1/org/capture/jitsi",
        json={"items": [{"host": "meet.example.com", "worker_id": worker["id"]}]},
    )
    assert mapped.status_code == 200, mapped.text

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    deleted = client.delete(f"/api/v1/workers/{worker['id']}")
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["cleanup"]["jitsi_hosts_removed"] == 1

    workers = client.get("/api/v1/workers").json()["items"]
    assert all(row["id"] != worker["id"] for row in workers)

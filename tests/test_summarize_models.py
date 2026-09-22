from tests.conftest import (
    add_worker,
    get_task_row,
    login,
    me,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
    wait_task,
)


def _seed_summarize_worker(client, *, name: str, base_url: str, model: str) -> dict:
    worker = add_worker(client, type="summarize", name=name, base_url=base_url)
    seed_node_health(worker["id"], {"status": "ok", "version": "x", "model": model}, ready_http=200)
    return worker


def test_instance_summarize_models_aggregate(client):
    setup_admin(client)
    _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    listed = client.get("/api/v1/instance/summarize-models")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert "llm-a" in body["summarize_models"]


def test_settings_rejects_unknown_summarize_model(client):
    setup_admin(client)
    _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    bad = client.patch("/api/v1/instance/settings", json={"summarize_model": "llm-b"})
    assert bad.status_code == 400


def test_user_can_override_summarize_model(client):
    setup_admin(client)
    _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    _seed_summarize_worker(client, name="sum-b", base_url="http://sum-b.test", model="llm-b")
    client.patch("/api/v1/instance/settings", json={"summarize_model": "llm-a"})

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "sumuser@example.com", "sumuserpass1", tariff_id).status_code == 200
    login(client, "sumuser@example.com", "sumuserpass1")

    patched = client.patch("/api/v1/me", json={"summarize_model": "llm-b"})
    assert patched.status_code == 200, patched.text
    payload = me(client)
    assert payload["user"]["summarize_model"] == "llm-b"
    assert payload["summarize_prefs"]["summarize_model"] == "llm-b"


def test_summarize_task_snapshots_model(client, fake_workers):
    setup_admin(client)
    transcribe_worker = add_worker(client, name="asr")
    seed_node_health(transcribe_worker["id"])
    _seed_summarize_worker(client, name="sum-a", base_url="http://sum-a.test", model="llm-a")
    client.patch("/api/v1/instance/settings", json={"summarize_model": "llm-a"})
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert skill.status_code == 200, skill.text

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "sumtask@example.com", "sumtaskpass1", tariff_id).status_code == 200
    login(client, "sumtask@example.com", "sumtaskpass1")
    client.patch("/api/v1/me", json={"summarize_model": "llm-a"})

    fake_workers.transcribe_mode = "success"
    audio = upload_audio(client)
    transcribed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert transcribed.status_code == 202, transcribed.text
    transcript_id = wait_task(client, transcribed.json()["task_id"], status="success")["transcript_id"]

    created = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": transcript_id, "skill_ids": [skill.json()["id"]]},
    )
    assert created.status_code == 202, created.text
    row = get_task_row(created.json()["task_id"])
    assert row.snap_summarize_model == "llm-a"

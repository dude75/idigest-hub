from tests.conftest import (
    ADMIN_PASSWORD,
    DEFAULT_WORKER_ASR_MODELS,
    DEFAULT_WORKER_DIARIZATION_MODELS,
    LOADED_ENGINES,
    add_worker,
    login,
    me,
    setup_admin,
    signup,
    upload_audio,
)


def test_worker_probe_lists_models(client):
    setup_admin(client)
    probed = client.post(
        "/api/v1/workers/probe",
        json={"type": "transcribe", "base_url": "http://worker.test", "api_token": "tok"},
    )
    assert probed.status_code == 200, probed.text
    body = probed.json()
    assert body["authorized"] is True
    assert {item["id"] for item in body["asr_models"]} == {"whisper", "gigaam", "parakeet"}
    assert {item["id"] for item in body["diarization_models"]} == {"nemo", "pyannote"}


def test_worker_create_requires_asr_models(client):
    setup_admin(client)
    missing = client.post(
        "/api/v1/workers",
        json={
            "type": "transcribe",
            "name": "asr",
            "base_url": "http://worker.test",
            "api_token": "tok",
            "weight": 1,
            "enabled": True,
        },
    )
    assert missing.status_code == 400


def test_instance_transcribe_models_aggregate(client):
    setup_admin(client)
    worker = add_worker(
        client,
        asr_models=["whisper"],
        diarization_models=["pyannote"],
    )
    listed = client.get("/api/v1/instance/transcribe-models")
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert "whisper" in body["asr_models"]
    assert "pyannote" in body["diarization_models"]
    assert worker["asr_models"] == ["whisper"]
    assert worker["diarization_models"] == ["pyannote"]


def test_settings_rejects_unknown_model(client):
    setup_admin(client)
    add_worker(client, asr_models=["whisper"], diarization_models=["pyannote"])
    bad = client.patch("/api/v1/instance/settings", json={"asr_model": "gigaam"})
    assert bad.status_code == 400


def test_user_can_override_transcribe_models(client):
    setup_admin(client)
    add_worker(client, asr_models=list(DEFAULT_WORKER_ASR_MODELS), diarization_models=["pyannote"])
    client.patch("/api/v1/instance/settings", json={"asr_model": "whisper", "diarization_model": "pyannote"})

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "user@example.com", "userpass12", tariff_id).status_code == 200
    login(client, "user@example.com", "userpass12")

    patched = client.patch("/api/v1/me", json={"asr_model": "gigaam", "diarization_model": ""})
    assert patched.status_code == 200, patched.text
    payload = me(client)
    assert payload["transcribe_prefs"]["asr_model"] == "gigaam"
    assert payload["transcribe_prefs"]["diarization_model"] is None
    assert payload["transcribe_prefs"]["asr_source"] == "user"
    assert payload["transcribe_prefs"]["diarization_source"] == "user"


def test_task_uses_user_model_snapshot(client, fake_workers):
    setup_admin(client)
    add_worker(client, asr_models=list(DEFAULT_WORKER_ASR_MODELS), diarization_models=list(DEFAULT_WORKER_DIARIZATION_MODELS))
    client.patch("/api/v1/instance/settings", json={"asr_model": "whisper", "diarization_model": "pyannote"})

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "snap@example.com", "snappass12", tariff_id).status_code == 200
    login(client, "snap@example.com", "snappass12")
    client.patch("/api/v1/me", json={"asr_model": "gigaam"})

    audio = upload_audio(client)
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text

    from tests.conftest import get_task_row

    row = get_task_row(task.json()["task_id"])
    assert row.snap_asr_model == "gigaam"
    assert row.snap_diarization_model == "pyannote"

import pytest

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


def test_split_workers_reject_invalid_combo(client):
    setup_admin(client)
    add_worker(client, name="asr-a", asr_models=["parakeet"], diarization_models=["nemo"])
    add_worker(client, name="asr-b", asr_models=["whisper"], diarization_models=["pyannote"])

    bad = client.patch("/api/v1/instance/settings", json={"asr_model": "parakeet", "diarization_model": "pyannote"})
    assert bad.status_code == 400


def test_dispatchable_pairs_listed(client):
    setup_admin(client)
    add_worker(client, asr_models=["parakeet"], diarization_models=["nemo"])
    add_worker(client, asr_models=["whisper"], diarization_models=["pyannote"])

    listed = client.get("/api/v1/instance/transcribe-models")
    assert listed.status_code == 200, listed.text
    pairs = {(item["asr_model"], item["diarization_model"]) for item in listed.json()["dispatchable_pairs"]}
    assert ("parakeet", "nemo") in pairs
    assert ("whisper", "pyannote") in pairs
    assert ("parakeet", "pyannote") not in pairs


def test_user_rejects_invalid_model_combo(client):
    setup_admin(client)
    add_worker(client, asr_models=["parakeet"], diarization_models=["nemo"])
    add_worker(client, asr_models=["whisper"], diarization_models=["pyannote"])
    client.patch("/api/v1/instance/settings", json={"asr_model": "parakeet", "diarization_model": "nemo"})

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "combo@example.com", "combopass12", tariff_id).status_code == 200
    login(client, "combo@example.com", "combopass12")

    bad = client.patch("/api/v1/me", json={"diarization_model": "pyannote"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_dispatch_marks_no_matching_worker(client):
    setup_admin(client)
    add_worker(client, name="asr-a", asr_models=["parakeet"], diarization_models=["nemo"])
    add_worker(client, name="asr-b", asr_models=["whisper"], diarization_models=["pyannote"])

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Task, WorkerNode, new_id
    from app.services.dispatcher import dispatch_queued_task
    from app.timeutil import utcnow

    now = utcnow()
    db = SessionLocal()
    try:
        nodes = list(db.scalars(select(WorkerNode)).all())
        task = Task(
            id=new_id(),
            type="transcribe",
            status="queued",
            org_id="org",
            user_id="user",
            audio_id="audio",
            queued_at=now,
            created_at=now,
            updated_at=now,
            snap_asr_model="parakeet",
            snap_diarization_model="pyannote",
        )
        await dispatch_queued_task(db, task, nodes, timeout_sec=0)
        assert task.meta_json["stage"] == "no_matching_worker"
        assert task.meta_json["asr_model"] == "parakeet"
        assert task.meta_json["diarization_model"] == "pyannote"
    finally:
        db.close()

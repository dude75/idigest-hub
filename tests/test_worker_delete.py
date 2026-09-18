import pytest

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, add_worker, login, setup_admin, signup, upload_audio


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


def test_delete_impact_last_summarize_worker(client):
    setup_admin(client)
    worker = add_worker(client, type="summarize", name="sum-1")
    impact = client.get(f"/api/v1/workers/{worker['id']}/delete-impact")
    assert impact.status_code == 200, impact.text
    body = impact.json()
    assert body["last_enabled_worker"] is True
    assert body["blocking"] is True

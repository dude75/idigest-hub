from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    add_worker,
    default_tariff_id,
    err_code,
    login,
    logout,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
)


def test_instance_stats_counts_completed_jobs_and_audio_time(client, fake_workers):
    setup_admin(client)
    empty = client.get("/api/v1/instance/stats")
    assert empty.status_code == 200, empty.text
    assert empty.json()["tasks_transcribe_success"] == 0
    assert empty.json()["tasks_summarize_success"] == 0
    assert empty.json()["audio_transcribed_sec"] == 0

    transcribe_worker = add_worker(client, type="transcribe", name="asr")
    summarize_worker = add_worker(
        client, type="summarize", name="llm", base_url="http://summarize.test"
    )
    seed_node_health(transcribe_worker["id"])
    seed_node_health(summarize_worker["id"], ready_http=200)
    skill = client.post("/api/v1/skills/base", json={"name": "Minutes", "body": "Sum it up"})
    assert skill.status_code == 200, skill.text
    tariff_id = default_tariff_id(client)
    logout(client)

    assert signup(client, "stats@example.com", "statspass", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    fake_workers.transcribe_mode = "success"
    fake_workers.audio_duration_sec = 10.0
    first = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "success"

    fake_workers.audio_duration_sec = 25.0
    second = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert second.status_code == 202, second.text
    assert second.json()["status"] == "success"

    fake_workers.transcribe_mode = "error"
    failed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert failed.status_code == 202, failed.text
    assert failed.json()["status"] == "error"

    fake_workers.summarize_mode = "success"
    summary = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": second.json()["transcript_id"], "skill_ids": [skill.json()["id"]]},
    )
    assert summary.status_code == 202, summary.text
    assert summary.json()["status"] == "success"

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    stats = client.get("/api/v1/instance/stats")
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["tasks_transcribe_success"] == 2
    assert body["tasks_summarize_success"] == 1
    assert body["audio_transcribed_sec"] == 35.0


def test_instance_stats_forbidden_for_non_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "member@example.com", "memberpass", tariff_id).status_code == 200
    response = client.get("/api/v1/instance/stats")
    assert response.status_code == 403
    assert err_code(response) == "forbidden"

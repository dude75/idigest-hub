from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    add_worker,
    default_tariff_id,
    err_code,
    login,
    login_ready,
    logout,
    me,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
)


def test_org_stats_counts_own_completed_jobs_and_audio_time(client, fake_workers):
    setup_admin(client)
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

    assert signup(client, "alice-stats@example.com", "alicepass", tariff_id).status_code == 200
    empty = client.get("/api/v1/org/stats")
    assert empty.status_code == 200, empty.text
    assert empty.json() == {
        "tasks_transcribe_success": 0,
        "tasks_summarize_success": 0,
        "audio_transcribed_sec": 0.0,
    }

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

    alice = client.get("/api/v1/org/stats")
    assert alice.status_code == 200, alice.text
    assert alice.json() == {
        "tasks_transcribe_success": 2,
        "tasks_summarize_success": 1,
        "audio_transcribed_sec": 35.0,
    }

    logout(client)
    assert signup(client, "bob-stats@example.com", "bobpass12", tariff_id).status_code == 200
    bob_audio = upload_audio(client)
    assert bob_audio.status_code == 200, bob_audio.text
    fake_workers.transcribe_mode = "success"
    fake_workers.audio_duration_sec = 8.0
    bob_task = client.post("/api/v1/tasks/transcribe", json={"audio_id": bob_audio.json()["id"]})
    assert bob_task.status_code == 202, bob_task.text
    assert bob_task.json()["status"] == "success"

    bob = client.get("/api/v1/org/stats")
    assert bob.status_code == 200, bob.text
    assert bob.json() == {
        "tasks_transcribe_success": 1,
        "tasks_summarize_success": 0,
        "audio_transcribed_sec": 8.0,
    }

    logout(client)
    login(client, "alice-stats@example.com", "alicepass")
    still_alice = client.get("/api/v1/org/stats")
    assert still_alice.json()["tasks_transcribe_success"] == 2
    assert still_alice.json()["audio_transcribed_sec"] == 35.0


def test_org_stats_forbidden_for_instance_admin_without_org(client):
    setup_admin(client)
    response = client.get("/api/v1/org/stats")
    assert response.status_code == 403
    assert err_code(response) == "forbidden"


def test_org_stats_unauthorized(client):
    setup_admin(client)
    logout(client)
    response = client.get("/api/v1/org/stats")
    assert response.status_code == 401
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.get("/api/v1/org/stats").status_code == 403


def test_org_admin_can_impersonate_member_and_stop(client):
    setup_admin(client)
    admin_id = me(client)["user"]["id"]
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    lead = me(client)
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]

    outside = signup(client, "other@example.com", "otherpass1", tariff_id)
    assert outside.status_code == 200
    other_id = me(client)["user"]["id"]
    logout(client)
    login(client, "lead@example.com", "leadpass1")

    denied_self = client.post("/api/v1/impersonate", json={"user_id": lead["user"]["id"]})
    assert denied_self.status_code == 403
    denied_other = client.post("/api/v1/impersonate", json={"user_id": other_id})
    assert denied_other.status_code == 404
    denied_admin = client.post("/api/v1/impersonate", json={"user_id": admin_id})
    assert denied_admin.status_code == 404

    started = client.post("/api/v1/impersonate", json={"user_id": member_id})
    assert started.status_code == 200, started.text
    who = me(client)
    assert who["impersonating"] is True
    assert who["user"]["id"] == member_id
    assert who["actor"]["id"] == lead["user"]["id"]
    assert who["user"]["role"] == "org_member"
    nested = client.post("/api/v1/impersonate", json={"user_id": other_id})
    assert nested.status_code == 403

    stopped = client.delete("/api/v1/impersonate")
    assert stopped.status_code == 200, stopped.text
    back = me(client)
    assert back["impersonating"] is False
    assert back["user"]["id"] == lead["user"]["id"]


def test_org_member_cannot_impersonate(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "lead2@example.com", "leadpass1", tariff_id).status_code == 200
    lead_id = me(client)["user"]["id"]
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member2@example.com", "password": "memberpass", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    logout(client)
    login_ready(client, "member2@example.com", "memberpass")
    response = client.post("/api/v1/impersonate", json={"user_id": lead_id})
    assert response.status_code == 403
    assert err_code(response) == "forbidden"
    assert client.delete("/api/v1/impersonate").status_code == 403

from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    add_worker,
    create_tariff,
    default_tariff_id,
    err_code,
    login,
    logout,
    me,
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
    assert body["summary_chars"] == 2
    assert body["days"]


def test_instance_org_ledger_shows_charges_and_wallet_topups(client, fake_workers):
    setup_admin(client)
    transcribe_worker = add_worker(client, type="transcribe", name="asr")
    seed_node_health(transcribe_worker["id"])
    paid = create_tariff(client, name="Metered ledger", price_per_audio_sec="1.000000")
    logout(client)

    assert signup(client, "ledger@example.com", "ledgerpass", paid["id"]).status_code == 200
    org_id = me(client)["org"]["id"]
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.post(f"/api/v1/orgs/{org_id}/wallet", json={"delta": "20.00"}).status_code == 200
    logout(client)
    login(client, "ledger@example.com", "ledgerpass")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    fake_workers.transcribe_mode = "success"
    fake_workers.audio_duration_sec = 12.0
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    assert task.json()["status"] == "success"

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    wallet = client.post(f"/api/v1/orgs/{org_id}/wallet", json={"delta": "5.00"})
    assert wallet.status_code == 200, wallet.text

    ledger = client.get(f"/api/v1/orgs/{org_id}/ledger")
    assert ledger.status_code == 200, ledger.text
    body = ledger.json()
    assert body["total_topup"] == "25.00"
    assert body["total_spent"] == "12.00"
    types = {item["entry_type"] for item in body["items"]}
    assert types == {"charge", "wallet"}
    charge = next(item for item in body["items"] if item["entry_type"] == "charge")
    assert charge["kind"] == "transcribe"
    assert charge["user_email"] == "ledger@example.com"
    topup = next(item for item in body["items"] if item["entry_type"] == "wallet")
    assert topup["amount"] == "5.00"
    assert topup["actor_email"] == ADMIN_EMAIL


def test_instance_org_ledger_forbidden_for_non_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "member@example.com", "memberpass", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    response = client.get(f"/api/v1/orgs/{org_id}/ledger")
    assert response.status_code == 403
    assert err_code(response) == "forbidden"


def test_instance_org_hide_and_include_hidden(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "hideorg@example.com", "hideorgp1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    assert client.post(f"/api/v1/orgs/{org_id}/hide").status_code == 200

    hidden = client.get("/api/v1/orgs")
    assert hidden.status_code == 200, hidden.text
    assert all(item["id"] != org_id for item in hidden.json()["items"])
    assert hidden.json()["hidden_count"] == 1

    shown = client.get("/api/v1/orgs?include_hidden=true")
    assert shown.status_code == 200, shown.text
    match = next(item for item in shown.json()["items"] if item["id"] == org_id)
    assert match["hidden"] is True
    assert shown.json()["hidden_count"] == 1

    assert client.post(f"/api/v1/orgs/{org_id}/unhide").status_code == 200
    restored = client.get("/api/v1/orgs")
    assert restored.status_code == 200, restored.text
    assert any(item["id"] == org_id for item in restored.json()["items"])
    assert restored.json()["hidden_count"] == 0


def test_instance_stats_forbidden_for_non_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "member@example.com", "memberpass", tariff_id).status_code == 200
    response = client.get("/api/v1/instance/stats")
    assert response.status_code == 403
    assert err_code(response) == "forbidden"

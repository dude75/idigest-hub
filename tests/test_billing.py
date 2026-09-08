from types import SimpleNamespace

from app.constants import MAX_UPLOAD_BYTES_CAP
from app.services.billing import upload_limit
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


def test_upload_limit_caps_at_one_gib():
    tariff = SimpleNamespace(max_upload_bytes=MAX_UPLOAD_BYTES_CAP * 4)
    assert upload_limit(tariff) == MAX_UPLOAD_BYTES_CAP


def test_unlimited_tariff_does_not_debit_but_records_usage(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    patched = client.patch(
        f"/api/v1/tariffs/{tariff_id}",
        json={
            "name": "Default",
            "unlimited": True,
            "available_on_signup": True,
            "price_per_audio_sec": "1.000000",
            "price_per_summarize_job": "0",
            "price_per_generated_text": "0",
            "max_upload_bytes": MAX_UPLOAD_BYTES_CAP,
        },
    )
    assert patched.status_code == 200, patched.text
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)
    assert signup(client, "free@example.com", "freepass1", tariff_id).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    fake_workers.transcribe_mode = "success"
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    assert task.json()["status"] == "success"
    org = client.get("/api/v1/org")
    assert org.status_code == 200, org.text
    body = org.json()
    assert body["balance"] == "0.00"
    assert body["unlimited"] is True
    assert "usage" in body
    assert body["usage"]["total_amount"] != "0"


def test_paid_tariff_zero_balance_rejects_transcribe(client):
    setup_admin(client)
    paid = create_tariff(client, name="Metered")
    logout(client)
    assert signup(client, "broke@example.com", "brokepass", paid["id"]).status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 429
    assert err_code(task) == "insufficient_balance"


def test_started_task_can_drive_balance_negative_and_returns_result(client, fake_workers):
    setup_admin(client)
    paid = create_tariff(client, name="Metered", price_per_audio_sec="1.000000")
    worker = add_worker(client)
    seed_node_health(worker["id"])
    logout(client)
    assert signup(client, "thin@example.com", "thinpass1", paid["id"]).status_code == 200
    org_id = me(client)["org"]["id"]
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    wallet = client.post(f"/api/v1/orgs/{org_id}/wallet", json={"delta": "0.01"})
    assert wallet.status_code == 200, wallet.text
    logout(client)
    login(client, "thin@example.com", "thinpass1")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    fake_workers.transcribe_mode = "success"
    fake_workers.audio_duration_sec = 10.0
    task = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert task.status_code == 202, task.text
    assert task.json()["status"] == "success"
    assert task.json()["transcript_id"]
    org = client.get("/api/v1/org").json()
    assert float(org["balance"]) < 0
    transcript = client.get(f"/api/v1/transcripts/{task.json()['transcript_id']}")
    assert transcript.status_code == 200, transcript.text
    assert transcript.json()["utterances"]


def test_charge_uses_snapshot_prices_after_tariff_change(client, fake_workers):
    setup_admin(client)
    cheap = create_tariff(client, name="Cheap", price_per_audio_sec="1.000000")
    expensive = create_tariff(client, name="Expensive", price_per_audio_sec="50.000000")
    logout(client)
    assert signup(client, "snap@example.com", "snappass1", cheap["id"]).status_code == 200
    org_id = me(client)["org"]["id"]
    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.post(f"/api/v1/orgs/{org_id}/wallet", json={"delta": "100.00"}).status_code == 200
    logout(client)
    login(client, "snap@example.com", "snappass1")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued"
    task_id = created.json()["task_id"]

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    switched = client.patch(f"/api/v1/orgs/{org_id}/tariff", json={"tariff_id": expensive["id"]})
    assert switched.status_code == 200, switched.text
    add_worker(client)
    logout(client)
    login(client, "snap@example.com", "snappass1")
    fake_workers.transcribe_mode = "success"
    fake_workers.audio_duration_sec = 2.0
    polled = client.get(f"/api/v1/tasks/{task_id}")
    assert polled.status_code == 200, polled.text
    assert polled.json()["status"] == "success"
    org = client.get("/api/v1/org").json()
    assert org["balance"] == "98.00"
    assert org["tariff"]["id"] == expensive["id"]


def test_upload_over_tariff_max_bytes_is_payload_too_large(client):
    setup_admin(client)
    tiny = create_tariff(client, name="Tiny", max_upload_bytes=32)
    logout(client)
    assert signup(client, "big@example.com", "bigpass12", tiny["id"]).status_code == 200
    response = upload_audio(client, data=b"x" * 200)
    assert response.status_code == 413
    assert err_code(response) == "payload_too_large"


def test_upload_capped_by_min_of_tariff_and_one_gib(client):
    setup_admin(client)
    tiny = create_tariff(client, name="Tiny", max_upload_bytes=16)
    logout(client)
    assert signup(client, "cap@example.com", "cappass12", tiny["id"]).status_code == 200
    response = upload_audio(client, data=b"y" * 64)
    assert response.status_code == 413
    assert err_code(response) == "payload_too_large"


def test_invalid_suffix_rejected(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "txt@example.com", "txtpass12", tariff_id).status_code == 200
    response = upload_audio(client, name="notes.txt", data=b"hello")
    assert response.status_code == 400
    assert err_code(response) == "invalid_file"


def test_archive_and_delete_tariff_rules(client):
    setup_admin(client)
    default_id = default_tariff_id(client)
    extra = create_tariff(client, name="Spare")
    logout(client)
    assert signup(client, "keep@example.com", "keeppass1", default_id).status_code == 200
    assert client.get("/api/v1/org").status_code == 200
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    archived = client.post(f"/api/v1/tariffs/{default_id}/archive")
    assert archived.status_code == 200, archived.text
    signup_list = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    assert all(item["id"] != default_id for item in signup_list)

    in_use = client.delete(f"/api/v1/tariffs/{default_id}")
    assert in_use.status_code == 409
    assert err_code(in_use) == "tariff_in_use"

    logout(client)
    login(client, "keep@example.com", "keeppass1")
    still = client.get("/api/v1/org")
    assert still.status_code == 200, still.text
    assert still.json()["tariff"]["id"] == default_id
    assert upload_audio(client, name="still.wav").status_code == 200

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.delete(f"/api/v1/tariffs/{extra['id']}").status_code == 200
    last = client.delete(f"/api/v1/tariffs/{default_id}")
    assert last.status_code == 409
    assert err_code(last) == "last_tariff"

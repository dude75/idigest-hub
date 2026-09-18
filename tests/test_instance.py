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
    wait_task,
)


def test_instance_smtp_test_endpoints(client, monkeypatch):
    setup_admin(client)

    missing = client.post("/api/v1/instance/smtp/test-connection", json={})
    assert missing.status_code == 400
    assert err_code(missing) == "validation_error"

    client.patch(
        "/api/v1/instance/settings",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "mailer",
            "smtp_from": "noreply@example.com",
            "smtp_tls": True,
        },
    )

    monkeypatch.setattr("app.services.mail.check_smtp_connection", lambda *_args, **_kwargs: None)
    ok = client.post(
        "/api/v1/instance/smtp/test-connection",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "mailer",
            "smtp_from": "noreply@example.com",
            "smtp_tls": True,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "ok"

    def _fail(*_args, **_kwargs):
        import smtplib

        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr("app.services.mail.check_smtp_connection", _fail)
    failed = client.post("/api/v1/instance/smtp/test-connection", json={})
    assert failed.status_code == 400, failed.text
    assert err_code(failed) == "validation_error"
    assert "535" in failed.json()["error"]["message"]

    sent_to: list[str] = []

    def _send(params, to_email, subject, body):
        sent_to.append(to_email)

    monkeypatch.setattr("app.services.mail.send_smtp_message", _send)
    sent = client.post("/api/v1/instance/smtp/test-send", json={})
    assert sent.status_code == 200, sent.text
    assert sent.json()["to"] == ADMIN_EMAIL
    assert sent_to == [ADMIN_EMAIL]

    custom = client.post(
        "/api/v1/instance/smtp/test-send",
        json={"to": "ops@example.com"},
    )
    assert custom.status_code == 200, custom.text
    assert custom.json()["to"] == "ops@example.com"
    assert sent_to[-1] == "ops@example.com"


def test_instance_smtp_test_forbidden_for_non_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "member@example.com", "memberpass", tariff_id).status_code == 200
    response = client.post("/api/v1/instance/smtp/test-connection", json={})
    assert response.status_code == 403
    assert err_code(response) == "forbidden"


def test_instance_stats_includes_download_proxy_status(client, monkeypatch):
    from app.services.download_proxy_health import reset_download_proxy_health_cache

    reset_download_proxy_health_cache()
    setup_admin(client)
    empty = client.get("/api/v1/instance/stats")
    assert empty.status_code == 200, empty.text
    assert empty.json()["download_proxy_status"] == "na"

    client.patch(
        "/api/v1/instance/settings",
        json={"download_proxy_url": "socks5://127.0.0.1:1"},
    )
    monkeypatch.setattr(
        "app.services.download_proxy_health.check_download_proxy_available",
        lambda *_args, **_kwargs: False,
    )
    reset_download_proxy_health_cache()
    down = client.get("/api/v1/instance/stats")
    assert down.status_code == 200, down.text
    assert down.json()["download_proxy_status"] == "down"

    monkeypatch.setattr(
        "app.services.download_proxy_health.check_download_proxy_available",
        lambda *_args, **_kwargs: True,
    )
    reset_download_proxy_health_cache()
    up = client.get("/api/v1/instance/stats")
    assert up.status_code == 200, up.text
    assert up.json()["download_proxy_status"] == "up"


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
    wait_task(client, first.json()["task_id"], status="success")

    fake_workers.audio_duration_sec = 25.0
    second = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert second.status_code == 202, second.text
    second_body = wait_task(client, second.json()["task_id"], status="success")

    fake_workers.transcribe_mode = "error"
    failed = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert failed.status_code == 202, failed.text
    wait_task(client, failed.json()["task_id"], status="error")

    fake_workers.summarize_mode = "success"
    summary = client.post(
        "/api/v1/tasks/summarize",
        json={"transcript_id": second_body["transcript_id"], "skill_ids": [skill.json()["id"]]},
    )
    assert summary.status_code == 202, summary.text
    wait_task(client, summary.json()["task_id"], status="success")

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
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": audio.json()["id"]})
    assert created.status_code == 202, created.text
    wait_task(client, created.json()["task_id"], status="success")

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


def test_instance_admin_can_create_org(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)

    created = client.post(
        "/api/v1/orgs",
        json={
            "name": "Acme Corp",
            "tariff_id": tariff_id,
            "admin_email": "acme@example.com",
            "admin_password": "acmepass1",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Acme Corp"
    assert body["is_personal"] is False
    assert len(body["members"]) == 1
    assert body["members"][0]["email"] == "acme@example.com"
    assert body["members"][0]["role"] == "org_admin"

    orgs = client.get("/api/v1/orgs")
    assert orgs.status_code == 200, orgs.text
    assert any(item["id"] == body["id"] for item in orgs.json()["items"])

    dup = client.post(
        "/api/v1/orgs",
        json={
            "name": "Other Corp",
            "tariff_id": tariff_id,
            "admin_email": "acme@example.com",
            "admin_password": "otherpass1",
        },
    )
    assert dup.status_code == 409
    assert err_code(dup) == "email_taken"

    logout(client)
    assert login(client, "acme@example.com", "acmepass1").status_code == 200
    assert me(client)["must_change_password"] is True


def test_instance_create_org_forbidden_for_non_admin(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "member@example.com", "memberpass", tariff_id).status_code == 200

    response = client.post(
        "/api/v1/orgs",
        json={
            "name": "Blocked Corp",
            "tariff_id": tariff_id,
            "admin_email": "blocked@example.com",
            "admin_password": "blockedp1",
        },
    )
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


def test_instance_admin_can_reset_org_admin_password(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "lead@example.com", "leadpass1", tariff_id).status_code == 200
    org_id = me(client)["org"]["id"]
    lead_id = me(client)["user"]["id"]
    created = client.post(
        "/api/v1/org/users",
        json={"email": "member@example.com", "password": "memberpass", "role": "org_member"},
    )
    assert created.status_code == 200, created.text
    member_id = created.json()["id"]

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    reset = client.post(f"/api/v1/orgs/{org_id}/users/{lead_id}/reset-password")
    assert reset.status_code == 200, reset.text
    temp = reset.json()["password"]
    assert len(temp) >= 8

    denied_member = client.post(f"/api/v1/orgs/{org_id}/users/{member_id}/reset-password")
    assert denied_member.status_code == 403
    assert err_code(denied_member) == "forbidden"

    logout(client)
    old_login = client.post("/api/v1/auth/login", json={"email": "lead@example.com", "password": "leadpass1"})
    assert old_login.status_code == 401
    assert login(client, "lead@example.com", temp).status_code == 200
    assert me(client)["must_change_password"] is True


def test_instance_audit_lists_entries_with_filters(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "audit@example.com", "auditpass", tariff_id).status_code == 200
    user_id = me(client)["user"]["id"]
    logout(client)

    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    start = client.post("/api/v1/impersonate", json={"user_id": user_id})
    assert start.status_code == 200, start.text
    stop = client.delete("/api/v1/impersonate")
    assert stop.status_code == 200, stop.text

    audit = client.get("/api/v1/instance/audit")
    assert audit.status_code == 200, audit.text
    body = audit.json()
    assert "total" in body
    actions = {item["action"] for item in body["items"]}
    assert "impersonate.start" in actions
    assert "impersonate.stop" in actions
    assert all("actor_email" in item for item in body["items"])
    assert body["total"] >= len(body["items"])

    filtered = client.get("/api/v1/instance/audit", params={"action": "impersonate.start"})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["items"]
    assert all(item["action"] == "impersonate.start" for item in filtered.json()["items"])

    paged = client.get("/api/v1/instance/audit", params={"limit": 1, "offset": 0})
    assert paged.status_code == 200, paged.text
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] >= 1

    export = client.get("/api/v1/instance/audit/export")
    assert export.status_code == 200, export.text
    assert export.headers["content-type"].startswith("text/csv")
    assert "impersonate.start" in export.text
    assert export.headers.get("content-disposition", "").endswith(".csv\"")

    filtered_export = client.get(
        "/api/v1/instance/audit/export",
        params={"action": "impersonate.start"},
    )
    assert filtered_export.status_code == 200, filtered_export.text
    assert "impersonate.start" in filtered_export.text
    assert "impersonate.stop" not in filtered_export.text

    logout(client)
    login(client, "audit@example.com", "auditpass")
    denied = client.get("/api/v1/instance/audit")
    assert denied.status_code == 403
    denied_export = client.get("/api/v1/instance/audit/export")
    assert denied_export.status_code == 403

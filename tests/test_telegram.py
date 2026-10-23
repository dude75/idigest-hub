"""Telegram link API and webhook security."""

from __future__ import annotations

from tests.conftest import err_code, login_ready, setup_admin, signup  # noqa: F401


def test_telegram_link_flow(client):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "telegram_bot_token": "123456:TEST",
            "telegram_enabled": True,
        },
    )
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings

    get_engine()
    with SessionLocal() as db:
        get_instance_settings(db).telegram_bot_username = "idigest_test_bot"
        db.commit()
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tguser@example.com", "tguserpass12", tariff_id).status_code == 200
    login_ready(client, "tguser@example.com", "tguserpass12")

    status = client.get("/api/v1/me/telegram")
    assert status.status_code == 200
    assert status.json()["linked"] is False
    assert status.json()["bot_enabled"] is True
    assert status.json()["bot_username"] == "idigest_test_bot"
    assert status.json()["bot_url"] == "https://t.me/idigest_test_bot"

    link = client.post("/api/v1/me/telegram/link")
    assert link.status_code == 200
    code = link.json()["code"]
    assert len(code) == 8

    from app.db import SessionLocal, get_engine
    from app.services.telegram_links import consume_link_code

    get_engine()
    assert SessionLocal is not None
    with SessionLocal() as db:
        user = consume_link_code(db, code=code, telegram_user_id="999001", chat_id="1001")
        db.commit()
        assert user.email == "tguser@example.com"

    status2 = client.get("/api/v1/me/telegram")
    assert status2.json()["linked"] is True

    unlink = client.delete("/api/v1/me/telegram")
    assert unlink.status_code == 200
    assert client.get("/api/v1/me/telegram").json()["linked"] is False


async def _noop_send(*_args, **_kwargs):
    return {}


def test_telegram_webhook_rejects_bad_secret(client, monkeypatch):
    monkeypatch.setattr("app.services.telegram_bot.send_message", _noop_send)
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": "123456:TEST", "telegram_enabled": True},
    )
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings

    get_engine()
    with SessionLocal() as db:
        secret = get_instance_settings(db).telegram_webhook_secret
    assert secret
    bad = client.post(
        "/api/v1/integrations/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert bad.status_code == 403
    ok = client.post(
        "/api/v1/integrations/telegram/webhook",
        json={"update_id": 1, "message": {"message_id": 1, "chat": {"id": 1}, "from": {"id": 2}, "text": "/help"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"


def test_telegram_link_requires_bot_enabled(client):
    setup_admin(client)
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    signup(client, "tg2@example.com", "tg2pass1234", tariff_id)
    login_ready(client, "tg2@example.com", "tg2pass1234")
    resp = client.post("/api/v1/me/telegram/link")
    assert resp.status_code == 400
    assert err_code(resp) == "validation_error"

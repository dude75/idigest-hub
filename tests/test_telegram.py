"""Telegram link API and webhook security."""

from __future__ import annotations

from tests.conftest import err_code, login_ready, setup_admin, signup  # noqa: F401


def test_instance_admin_without_org_cannot_use_me_telegram(client):
    setup_admin(client)
    denied = client.get("/api/v1/me/telegram")
    assert denied.status_code == 403
    assert err_code(denied) == "forbidden"


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


def test_telegram_notify_meta_propagation():
    from app.services.telegram_bot import telegram_notify_meta

    assert telegram_notify_meta({}) == {}
    assert telegram_notify_meta({"notify_telegram": True}) == {}
    assert telegram_notify_meta({"notify_telegram": True, "telegram_chat_id": "42"}) == {
        "notify_telegram": True,
        "telegram_chat_id": "42",
    }


def test_telegram_bot_menu_commands():
    from app.services.telegram_commands import BOT_MENU_COMMANDS

    names = [row["command"] for row in BOT_MENU_COMMANDS]
    assert "transcribe" in names
    assert "summary" in names


def test_telegram_parse_command():
    from app.services.telegram_bot import _parse_command

    assert _parse_command("/transcribe@mybot abc") == ("/transcribe", ["abc"])
    assert _parse_command("/summary") == ("/summary", [])


async def test_telegram_cmd_transcribe_queues(client, monkeypatch):
    monkeypatch.setattr("app.services.telegram_bot.send_message", _noop_send)
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": "123456:TEST", "telegram_enabled": True},
    )
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    signup(client, "tgtr@example.com", "tgtrpass1234", tariff_id)
    login_ready(client, "tgtr@example.com", "tgtrpass1234")
    link = client.post("/api/v1/me/telegram/link").json()
    from sqlalchemy import select

    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings, load_org_bundle
    from app.models import Audio, Task, User, new_id
    from app.services.telegram_bot import handle_update
    from app.services.telegram_links import consume_link_code
    from app.timeutil import utcnow

    get_engine()
    with SessionLocal() as db:
        consume_link_code(db, code=link["code"], telegram_user_id="888", chat_id="2000")
        user = db.scalars(select(User).where(User.email == "tgtr@example.com")).one()
        org, _ = load_org_bundle(db, user)
        audio = Audio(
            id=new_id(),
            org_id=org.id,
            owner_user_id=user.id,
            storage_path="test/fake.ogg",
            original_filename="fake.ogg",
            created_at=utcnow(),
        )
        db.add(audio)
        db.commit()
        audio_id = audio.id

    class _FakeStorage:
        def exists(self, _path: str) -> bool:
            return True

    monkeypatch.setattr("app.services.storage.get_storage", lambda: _FakeStorage())
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        await handle_update(
            db,
            {
                "message": {
                    "chat": {"id": 2000},
                    "from": {"id": 888},
                    "text": f"/transcribe {audio_id}",
                }
            },
            token="123456:TEST",
            settings=settings,
            bot_username=None,
        )
        db.commit()
        task = db.scalars(select(Task).where(Task.type == "transcribe").order_by(Task.created_at.desc())).first()
        assert task is not None
        assert task.audio_id == audio_id
        assert (task.meta_json or {}).get("notify_telegram") is True
        assert (task.meta_json or {}).get("telegram_chat_id") == "2000"


def test_telegram_link_requires_bot_enabled(client):
    setup_admin(client)
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    signup(client, "tg2@example.com", "tg2pass1234", tariff_id)
    login_ready(client, "tg2@example.com", "tg2pass1234")
    resp = client.post("/api/v1/me/telegram/link")
    assert resp.status_code == 400
    assert err_code(resp) == "validation_error"

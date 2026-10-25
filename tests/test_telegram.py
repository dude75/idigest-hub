"""Telegram link API and webhook security."""

from __future__ import annotations

from sqlalchemy import select

from app.models import TelegramLink
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, err_code, login, login_ready, logout, setup_admin, signup  # noqa: F401


def _mock_telegram_get_me(monkeypatch, *, bot_id: int, username: str) -> None:
    async def _me(*_args, **_kwargs):
        return {"id": bot_id, "username": username}

    monkeypatch.setattr("app.services.telegram_identity.get_me", _me)


def _enable_telegram(client, token: str = "123456:TEST") -> None:
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": token, "telegram_enabled": True},
    )


def test_instance_admin_without_org_cannot_use_me_telegram(client):
    setup_admin(client)
    denied = client.get("/api/v1/me/telegram")
    assert denied.status_code == 403
    assert err_code(denied) == "forbidden"


def test_me_telegram_resolves_missing_bot_username(client, monkeypatch):
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
        get_instance_settings(db).telegram_bot_username = None
        db.commit()

    async def _me(*_args, **_kwargs):
        return {"username": "idigest_test_bot"}

    monkeypatch.setattr("app.services.telegram_identity.get_me", _me)

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tgresolve@example.com", "tgresolvepass1", tariff_id).status_code == 200
    login_ready(client, "tgresolve@example.com", "tgresolvepass1")

    status = client.get("/api/v1/me/telegram")
    assert status.status_code == 200
    assert status.json()["bot_username"] == "idigest_test_bot"
    assert status.json()["bot_url"] == "https://t.me/idigest_test_bot"

    link = client.post("/api/v1/me/telegram/link")
    assert link.status_code == 200
    assert link.json()["bot_username"] == "idigest_test_bot"


def test_me_telegram_refreshes_stale_bot_username(client, monkeypatch):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": "123456:TEST", "telegram_enabled": True},
    )
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "stale_bot"
        settings.telegram_bot_id = 100
        db.commit()

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tgfresh@example.com", "tgfreshpass12", tariff_id).status_code == 200
    login_ready(client, "tgfresh@example.com", "tgfreshpass12")

    calls = 0

    async def _me(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {"id": 200, "username": "new_audio_bot"}

    monkeypatch.setattr("app.services.telegram_identity.get_me", _me)
    body = client.get("/api/v1/me/telegram").json()
    assert calls >= 1
    assert body["bot_username"] == "new_audio_bot"
    assert body["bot_instance_id"] == 200
    assert body["bot_url"] == "https://t.me/new_audio_bot"


def test_me_telegram_invalidates_link_without_instance_bot_id(client, monkeypatch):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": "123456:TEST", "telegram_enabled": True},
    )
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings
    from app.services.telegram_links import consume_link_code

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "idigest_test_bot"
        settings.telegram_bot_id = 100
        db.commit()

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tglegacy@example.com", "tglegacypass1", tariff_id).status_code == 200
    login_ready(client, "tglegacy@example.com", "tglegacypass1")
    code = client.post("/api/v1/me/telegram/link").json()["code"]
    with SessionLocal() as db:
        consume_link_code(db, code=code, telegram_user_id="888001", chat_id="8001")
        db.commit()
    assert client.get("/api/v1/me/telegram").json()["linked"] is True

    with SessionLocal() as db:
        link = db.execute(
            __import__("sqlalchemy").select(__import__("app.models", fromlist=["TelegramLink"]).TelegramLink)
        ).scalar_one()
        link.instance_bot_id = None
        db.commit()

    async def _me(*_args, **_kwargs):
        return {"id": 100, "username": "idigest_test_bot"}

    monkeypatch.setattr("app.services.telegram_identity.get_me", _me)
    assert client.get("/api/v1/me/telegram").json()["linked"] is False


def test_me_telegram_wrong_instance_bot_id_shows_unlinked(client, monkeypatch):
    """Привязка к bot_id=100 не считается валидной, когда инстанс уже на bot_id=200."""
    setup_admin(client)
    _enable_telegram(client)
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings
    from app.services.telegram_links import consume_link_code

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "bot_a"
        settings.telegram_bot_id = 100
        db.commit()

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tgwrongid@example.com", "tgwrongidpass", tariff_id).status_code == 200
    login_ready(client, "tgwrongid@example.com", "tgwrongidpass")
    code = client.post("/api/v1/me/telegram/link").json()["code"]
    with SessionLocal() as db:
        consume_link_code(db, code=code, telegram_user_id="888002", chat_id="8002")
        db.commit()

    with SessionLocal() as db:
        row = db.scalar(select(TelegramLink).where(TelegramLink.telegram_user_id == "888002"))
        assert row is not None
        row.instance_bot_id = 100
        settings = get_instance_settings(db)
        settings.telegram_bot_id = 200
        settings.telegram_bot_username = "bot_b"
        db.commit()

    _mock_telegram_get_me(monkeypatch, bot_id=200, username="bot_b")
    body = client.get("/api/v1/me/telegram").json()
    assert body["linked"] is False
    assert body["bot_instance_id"] == 200
    assert body["bot_username"] == "bot_b"


def test_me_telegram_bot_swap_user_relinks_with_new_instance_bot_id(client, monkeypatch):
    """Смена бота админом: сброс привязки, новое имя в API, повторная привязка с новым instance_bot_id."""
    setup_admin(client)
    _enable_telegram(client, token="123456:OLDBOT")
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings
    from app.services.telegram_links import consume_link_code

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "old_audio"
        settings.telegram_bot_id = 100
        db.commit()

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tgswap@example.com", "tgswappass12", tariff_id).status_code == 200
    login_ready(client, "tgswap@example.com", "tgswappass12")
    code_a = client.post("/api/v1/me/telegram/link").json()["code"]
    with SessionLocal() as db:
        consume_link_code(db, code=code_a, telegram_user_id="999100", chat_id="9100")
        db.commit()
    assert client.get("/api/v1/me/telegram").json()["linked"] is True

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    _mock_telegram_get_me(monkeypatch, bot_id=200, username="new_audio")
    client.patch("/api/v1/instance/settings", json={"telegram_bot_token": "789012:NEWBOT"})

    logout(client)
    login_ready(client, "tgswap@example.com", "tgswappass12")
    status = client.get("/api/v1/me/telegram").json()
    assert status["linked"] is False
    assert status["bot_username"] == "new_audio"
    assert status["bot_instance_id"] == 200

    link = client.post("/api/v1/me/telegram/link").json()
    assert link["bot_username"] == "new_audio"
    with SessionLocal() as db:
        consume_link_code(db, code=link["code"], telegram_user_id="999100", chat_id="9100")
        db.commit()
        row = db.scalar(select(TelegramLink).where(TelegramLink.telegram_user_id == "999100"))
        assert row is not None
        assert row.instance_bot_id == 200
    assert client.get("/api/v1/me/telegram").json()["linked"] is True


def test_me_telegram_link_fresh_username_when_db_stale(client, monkeypatch):
    """POST /me/telegram/link отдаёт имя с getMe, а не устаревший кэш в БД."""
    setup_admin(client)
    _enable_telegram(client)
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "cached_old_name"
        settings.telegram_bot_id = 200
        db.commit()

    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    assert signup(client, "tglinkfresh@example.com", "tglinkfreshpass", tariff_id).status_code == 200
    login_ready(client, "tglinkfresh@example.com", "tglinkfreshpass")

    _mock_telegram_get_me(monkeypatch, bot_id=200, username="live_from_api")
    link = client.post("/api/v1/me/telegram/link").json()
    assert link["bot_username"] == "live_from_api"
    assert link["bot_url"] == "https://t.me/live_from_api"


def test_token_patch_clears_bot_identity_then_refresh(client, monkeypatch):
    """Сохранение нового токена сбрасывает id/username до getMe на том же запросе."""
    setup_admin(client)
    _enable_telegram(client, token="123456:FIRST")
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings

    get_engine()
    with SessionLocal() as db:
        settings = get_instance_settings(db)
        settings.telegram_bot_username = "before"
        settings.telegram_bot_id = 100
        db.commit()

    _mock_telegram_get_me(monkeypatch, bot_id=200, username="after_save")
    client.patch("/api/v1/instance/settings", json={"telegram_bot_token": "789012:SECOND"})

    with SessionLocal() as db:
        settings = get_instance_settings(db)
        assert settings.telegram_bot_id == 200
        assert settings.telegram_bot_username == "after_save"


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


def test_notify_task_terminal_uses_hub_loop(client, monkeypatch):
    import asyncio

    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings
    from app.models import Task, new_id
    from app.services.telegram_bot import notify_task_terminal, register_hub_event_loop
    from app.timeutil import utcnow

    loop = asyncio.new_event_loop()
    register_hub_event_loop(loop)
    scheduled: list = []

    def _fake_threadsafe(coro, target_loop):
        scheduled.append(coro)
        coro.close()

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _fake_threadsafe)
    monkeypatch.setattr("app.services.telegram_runtime.schedule_telegram_reconfigure", lambda: None)
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"telegram_bot_token": "123456:TEST", "telegram_enabled": True},
    )
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    signup(client, "tgnotify@example.com", "tgnotifypass12", tariff_id)
    get_engine()
    with SessionLocal() as db:
        from sqlalchemy import select

        from app.models import User

        from app.deps import load_org_bundle

        user = db.scalars(select(User).where(User.email == "tgnotify@example.com")).one()
        org, _ = load_org_bundle(db, user)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="import",
            status="success",
            org_id=org.id,
            user_id=user.id,
            meta_json={"notify_telegram": True, "telegram_chat_id": "12345"},
            queued_at=now,
            created_at=now,
            updated_at=now,
            snap_unlimited=org.tariff.unlimited,
            snap_price_per_audio_sec=org.tariff.price_per_audio_sec,
            snap_price_per_1k_summary_chars=org.tariff.price_per_1k_summary_chars,
            snap_max_upload_bytes=org.tariff.max_upload_bytes,
        )
        db.add(task)
        db.flush()
        notify_task_terminal(db, task)
    assert len(scheduled) == 1
    loop.close()


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
    assert "skills" not in names
    assert "make_transcribe" in names
    assert "make_summary" in names
    assert "view_summary" in names


def test_telegram_parse_command():
    from app.services.telegram_bot import _parse_command

    assert _parse_command("/make_transcribe@mybot abc") == ("/make_transcribe", ["abc"])
    assert _parse_command("/make_summary") == ("/make_summary", [])


def test_merge_task_meta_keeps_telegram_notify():
    from app.models import Task, new_id
    from app.services.dispatcher import _merge_task_meta
    from app.timeutil import utcnow

    now = utcnow()
    task = Task(
        id=new_id(),
        type="transcribe",
        status="queued",
        org_id="org",
        user_id="user",
        meta_json={"notify_telegram": True, "telegram_chat_id": "99"},
        queued_at=now,
        created_at=now,
        updated_at=now,
        snap_unlimited=True,
        snap_price_per_audio_sec=0,
        snap_price_per_1k_summary_chars=0,
        snap_max_upload_bytes=1,
    )
    _merge_task_meta(task, stage="running")
    assert task.meta_json["notify_telegram"] is True
    assert task.meta_json["telegram_chat_id"] == "99"
    assert task.meta_json["stage"] == "running"


def test_telegram_display_names(client):
    from app.db import SessionLocal, get_engine
    from app.models import Audio, Transcript, new_id
    from app.services.telegram_bot import _audio_display_name, _transcript_display_name
    from app.timeutil import utcnow

    setup_admin(client)
    tariff_id = client.get("/api/v1/tariffs").json()["items"][0]["id"]
    signup(client, "tgname@example.com", "tgnamepass12", tariff_id)
    get_engine()
    with SessionLocal() as db:
        from sqlalchemy import select

        from app.deps import load_org_bundle
        from app.models import User

        user = db.scalars(select(User).where(User.email == "tgname@example.com")).one()
        org, _ = load_org_bundle(db, user)
        now = utcnow()
        audio = Audio(
            id=new_id(),
            org_id=org.id,
            owner_user_id=user.id,
            storage_path="x/y",
            original_filename="My Podcast Episode.mp3",
            created_at=now,
        )
        db.add(audio)
        tr = Transcript(
            id=new_id(),
            org_id=org.id,
            owner_user_id=user.id,
            source_audio_id=audio.id,
            title="Meeting notes",
            utterances_encrypted="enc",
            created_at=now,
        )
        db.add(tr)
        db.commit()
        assert _audio_display_name(db, audio.id) == "My Podcast Episode.mp3"
        assert _transcript_display_name(db, tr.id) == "Meeting notes"


def test_skill_inline_keyboard_callback_data():
    from app.models import Skill
    from app.services.telegram_bot import _SKILL_CALLBACK_PREFIX, _skill_inline_keyboard

    skill = Skill(id="a" * 36, name="Minutes", body="x", scope="base", org_id=None, owner_user_id="u")
    markup = _skill_inline_keyboard([skill])
    assert markup["inline_keyboard"][0][0]["callback_data"] == f"{_SKILL_CALLBACK_PREFIX}{skill.id}"


async def test_configure_skips_webhook_when_disabled(client, monkeypatch):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "public_base_url": "https://hub.example.com",
            "telegram_bot_token": "123456:TEST",
            "telegram_enabled": True,
            "telegram_use_webhook": False,
        },
    )
    calls: list[str] = []

    async def _set_webhook(*_args, **_kwargs):
        calls.append("set")
        return None

    async def _delete_webhook(*_args, **_kwargs):
        calls.append("delete")
        return None

    async def _username(_settings, _db):
        return "test_bot"

    async def _set_cmds(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.telegram_runtime.set_webhook", _set_webhook)
    monkeypatch.setattr("app.services.telegram_runtime.delete_webhook", _delete_webhook)
    monkeypatch.setattr("app.services.telegram_identity.fetch_bot_username", _username)
    monkeypatch.setattr("app.services.telegram_runtime.set_my_commands", _set_cmds)

    from app.services.telegram_runtime import configure_telegram_transport

    mode = await configure_telegram_transport(__import__("asyncio").Event())
    assert mode == "poll"
    assert calls == ["delete"]
    assert "set" not in calls


def test_view_summary_inline_keyboard_callback_data():
    from unittest.mock import MagicMock

    from app.models import Summary
    from app.services.telegram_bot import _VIEW_SUMMARY_CALLBACK_PREFIX, _view_summary_inline_keyboard
    from app.timeutil import utcnow

    summary = Summary(
        id="b" * 36,
        org_id="org",
        owner_user_id="u",
        source_transcript_id=None,
        skill_ids_json=[],
        title="Weekly notes",
        body_encrypted="enc",
        created_at=utcnow(),
    )
    db = MagicMock()
    db.get.return_value = summary
    markup = _view_summary_inline_keyboard([summary], db)
    assert markup["inline_keyboard"][0][0]["callback_data"] == f"{_VIEW_SUMMARY_CALLBACK_PREFIX}{summary.id}"


def test_transcribe_and_summary_inline_keyboard_callback_data():
    from unittest.mock import MagicMock

    from app.models import Audio, Transcript
    from app.services.telegram_bot import (
        _SUMMARY_TRANSCRIPT_CALLBACK_PREFIX,
        _TRANSCRIBE_AUDIO_CALLBACK_PREFIX,
        _audio_inline_keyboard,
        _transcript_inline_keyboard,
    )
    from app.timeutil import utcnow

    audio_id = "a" * 36
    transcript_id = "c" * 36
    audio = Audio(
        id=audio_id,
        org_id="org",
        owner_user_id="u",
        storage_path="x.ogg",
        original_filename="clip.ogg",
        created_at=utcnow(),
    )
    transcript = Transcript(
        id=transcript_id,
        org_id="org",
        owner_user_id="u",
        source_audio_id=None,
        title="Notes",
        utterances_encrypted="enc",
        created_at=utcnow(),
    )
    db = MagicMock()
    db.get.side_effect = lambda model, pk: audio if pk == audio_id else transcript if pk == transcript_id else None
    audio_markup = _audio_inline_keyboard([audio], db)
    assert audio_markup["inline_keyboard"][0][0]["callback_data"] == f"{_TRANSCRIBE_AUDIO_CALLBACK_PREFIX}{audio_id}"
    transcript_markup = _transcript_inline_keyboard([transcript], db)
    assert (
        transcript_markup["inline_keyboard"][0][0]["callback_data"]
        == f"{_SUMMARY_TRANSCRIPT_CALLBACK_PREFIX}{transcript_id}"
    )


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
                    "text": f"/make_transcribe {audio_id}",
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

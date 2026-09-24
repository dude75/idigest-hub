"""MCP library payloads (OAuth scope + CRUD alignment with REST)."""

from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import select

from app.deps import AuthContext, load_org_bundle
from app.models import User
from app.services.mcp_library import (
    create_audio_import_payload,
    create_audio_upload_payload,
    create_skill_payload,
    create_summary_payload,
    create_transcribe_payload,
    delete_audio_payload,
    delete_skill_payload,
    delete_summary_payload,
    get_audio_payload,
    get_skill_payload,
    get_summary_payload,
    get_task_payload,
    get_transcript_payload,
    list_audios_payload,
    list_transcripts_payload,
    stop_capture_task_payload,
    update_summary_payload,
    update_transcript_payload,
)
from app.services.oauth_scopes import (
    SCOPE_AUDIO_READ,
    SCOPE_AUDIO_WRITE,
    SCOPE_SKILLS_READ,
    SCOPE_SKILLS_WRITE,
    SCOPE_SUMMARIES_READ,
    SCOPE_SUMMARIES_WRITE,
    SCOPE_TASKS_WRITE,
    SCOPE_TRANSCRIPTS_READ,
    SCOPE_TRANSCRIPTS_WRITE,
)
from tests.conftest import (
    SAMPLE_WAV_BYTES,
    add_worker,
    default_tariff_id,
    login,
    login_ready,
    logout,
    open_db,
    seed_node_health,
    setup_admin,
    signup,
    upload_audio,
)


def _oauth_ctx(db, user: User, scopes: frozenset[str]) -> AuthContext:
    org, membership = load_org_bundle(db, user)
    return AuthContext(
        user=user,
        actor=user,
        org=org,
        membership=membership,
        session=None,
        via_api_token=False,
        locale=user.locale or "en",
        impersonating=False,
        via_oauth_token=True,
        oauth_scopes=scopes,
    )


def _session_ctx(db, user: User) -> AuthContext:
    org, membership = load_org_bundle(db, user)
    return AuthContext(
        user=user,
        actor=user,
        org=org,
        membership=membership,
        session=None,
        via_api_token=False,
        locale=user.locale or "en",
        impersonating=False,
        via_oauth_token=False,
        oauth_scopes=frozenset(),
    )


def _user(db, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _insert_transcript_and_summary(org_id: str, user_id: str, *, title: str = "Meet") -> tuple[str, str]:
    from app.crypto import encrypt_str
    from app.models import Summary, Transcript, new_id
    from app.timeutil import utcnow

    db = open_db()
    try:
        now = utcnow()
        transcript_id = new_id()
        summary_id = new_id()
        db.add(
            Transcript(
                id=transcript_id,
                org_id=org_id,
                owner_user_id=user_id,
                title=title,
                utterances_encrypted=encrypt_str(
                    json.dumps([{"speaker": "A", "start": 0, "end": 1, "text": "hi"}]),
                    db,
                ),
                created_at=now,
            )
        )
        db.flush()
        db.add(
            Summary(
                id=summary_id,
                org_id=org_id,
                owner_user_id=user_id,
                source_transcript_id=transcript_id,
                skill_ids_json=[],
                body_encrypted=encrypt_str("original body", db),
                created_at=now,
            )
        )
        db.commit()
        return transcript_id, summary_id
    finally:
        db.close()


def test_mcp_oauth_scopes_optional_for_session_context(client):
    setup_admin(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "mcp-sess@example.com", "mcppass99", tariffs[0]["id"])

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-sess@example.com")
        ctx = _session_ctx(db, user)
        assert list_audios_payload(db, ctx)["items"] == []


def test_mcp_skill_crud_requires_scopes(client):
    setup_admin(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "mcp@example.com", "mcppass12", tariffs[0]["id"])

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp@example.com")
        ctx = _oauth_ctx(db, user, frozenset({SCOPE_SKILLS_WRITE}))

        with pytest.raises(PermissionError, match="skills:read"):
            get_skill_payload(db, ctx, "missing")

        created = create_skill_payload(db, ctx, name="Notes", body="Summarize notes")
        db.commit()
        skill_id = created["id"]

        ctx_read = _oauth_ctx(db, user, frozenset({SCOPE_SKILLS_READ}))
        fetched = get_skill_payload(db, ctx_read, skill_id)
        assert fetched["name"] == "Notes"
        assert fetched["body"] == "Summarize notes"

        delete_skill_payload(db, ctx, skill_id)
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            get_skill_payload(db, ctx_read, skill_id)


def test_mcp_audio_upload_get_list_delete(client):
    setup_admin(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "mcp-audio@example.com", "mcppass32", tariffs[0]["id"])

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-audio@example.com")
        ctx_write = _oauth_ctx(db, user, frozenset({SCOPE_AUDIO_WRITE}))
        created = create_audio_upload_payload(
            db,
            ctx_write,
            filename="clip.wav",
            content_base64=base64.b64encode(SAMPLE_WAV_BYTES).decode("ascii"),
        )
        db.commit()
        audio_id = created["id"]

        ctx_read = _oauth_ctx(db, user, frozenset({SCOPE_AUDIO_READ}))
        listed = list_audios_payload(db, ctx_read)
        assert any(item["id"] == audio_id for item in listed["items"])

        detail = get_audio_payload(db, ctx_read, audio_id)
        assert detail["filename"] == "clip.wav"
        assert detail["can_transcribe"] is True

        delete_audio_payload(db, ctx_write, audio_id)
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            get_audio_payload(db, ctx_read, audio_id)


def test_mcp_create_transcribe_queues_task(client):
    setup_admin(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "mcp-tr@example.com", "mcppass33", tariffs[0]["id"])

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-tr@example.com")
        ctx_write = _oauth_ctx(db, user, frozenset({SCOPE_AUDIO_WRITE, SCOPE_TASKS_WRITE}))
        created = create_audio_upload_payload(
            db,
            ctx_write,
            filename="meet.wav",
            content_base64=base64.b64encode(SAMPLE_WAV_BYTES).decode("ascii"),
        )
        db.commit()
        audio_id = created["id"]

        task = create_transcribe_payload(db, ctx_write, audio_id=audio_id)
        assert task["type"] == "transcribe"
        assert task["status"] == "queued"
        assert task["audio_id"] == audio_id


def test_mcp_audio_delete_forbidden_for_org_member(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-lead@example.com", "leadpass12", tariff_id)
    login_ready(client, "mcp-lead@example.com", "leadpass12")
    audio = upload_audio(client)
    assert audio.status_code == 200, audio.text
    audio_id = audio.json()["id"]

    member = client.post(
        "/api/v1/org/users",
        json={"email": "mcp-member@example.com", "password": "memberpass1", "role": "org_member"},
    )
    assert member.status_code == 200, member.text

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        member_user = _user(db, "mcp-member@example.com")
        ctx = _oauth_ctx(db, member_user, frozenset({SCOPE_AUDIO_WRITE}))
        with pytest.raises(PermissionError, match="forbidden"):
            delete_audio_payload(db, ctx, audio_id)


def test_mcp_get_task_scope_and_payload(client, monkeypatch):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-gettask@example.com", "gettaskpass1", tariff_id)

    def _allow_import_url(url: str, *, settings_allowed):
        return url.strip()

    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-gettask@example.com")
        ctx = _oauth_ctx(db, user, frozenset())
        with pytest.raises(PermissionError, match="tasks:write"):
            get_task_payload(db, ctx, task_id="missing")

        ctx_write = _oauth_ctx(db, user, frozenset({SCOPE_TASKS_WRITE}))
        created = create_audio_import_payload(
            db,
            ctx_write,
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.commit()
        task_id = created["task_id"]

        payload, schedule, refresh_health = get_task_payload(db, ctx_write, task_id=task_id)
        assert payload["task_id"] == task_id
        assert payload["type"] == "import"
        assert schedule is True
        assert refresh_health is False


@pytest.mark.asyncio
async def test_mcp_stop_capture_task(client, fake_workers):
    setup_admin(client)
    worker = add_worker(client, type="capture", name="cap-mcp", base_url="http://capture-mcp.test")
    seed_node_health(worker["id"])
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-capstop@example.com", "capstoppass1", tariff_id)

    import app.db as hub_db
    from app.deps import get_instance_settings
    from app.models import Task, new_id
    from app.services.billing import snapshot_fields
    from app.services.capture_runner import reset_capture_runner
    from app.timeutil import utcnow

    fake_workers.capture_stop_calls.clear()
    reset_capture_runner()

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-capstop@example.com")
        org, _ = load_org_bundle(db, user)
        assert org is not None
        settings = get_instance_settings(db)
        now = utcnow()
        task = Task(
            id=new_id(),
            type="capture",
            status="running",
            org_id=org.id,
            user_id=user.id,
            worker_id=worker["id"],
            worker_task_id=fake_workers.capture_worker_task_id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            meta_json={
                "meeting_url": "https://meet.example.com/room1",
                "stage": "capturing",
                "connector": "jitsi",
            },
            **snapshot_fields(org.tariff, settings.asr_model, settings.diarization_model),
        )
        db.add(task)
        db.commit()
        hub_task_id = task.id

        ctx = _oauth_ctx(db, user, frozenset({SCOPE_TASKS_WRITE}))
        result, need_tick = await stop_capture_task_payload(db, ctx, task_id=hub_task_id)
        db.commit()
        assert need_tick is True
        assert fake_workers.capture_worker_task_id in fake_workers.capture_stop_calls
        assert result["meta"]["stop_requested"] is True


def test_mcp_audio_import_enqueues_task(client, monkeypatch):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-import@example.com", "importpass1", tariff_id)

    def _allow_import_url(url: str, *, settings_allowed):
        return url.strip()

    monkeypatch.setattr("app.services.url_import.assert_import_fetch_allowed", _allow_import_url)

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-import@example.com")
        ctx = _oauth_ctx(db, user, frozenset({SCOPE_TASKS_WRITE}))
        task = create_audio_import_payload(
            db,
            ctx,
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.commit()
        assert task["type"] == "import"
        assert task["status"] == "queued"


def test_mcp_list_transcripts_scope(client):
    setup_admin(client)
    tariffs = client.get("/api/v1/auth/signup-tariffs").json()["items"]
    signup(client, "mcp2@example.com", "mcppass22", tariffs[0]["id"])

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp2@example.com")
        ctx = _oauth_ctx(db, user, frozenset())
        with pytest.raises(PermissionError, match="transcripts:read"):
            list_transcripts_payload(db, ctx)

        ctx_ok = _oauth_ctx(db, user, frozenset({SCOPE_TRANSCRIPTS_READ}))
        listed = list_transcripts_payload(db, ctx_ok)
        assert listed["items"] == []


def test_mcp_transcript_update(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-tr@example.com", "trpass1234", tariff_id)

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-tr@example.com")
        org, _ = load_org_bundle(db, user)
        assert org is not None
        transcript_id, _ = _insert_transcript_and_summary(org.id, user.id, title="Old")

        ctx = _oauth_ctx(db, user, frozenset({SCOPE_TRANSCRIPTS_WRITE}))
        updated = update_transcript_payload(db, ctx, transcript_id, title="New title")
        db.commit()
        assert updated["title"] == "New title"

        ctx_read = _oauth_ctx(db, user, frozenset({SCOPE_TRANSCRIPTS_READ}))
        fetched = get_transcript_payload(db, ctx_read, transcript_id)
        assert fetched["title"] == "New title"
        assert len(fetched["utterances"]) == 1


def test_mcp_summary_read_update_delete(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    signup(client, "mcp-sum@example.com", "sumpass1234", tariff_id)

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-sum@example.com")
        org, _ = load_org_bundle(db, user)
        assert org is not None
        _, summary_id = _insert_transcript_and_summary(org.id, user.id)

        ctx_read = _oauth_ctx(db, user, frozenset({SCOPE_SUMMARIES_READ}))
        with pytest.raises(PermissionError, match="summaries:read"):
            get_summary_payload(db, _oauth_ctx(db, user, frozenset()), summary_id)

        got = get_summary_payload(db, ctx_read, summary_id)
        assert got["body"] == "original body"

        ctx_write = _oauth_ctx(db, user, frozenset({SCOPE_SUMMARIES_WRITE}))
        patched = update_summary_payload(
            db,
            ctx_write,
            summary_id,
            title="Edited",
            body="new body",
        )
        db.commit()
        assert patched["title"] == "Edited"
        assert patched["body"] == "new body"
        assert patched["edited"] is True

        delete_summary_payload(db, ctx_write, summary_id)
        db.commit()
        with pytest.raises(ValueError, match="not found"):
            get_summary_payload(db, ctx_read, summary_id)


def test_mcp_create_summary_queues_task(client, fake_workers):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    worker = add_worker(client, type="summarize")
    seed_node_health(worker["id"])
    logout(client)
    signup(client, "mcp-csum@example.com", "csumpass12", tariff_id)

    import app.db as hub_db

    with hub_db.SessionLocal() as db:
        user = _user(db, "mcp-csum@example.com")
        org, _ = load_org_bundle(db, user)
        assert org is not None
        transcript_id, _ = _insert_transcript_and_summary(org.id, user.id)

        ctx_skill = _oauth_ctx(db, user, frozenset({SCOPE_SKILLS_WRITE}))
        skill = create_skill_payload(db, ctx_skill, name="Brief", body="Be brief")
        db.commit()

        ctx = _oauth_ctx(db, user, frozenset({SCOPE_TASKS_WRITE}))
        task = create_summary_payload(
            db,
            ctx,
            transcript_id=transcript_id,
            skill_ids=[skill["id"]],
        )
        db.commit()
        assert task["type"] == "summarize"
        assert task["status"] == "queued"
        assert task["source_transcript_id"] == transcript_id

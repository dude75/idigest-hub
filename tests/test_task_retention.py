from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import Task, Transcript, UsageEvent, new_id
from app.services.task_retention import purge_expired_task_history
from app.timeutil import utcnow
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    err_code,
    login,
    logout,
    me,
    open_db,
    setup_admin,
    signup,
    task_list_ids,
    upload_audio,
    wait_task,
)
from tests.test_tasks import _org_user_with_audio


def test_task_purge_forbidden_for_org_user(client, fake_workers):
    ctx = _org_user_with_audio(client, fake_workers, email="purge1@example.com")
    fake_workers.transcribe_mode = "success"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202
    wait_task(client, created.json()["task_id"], status="success")

    response = client.post("/api/v1/tasks/purge")
    assert response.status_code == 403
    assert err_code(response) == "forbidden"


def test_instance_admin_purge_keeps_artifacts_and_usage(client, fake_workers):
    ctx = _org_user_with_audio(client, fake_workers, email="purge2@example.com")
    fake_workers.transcribe_mode = "success"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    polled = wait_task(client, task_id, status="success")
    transcript_id = polled["transcript_id"]
    org_id = ctx["me"]["org"]["id"]
    user_id = ctx["me"]["user"]["id"]

    now = utcnow()
    usage_id = new_id()
    with open_db() as db:
        db.add(
            UsageEvent(
                id=usage_id,
                org_id=org_id,
                user_id=user_id,
                task_id=task_id,
                kind="transcribe",
                audio_sec=10.0,
                summary_chars=None,
                amount=Decimal("1.50"),
                unlimited_skip=False,
                created_at=now,
            )
        )
        db.commit()

    logout(client)
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    before = client.get("/api/v1/tasks")
    assert before.status_code == 200
    assert task_id in task_list_ids(before.json())

    purged = client.post(f"/api/v1/tasks/purge?org_id={org_id}&user_id={user_id}")
    assert purged.status_code == 200, purged.text
    assert purged.json()["deleted"] >= 1

    after = client.get("/api/v1/tasks")
    assert task_id not in task_list_ids(after.json())

    transcript = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert transcript.status_code == 200

    with open_db() as db:
        assert db.get(Task, task_id) is None
        assert db.get(Transcript, transcript_id) is not None
        event = db.get(UsageEvent, usage_id)
        assert event is not None
        assert event.task_id is None
        assert event.amount == Decimal("1.50")


def test_task_history_retention_days_setting(client):
    setup_admin(client)
    response = client.patch("/api/v1/instance/settings", json={"task_history_retention_days": 30})
    assert response.status_code == 200
    assert response.json()["task_history_retention_days"] == 30

    bad = client.patch("/api/v1/instance/settings", json={"task_history_retention_days": -1})
    assert bad.status_code == 400


def test_auto_purge_respects_ttl(client, fake_workers):
    ctx = _org_user_with_audio(client, fake_workers, email="purge3@example.com")
    fake_workers.transcribe_mode = "success"
    created = client.post("/api/v1/tasks/transcribe", json={"audio_id": ctx["audio"]["id"]})
    task_id = created.json()["task_id"]
    wait_task(client, task_id, status="success")

    old = utcnow() - timedelta(days=10)
    with open_db() as db:
        task = db.get(Task, task_id)
        task.updated_at = old
        db.commit()

    with open_db() as db:
        from app.deps import get_instance_settings

        settings = get_instance_settings(db)
        settings.task_history_retention_days = 7
        db.commit()
        deleted = purge_expired_task_history(db, settings)
        db.commit()
        assert deleted >= 1
        assert db.get(Task, task_id) is None

    with open_db() as db:
        settings = get_instance_settings(db)
        settings.task_history_retention_days = 0
        db.commit()

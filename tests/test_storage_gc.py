"""Durable storage delete queue tests (local and S3 backends)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Audio, PendingStorageDelete
from app.services.storage_gc import drain_all_pending_storage_deletes, queue_storage_delete
from tests.conftest import default_tariff_id, login_ready, open_db, setup_admin, signup, upload_audio
from tests.test_storage import SAMPLE_WAV_BYTES, _Upload


@pytest.mark.asyncio
async def test_pending_delete_survives_restart(tmp_path, monkeypatch):
    """Simulates crash after commit: row stays in DB until drain on startup."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'gc.db'}")
    from app.config import get_settings
    import app.db as db_module
    from app.db import get_engine, init_database, reset_engine
    from app.services.storage import LocalStorageBackend, reset_storage

    get_settings.cache_clear()
    reset_storage()
    reset_engine()
    init_database(get_engine())

    backend = LocalStorageBackend(str(tmp_path))
    upload = _Upload(SAMPLE_WAV_BYTES + b"survive-crash")
    ref = await backend.save_upload("gc1", ".wav", upload, max_bytes=1024)

    session = db_module.SessionLocal()
    try:
        queue_storage_delete(session, ref)
        session.commit()
    finally:
        session.close()

    assert backend.exists(ref)
    pending = db_module.SessionLocal()
    try:
        row = pending.scalar(select(PendingStorageDelete).where(PendingStorageDelete.storage_path == ref))
        assert row is not None
    finally:
        pending.close()

    drain_all_pending_storage_deletes()
    assert not backend.exists(ref)

    get_settings.cache_clear()
    reset_storage()
    reset_engine()


def test_wipe_local_storage_uses_durable_queue(client):
    """Default local backend: API wipe queues blob delete and drains it."""
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "localgc@example.com", "localgcpass1", tariff_id).status_code == 200
    login_ready(client, "localgc@example.com", "localgcpass1")

    uploaded = upload_audio(client)
    assert uploaded.status_code == 200, uploaded.text
    audio_id = uploaded.json()["id"]

    db = open_db()
    try:
        audio = db.get(Audio, audio_id)
        assert audio is not None
        storage_path = audio.storage_path
        assert Path(storage_path).is_file()
    finally:
        db.close()

    wiped = client.delete(f"/api/v1/audios/{audio_id}")
    assert wiped.status_code == 200, wiped.text

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        db = open_db()
        try:
            pending_count = db.scalar(select(func.count()).select_from(PendingStorageDelete))
        finally:
            db.close()
        if not Path(storage_path).is_file() and pending_count == 0:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("local wipe did not drain blob and pending queue in time")

    assert not Path(storage_path).is_file()

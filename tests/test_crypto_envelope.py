"""Envelope encryption: DEK bootstrap, rotation, re-encrypt job."""

from __future__ import annotations

import time

import pytest
from sqlalchemy import select

from app.crypto import (
    count_dek_usage,
    count_deks_needing_rewrap,
    create_dek,
    decrypt_str,
    dek_needs_rewrap,
    delete_retiring_dek,
    encrypt_str,
    rewrap_pending_deks,
    token_dek_id,
)
from app.models import DataEncryptionKey, EncryptionJob, InstanceSettings, WorkerNode, new_id
from app.timeutil import utcnow
from app.services.crypto_bootstrap import CryptoConfigError, bootstrap_encryption, validate_crypto_config
from app.services.crypto_reencrypt import reset_crypto_reencrypt, wait_reencrypt_job
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, open_db, setup_admin


def _login_admin(client):
    setup_admin(client)
    client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})


def test_bootstrap_creates_dek(client):
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        deks = list(db.scalars(select(DataEncryptionKey)).all())
        assert len(deks) == 1
        settings = db.get(InstanceSettings, 1)
        assert settings is not None
        assert settings.active_dek_id == deks[0].id
    finally:
        db.close()


def test_encrypt_decrypt_roundtrip(client):
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        token = encrypt_str("secret-value", db)
        assert token.startswith("v1:")
        assert decrypt_str(token, db) == "secret-value"
    finally:
        db.close()


def test_worker_token_encrypted_with_dek(client):
    _login_admin(client)
    r = client.post(
        "/api/v1/workers",
        json={"type": "transcribe", "name": "w1", "base_url": "http://127.0.0.1:9001", "api_token": "tok123"},
    )
    assert r.status_code == 200
    from app.db import SessionLocal, get_engine

    get_engine()
    db = SessionLocal()
    try:
        node = db.scalar(select(WorkerNode).where(WorkerNode.name == "w1"))
        assert node is not None
        assert token_dek_id(node.api_token_encrypted) is not None
        assert decrypt_str(node.api_token_encrypted, db) == "tok123"
    finally:
        db.close()


def test_add_dek_and_reencrypt_job(client):
    _login_admin(client)
    client.post(
        "/api/v1/workers",
        json={"type": "transcribe", "name": "w2", "base_url": "http://127.0.0.1:9002", "api_token": "tok456"},
    )
    from app.db import SessionLocal, get_engine

    get_engine()
    db = SessionLocal()
    try:
        settings = db.get(InstanceSettings, 1)
        old_dek = settings.active_dek_id
    finally:
        db.close()

    r = client.post("/api/v1/instance/crypto/deks")
    assert r.status_code == 200
    new_dek_id = r.json()["id"]
    assert new_dek_id != old_dek

    r = client.post("/api/v1/instance/crypto/reencrypt")
    assert r.status_code == 200
    job_id = r.json()["id"]

    deadline = time.monotonic() + 15
    status = None
    while time.monotonic() < deadline:
        wait_reencrypt_job(timeout_sec=0.5)
        status = client.get(f"/api/v1/instance/crypto/reencrypt/{job_id}")
        assert status.status_code == 200
        if status.json()["status"] in ("completed", "failed", "canceled"):
            break
        time.sleep(0.2)

    assert status is not None
    assert status.json()["status"] == "completed"

    db = SessionLocal()
    try:
        old = db.get(DataEncryptionKey, old_dek)
        assert old is None
        node = db.scalar(select(WorkerNode).where(WorkerNode.name == "w2"))
        assert node is not None
        assert token_dek_id(node.api_token_encrypted) == new_dek_id
        assert decrypt_str(node.api_token_encrypted, db) == "tok456"
        assert count_dek_usage(db, new_dek_id) >= 1
    finally:
        db.close()


def test_delete_retiring_dek_clears_encryption_job_fk(client):
    _login_admin(client)
    from app.db import SessionLocal, get_engine

    get_engine()
    db = SessionLocal()
    try:
        settings = db.get(InstanceSettings, 1)
        retiring_id = settings.active_dek_id
        retiring = db.get(DataEncryptionKey, retiring_id)
        retiring.status = "retiring"
        new_dek = create_dek(db, status="active")
        settings.active_dek_id = new_dek.id
        job = EncryptionJob(
            id=new_id(),
            target_dek_id=retiring_id,
            status="completed",
            created_at=utcnow(),
        )
        db.add(job)
        db.commit()
        job_id = job.id

        assert delete_retiring_dek(db, retiring_id)
        assert db.get(DataEncryptionKey, retiring_id) is None
        job = db.get(EncryptionJob, job_id)
        assert job is not None
        assert job.target_dek_id is None
    finally:
        db.close()


def test_rewrap_deks_on_startup_after_hub_secret_change(client, monkeypatch):
    _login_admin(client)
    from app.db import SessionLocal, get_engine

    get_engine()
    db = SessionLocal()
    try:
        wrapped_before = list(db.scalars(select(DataEncryptionKey)))[0].wrapped_key
        assert not dek_needs_rewrap(wrapped_before)
    finally:
        db.close()

    monkeypatch.setenv("HUB_SECRET", "new-hub-secret-rotation")
    monkeypatch.setenv("HUB_SECRET_PREV", "test-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    db = SessionLocal()
    try:
        row = db.scalars(select(DataEncryptionKey)).first()
        assert dek_needs_rewrap(row.wrapped_key)
        rewrapped = rewrap_pending_deks(db)
        assert rewrapped == 1
        wrapped_after = db.scalars(select(DataEncryptionKey)).first().wrapped_key
        assert wrapped_after != wrapped_before
        assert not dek_needs_rewrap(wrapped_after)
        assert count_deks_needing_rewrap(db) == 0
        assert decrypt_str(encrypt_str("x", db), db) == "x"
    finally:
        db.close()

    bootstrap_encryption()
    db = SessionLocal()
    try:
        assert count_deks_needing_rewrap(db) == 0
    finally:
        db.close()


def test_validate_fails_without_hub_secret_after_setup(client, monkeypatch):
    setup_admin(client)
    monkeypatch.setenv("HUB_SECRET", "")
    from app.config import get_settings

    get_settings.cache_clear()
    db = open_db()
    try:
        with pytest.raises(CryptoConfigError, match="HUB_SECRET is empty"):
            validate_crypto_config(db)
    finally:
        db.close()


def test_validate_fails_with_wrong_hub_secret(client, monkeypatch):
    setup_admin(client)
    monkeypatch.setenv("HUB_SECRET", "totally-wrong-secret")
    monkeypatch.delenv("HUB_SECRET_PREV", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    db = open_db()
    try:
        with pytest.raises(CryptoConfigError, match="cannot unwrap DEK"):
            validate_crypto_config(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_reencrypt():
    reset_crypto_reencrypt()
    yield
    reset_crypto_reencrypt()

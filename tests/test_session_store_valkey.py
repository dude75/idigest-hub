"""Valkey session store tests (fakeredis)."""

from __future__ import annotations

import fakeredis

from app.config import get_settings
from app.session_store import get_session_store, init_session_store, reset_session_store


def _use_fake_valkey(monkeypatch) -> fakeredis.FakeRedis:
    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setenv("SESSION_STORE", "valkey")
    monkeypatch.setenv("VALKEY_URL", "redis://valkey:6379/0")
    get_settings.cache_clear()
    monkeypatch.setattr("app.session_store._make_redis_client", lambda _url: fake)
    reset_session_store()
    init_session_store(get_settings())
    return fake


def test_valkey_session_create_lookup_touch_delete(monkeypatch, client, db):
    _use_fake_valkey(monkeypatch)
    store = get_session_store()
    raw = store.create(db, "user-1", 3600)
    record = store.lookup_by_raw_token(db, raw)
    assert record is not None
    assert record.user_id == "user-1"
    original_expires = record.expires_at
    store.touch(db, record, 7200)
    refreshed = store.lookup_by_raw_token(db, raw)
    assert refreshed is not None
    assert refreshed.expires_at > original_expires
    store.delete_by_raw_token(db, raw)
    assert store.lookup_by_raw_token(db, raw) is None


def test_valkey_session_auto_resolves_with_valkey_url(monkeypatch):
    monkeypatch.setenv("SESSION_STORE", "auto")
    monkeypatch.setenv("VALKEY_URL", "redis://valkey:6379/0")
    get_settings.cache_clear()
    from app.session_store import resolve_session_backend

    assert resolve_session_backend(get_settings()) == "valkey"

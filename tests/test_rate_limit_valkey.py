"""Valkey-backed rate limit store tests (fakeredis)."""

from __future__ import annotations

import fakeredis

from app.config import get_settings
from app.rate_limit import _hit, enforce_checks, reset_rate_limiter
from app.rate_limit_store import init_rate_limit_store


def _use_fake_valkey(monkeypatch) -> fakeredis.FakeRedis:
    server = fakeredis.FakeServer()
    fake = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "valkey")
    monkeypatch.setenv("VALKEY_URL", "redis://valkey:6379/0")
    get_settings.cache_clear()
    monkeypatch.setattr("app.rate_limit_store._make_redis_client", lambda _url: fake)
    reset_rate_limiter()
    init_rate_limit_store(get_settings())
    return fake


def test_valkey_hit_blocks_at_limit(monkeypatch):
    _use_fake_valkey(monkeypatch)
    allowed, _ = _hit("valkey:test", 2, 60.0)
    assert allowed
    allowed, _ = _hit("valkey:test", 2, 60.0)
    assert allowed
    allowed, retry = _hit("valkey:test", 2, 60.0)
    assert not allowed
    assert retry >= 1


def test_valkey_limit_zero_skips_counter(monkeypatch):
    fake = _use_fake_valkey(monkeypatch)
    for _ in range(5):
        allowed, _ = _hit("valkey:disabled", 0, 60.0)
        assert allowed
    assert fake.keys() == []


def test_valkey_shared_between_store_instances(monkeypatch):
    _use_fake_valkey(monkeypatch)
    allowed, _ = _hit("shared:key", 1, 60.0)
    assert allowed
    allowed, _ = _hit("shared:key", 1, 60.0)
    assert not allowed


def test_valkey_enforce_checks_rate_limited(monkeypatch):
    _use_fake_valkey(monkeypatch)
    from app.errors import ApiError, ErrorCode

    enforce_checks([("valkey:enforce", 1, 60.0)], "en")
    try:
        enforce_checks([("valkey:enforce", 1, 60.0)], "en")
    except ApiError as exc:
        assert exc.code == ErrorCode.rate_limited
    else:
        raise AssertionError("expected rate_limited")

"""Rate limit counter storage (memory or Valkey)."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any, Protocol

from app.config import Settings, get_settings

if TYPE_CHECKING:
    import redis

log = logging.getLogger("app.rate_limit")

MAX_BUCKETS = 20_000
PURGE_EVERY = 100
KEY_PREFIX = "hub:rl:"


class RateLimitStoreError(Exception):
    """Valkey unreachable or command failed."""


class RateLimitStore(Protocol):
    def hit(self, key: str, limit: int, window_sec: float) -> tuple[bool, int]: ...

    def reset(self) -> None: ...

    def purge_expired(self) -> int: ...

    def close(self) -> None: ...


@dataclass
class Bucket:
    count: int
    expires_at: float


_lock = Lock()
_buckets: dict[str, Bucket] = {}
_hit_count = 0

_redis_client: Any | None = None
_store: RateLimitStore | None = None


def _redis_module():
    import redis

    return redis


def _make_redis_client(url: str) -> redis.Redis:
    return _redis_module().Redis.from_url(url, decode_responses=True)


def _map_redis_error(exc: BaseException) -> RateLimitStoreError:
    from redis.exceptions import RedisError

    if isinstance(exc, RedisError):
        return RateLimitStoreError(str(exc))
    raise exc


class MemoryRateLimitStore:
    def hit(self, key: str, limit: int, window_sec: float) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        now = time.monotonic()
        global _hit_count
        with _lock:
            _hit_count += 1
            if _hit_count % PURGE_EVERY == 0:
                _purge_expired(now)

            bucket = _buckets.get(key)
            if bucket is None or bucket.expires_at <= now:
                _evict_if_needed()
                _buckets[key] = Bucket(count=1, expires_at=now + window_sec)
                return True, 0

            if bucket.count >= limit:
                retry_after = max(1, math.ceil(bucket.expires_at - now))
                return False, retry_after

            bucket.count += 1
            return True, 0

    def reset(self) -> None:
        global _buckets, _hit_count
        with _lock:
            _buckets = {}
            _hit_count = 0

    def purge_expired(self) -> int:
        now = time.monotonic()
        with _lock:
            before = len(_buckets)
            _purge_expired(now)
            return before - len(_buckets)

    def close(self) -> None:
        return None


class ValkeyRateLimitStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def hit(self, key: str, limit: int, window_sec: float) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        redis_key = f"{KEY_PREFIX}{key}"
        window_ms = max(1, int(math.ceil(window_sec * 1000)))
        try:
            count = int(self._client.incr(redis_key))
            if count == 1:
                self._client.pexpire(redis_key, window_ms)
            if count > limit:
                ttl_ms = int(self._client.pttl(redis_key))
                if ttl_ms < 0:
                    ttl_ms = window_ms
                return False, max(1, math.ceil(ttl_ms / 1000))
        except Exception as exc:
            raise _map_redis_error(exc) from exc
        return True, 0

    def reset(self) -> None:
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=f"{KEY_PREFIX}*", count=500)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            raise _map_redis_error(exc) from exc

    def purge_expired(self) -> int:
        return 0

    def close(self) -> None:
        return None


def _purge_expired(now: float) -> None:
    dead = [key for key, bucket in _buckets.items() if bucket.expires_at <= now]
    for key in dead:
        del _buckets[key]


def _evict_if_needed() -> None:
    if len(_buckets) < MAX_BUCKETS:
        return
    now = time.monotonic()
    _purge_expired(now)
    while len(_buckets) >= MAX_BUCKETS and _buckets:
        oldest_key = min(_buckets, key=lambda key: _buckets[key].expires_at)
        del _buckets[oldest_key]


def rate_limit_uses_memory(settings: Settings | None = None) -> bool:
    resolved = settings or get_settings()
    return resolved.RATE_LIMIT_BACKEND == "memory"


def _build_store(settings: Settings) -> RateLimitStore:
    if settings.RATE_LIMIT_BACKEND == "memory":
        return MemoryRateLimitStore()
    global _redis_client
    try:
        _redis_client = _make_redis_client(settings.VALKEY_URL)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RATE_LIMIT_BACKEND=valkey requires the redis package; pip install -r requirements.txt"
        ) from exc
    return ValkeyRateLimitStore(_redis_client)


def get_rate_limit_store() -> RateLimitStore:
    global _store
    if _store is None:
        _store = _build_store(get_settings())
    return _store


def init_rate_limit_store(settings: Settings) -> None:
    global _store
    close_rate_limit_store()
    _store = _build_store(settings)
    if settings.RATE_LIMIT_BACKEND == "valkey":
        assert _redis_client is not None
        try:
            _redis_client.ping()
        except Exception as exc:
            from redis.exceptions import RedisError

            if isinstance(exc, RedisError):
                raise RuntimeError(f"Valkey ping failed ({settings.VALKEY_URL}): {exc}") from exc
            raise
        log.info("rate limit backend: valkey")
    else:
        log.info("rate limit backend: memory")


def close_rate_limit_store() -> None:
    global _store, _redis_client
    if _store is not None:
        _store.close()
    _store = None
    if _redis_client is not None:
        _redis_client.close()
    _redis_client = None

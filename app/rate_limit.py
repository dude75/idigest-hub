"""In-memory rate limits (fixed window). One Uvicorn worker; counters reset on restart."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from sqlalchemy.orm import Session

from app.deps import get_instance_settings
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.models import InstanceSettings

log = logging.getLogger("app.rate_limit")

MAX_BUCKETS = 20_000
PURGE_EVERY = 100
WINDOW_MIN = 60.0
WINDOW_HOUR = 3600.0
SWEEP_INTERVAL_SEC = 300.0

_lock = Lock()
_buckets: dict[str, Bucket] = {}
_hit_count = 0
_cache_stamp = 0
_stamp = 0
_cached_limits: RateLimits | None = None


@dataclass
class Bucket:
    count: int
    expires_at: float


@dataclass(frozen=True)
class RateLimits:
    enabled: bool
    login_email: int
    login_ip: int
    login_global: int
    signup_email: int
    signup_ip: int
    signup_global: int
    reset_email: int
    reset_ip: int
    reset_global: int
    reset_confirm_ip: int
    reset_confirm_global: int
    setup_ip: int
    setup_global: int
    api_user: int
    api_ip: int
    api_global: int
    api_tasks_user: int
    api_tasks_ip: int


def limits_from_row(row: InstanceSettings) -> RateLimits:
    return RateLimits(
        enabled=bool(row.rate_limit_enabled),
        login_email=int(row.rate_limit_login_email),
        login_ip=int(row.rate_limit_login_ip),
        login_global=int(row.rate_limit_login_global),
        signup_email=int(row.rate_limit_signup_email),
        signup_ip=int(row.rate_limit_signup_ip),
        signup_global=int(row.rate_limit_signup_global),
        reset_email=int(row.rate_limit_reset_email),
        reset_ip=int(row.rate_limit_reset_ip),
        reset_global=int(row.rate_limit_reset_global),
        reset_confirm_ip=int(row.rate_limit_reset_confirm_ip),
        reset_confirm_global=int(row.rate_limit_reset_confirm_global),
        setup_ip=int(row.rate_limit_setup_ip),
        setup_global=int(row.rate_limit_setup_global),
        api_user=int(row.rate_limit_api_user),
        api_ip=int(row.rate_limit_api_ip),
        api_global=int(row.rate_limit_api_global),
        api_tasks_user=int(row.rate_limit_api_tasks_user),
        api_tasks_ip=int(row.rate_limit_api_tasks_ip),
    )


def invalidate_rate_limit_cache() -> None:
    global _stamp
    _stamp += 1


def get_rate_limits(db: Session) -> RateLimits:
    global _cached_limits, _cache_stamp
    if _cached_limits is not None and _cache_stamp == _stamp:
        return _cached_limits
    row = get_instance_settings(db)
    _cached_limits = limits_from_row(row)
    _cache_stamp = _stamp
    return _cached_limits


def client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def reset_rate_limiter() -> None:
    """Tests: clear buckets and settings cache."""
    global _buckets, _hit_count, _cached_limits, _cache_stamp
    with _lock:
        _buckets = {}
        _hit_count = 0
    _cached_limits = None
    _cache_stamp = -1
    invalidate_rate_limit_cache()


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


def _hit(key: str, limit: int, window_sec: float) -> tuple[bool, int]:
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


def _raise_rate_limited(locale: str, retry_after: int) -> None:
    raise ApiError(
        ErrorCode.rate_limited,
        t(locale, ErrorCode.rate_limited.value),
        headers={"Retry-After": str(retry_after)},
    )


def enforce_checks(checks: list[tuple[str, int, float]], locale: str) -> None:
    retry_after = 0
    for key, limit, window in checks:
        allowed, retry = _hit(key, limit, window)
        if not allowed:
            retry_after = max(retry_after, retry)
    if retry_after:
        _raise_rate_limited(locale, retry_after)


def enforce_login(email: str, ip: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    enforce_checks(
        [
            (f"login:email:{email}", limits.login_email, WINDOW_MIN),
            (f"login:ip:{ip}", limits.login_ip, WINDOW_MIN),
            ("login:global", limits.login_global, WINDOW_MIN),
        ],
        locale,
    )


def enforce_signup(email: str, ip: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    enforce_checks(
        [
            (f"signup:email:{email}", limits.signup_email, WINDOW_MIN),
            (f"signup:ip:{ip}", limits.signup_ip, WINDOW_MIN),
            ("signup:global", limits.signup_global, WINDOW_MIN),
        ],
        locale,
    )


def enforce_reset_request(email: str, ip: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    enforce_checks(
        [
            (f"reset:email:{email}", limits.reset_email, WINDOW_HOUR),
            (f"reset:ip:{ip}", limits.reset_ip, WINDOW_HOUR),
            ("reset:global", limits.reset_global, WINDOW_HOUR),
        ],
        locale,
    )


def enforce_reset_confirm(ip: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    enforce_checks(
        [
            (f"reset_confirm:ip:{ip}", limits.reset_confirm_ip, WINDOW_HOUR),
            ("reset_confirm:global", limits.reset_confirm_global, WINDOW_HOUR),
        ],
        locale,
    )


def enforce_setup(ip: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    enforce_checks(
        [
            (f"setup:ip:{ip}", limits.setup_ip, WINDOW_HOUR),
            ("setup:global", limits.setup_global, WINDOW_HOUR),
        ],
        locale,
    )


def enforce_bearer_api(request: Request, user_id: str, limits: RateLimits, locale: str) -> None:
    if not limits.enabled:
        return
    ip = client_ip(request)
    checks: list[tuple[str, int, float]] = [
        (f"api:user:{user_id}", limits.api_user, WINDOW_MIN),
        (f"api:ip:{ip}", limits.api_ip, WINDOW_MIN),
        ("api:global", limits.api_global, WINDOW_MIN),
    ]
    enforce_checks(checks, locale)


def enforce_write_limits(request: Request, user_id: str, limits: RateLimits, locale: str) -> None:
    """Rate-limit upload and task-create for session cookies and Bearer alike."""
    if not limits.enabled:
        return
    ip = client_ip(request)
    path = request.url.path.rstrip("/") or "/"
    if request.method != "POST":
        return
    checks: list[tuple[str, int, float]] = []
    if path.endswith("/audios"):
        checks = [
            (f"write:upload:user:{user_id}", limits.api_tasks_user, WINDOW_MIN),
            (f"write:upload:ip:{ip}", limits.api_tasks_ip, WINDOW_MIN),
        ]
    elif path.endswith(("/tasks/transcribe", "/tasks/summarize")):
        checks = [
            (f"api:tasks:user:{user_id}", limits.api_tasks_user, WINDOW_MIN),
            (f"api:tasks:ip:{ip}", limits.api_tasks_ip, WINDOW_MIN),
        ]
    if checks:
        enforce_checks(checks, locale)


def purge_expired_buckets() -> int:
    now = time.monotonic()
    with _lock:
        before = len(_buckets)
        _purge_expired(now)
        return before - len(_buckets)


async def rate_limit_sweeper(stop: asyncio.Event) -> None:
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=SWEEP_INTERVAL_SEC)
            return
        except asyncio.TimeoutError:
            removed = purge_expired_buckets()
            if removed:
                log.debug("rate_limit sweeper removed %s buckets", removed)


def rate_limits_public(row: InstanceSettings) -> dict[str, int | bool]:
    return {
        "rate_limit_enabled": bool(row.rate_limit_enabled),
        "rate_limit_login_email": int(row.rate_limit_login_email),
        "rate_limit_login_ip": int(row.rate_limit_login_ip),
        "rate_limit_login_global": int(row.rate_limit_login_global),
        "rate_limit_signup_email": int(row.rate_limit_signup_email),
        "rate_limit_signup_ip": int(row.rate_limit_signup_ip),
        "rate_limit_signup_global": int(row.rate_limit_signup_global),
        "rate_limit_reset_email": int(row.rate_limit_reset_email),
        "rate_limit_reset_ip": int(row.rate_limit_reset_ip),
        "rate_limit_reset_global": int(row.rate_limit_reset_global),
        "rate_limit_reset_confirm_ip": int(row.rate_limit_reset_confirm_ip),
        "rate_limit_reset_confirm_global": int(row.rate_limit_reset_confirm_global),
        "rate_limit_setup_ip": int(row.rate_limit_setup_ip),
        "rate_limit_setup_global": int(row.rate_limit_setup_global),
        "rate_limit_api_user": int(row.rate_limit_api_user),
        "rate_limit_api_ip": int(row.rate_limit_api_ip),
        "rate_limit_api_global": int(row.rate_limit_api_global),
        "rate_limit_api_tasks_user": int(row.rate_limit_api_tasks_user),
        "rate_limit_api_tasks_ip": int(row.rate_limit_api_tasks_ip),
    }

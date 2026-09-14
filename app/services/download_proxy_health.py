"""Reachability checks for the optional URL-download proxy."""

from __future__ import annotations

import socket
import threading
import time
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import InstanceSettings
from app.services.import_platforms import effective_download_proxy, resolve_download_proxy_url

DEFAULT_PROXY_PORTS = {
    "socks5": 1080,
    "socks5h": 1080,
    "socks4": 1080,
    "http": 8080,
    "https": 8443,
}
CHECK_TIMEOUT_SEC = 3.0
CACHE_TTL_SEC = 30.0

_cache: dict[str, tuple[float, bool]] = {}
_cache_lock = threading.Lock()


def reset_download_proxy_health_cache() -> None:
    with _cache_lock:
        _cache.clear()


def proxy_host_port(proxy_url: str) -> tuple[str, int]:
    parsed = urlparse(proxy_url.strip())
    host = parsed.hostname
    if not host:
        raise ValueError("invalid proxy url")
    port = parsed.port
    if port is None:
        port = DEFAULT_PROXY_PORTS.get(parsed.scheme or "", 1080)
    return host, int(port)


def check_download_proxy_available(proxy_url: str, *, timeout: float = CHECK_TIMEOUT_SEC) -> bool:
    try:
        host, port = proxy_host_port(proxy_url)
    except ValueError:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_download_proxy_available(proxy_url: str, *, force: bool = False) -> bool:
    now = time.monotonic()
    with _cache_lock:
        if not force and proxy_url in _cache:
            checked_at, result = _cache[proxy_url]
            if now - checked_at < CACHE_TTL_SEC:
                return result
    result = check_download_proxy_available(proxy_url)
    with _cache_lock:
        _cache[proxy_url] = (now, result)
    return result


def download_proxy_status(settings: InstanceSettings, db: Session) -> dict[str, bool]:
    required = bool(settings.download_proxy_enabled)
    if not required:
        return {"download_proxy_required": False, "download_proxy_available": True}
    proxy = effective_download_proxy(settings, db)
    if not proxy:
        return {"download_proxy_required": True, "download_proxy_available": False}
    return {
        "download_proxy_required": True,
        "download_proxy_available": is_download_proxy_available(proxy),
    }


def download_proxy_ready(settings: InstanceSettings, db: Session) -> bool:
    status = download_proxy_status(settings, db)
    if not status["download_proxy_required"]:
        return True
    return status["download_proxy_available"]


def download_proxy_card_status(settings: InstanceSettings, db: Session) -> str:
    if not (settings.download_proxy_url or "").strip():
        return "na"
    proxy = resolve_download_proxy_url(settings, db)
    if not proxy:
        return "down"
    return "up" if is_download_proxy_available(proxy) else "down"

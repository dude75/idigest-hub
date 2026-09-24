"""Trusted reverse-proxy client IP resolution for rate limits."""

from __future__ import annotations

import ipaddress
import logging
from functools import lru_cache

from fastapi import Request

log = logging.getLogger("app.proxy")

TrustedEntry = ipaddress.IPv4Address | ipaddress.IPv6Address | ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache
def trusted_proxy_entries(raw: str) -> tuple[TrustedEntry, ...]:
    entries: list[TrustedEntry] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            if "/" in item:
                entries.append(ipaddress.ip_network(item, strict=False))
            else:
                entries.append(ipaddress.ip_address(item))
        except ValueError:
            log.warning("ignoring invalid TRUSTED_PROXIES entry: %r", item)
    return tuple(entries)


def reset_trusted_proxy_cache() -> None:
    """Tests: clear parsed TRUSTED_PROXIES cache."""
    trusted_proxy_entries.cache_clear()


def is_trusted_proxy(ip_str: str, trusted: tuple[TrustedEntry, ...]) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for entry in trusted:
        if isinstance(entry, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if addr in entry:
                return True
        elif addr == entry:
            return True
    return False


def _valid_ip(ip_str: str) -> str | None:
    try:
        return str(ipaddress.ip_address(ip_str.strip()))
    except ValueError:
        return None


def _peer_host(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _client_from_forwarded_for(
    forwarded_for: str,
    trusted: tuple[TrustedEntry, ...],
) -> str | None:
    ips = [part.strip() for part in forwarded_for.split(",") if part.strip()]
    if not ips:
        return None
    for ip_str in reversed(ips):
        if not is_trusted_proxy(ip_str, trusted):
            return _valid_ip(ip_str)
    return _valid_ip(ips[0])


def _resolve_client_ip_from_headers(
    peer: str,
    headers: dict[str, str],
    trusted: tuple[TrustedEntry, ...],
) -> str:
    if not trusted or not is_trusted_proxy(peer, trusted):
        return peer

    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        client = _client_from_forwarded_for(forwarded_for, trusted)
        if client:
            return client

    real_ip = headers.get("x-real-ip", "")
    if real_ip:
        client = _valid_ip(real_ip)
        if client:
            return client

    return peer


def resolve_client_ip(request: Request, trusted: tuple[TrustedEntry, ...]) -> str:
    peer = _peer_host(request)
    headers = {key.lower(): value for key, value in request.headers.items()}
    return _resolve_client_ip_from_headers(peer, headers, trusted)


def asgi_headers(scope: dict) -> dict[str, str]:
    raw = scope.get("headers") or []
    return {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in raw}


def client_ip_from_asgi_scope(scope: dict) -> str:
    from app.config import get_settings

    trusted = trusted_proxy_entries(get_settings().TRUSTED_PROXIES)
    client = scope.get("client")
    peer = client[0] if client else "unknown"
    return _resolve_client_ip_from_headers(peer, asgi_headers(scope), trusted)

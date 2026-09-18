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


def resolve_client_ip(request: Request, trusted: tuple[TrustedEntry, ...]) -> str:
    peer = _peer_host(request)
    if not trusted or not is_trusted_proxy(peer, trusted):
        return peer

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        client = _client_from_forwarded_for(forwarded_for, trusted)
        if client:
            return client

    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        client = _valid_ip(real_ip)
        if client:
            return client

    return peer

"""Trusted proxy client IP resolution."""

from __future__ import annotations

from starlette.requests import Request

from app.config import get_settings
from app.proxy import (
    is_trusted_proxy,
    reset_trusted_proxy_cache,
    resolve_client_ip,
    trusted_proxy_entries,
)
from app.rate_limit import client_ip, reset_rate_limiter


def _request(
    peer: str,
    *,
    x_forwarded_for: str | None = None,
    x_real_ip: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if x_forwarded_for is not None:
        headers.append((b"x-forwarded-for", x_forwarded_for.encode()))
    if x_real_ip is not None:
        headers.append((b"x-real-ip", x_real_ip.encode()))
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_empty_trusted_proxies_uses_peer():
    trusted = trusted_proxy_entries("")
    req = _request("203.0.113.50", x_forwarded_for="1.2.3.4")
    assert resolve_client_ip(req, trusted) == "203.0.113.50"


def test_trusted_peer_uses_x_forwarded_for():
    trusted = trusted_proxy_entries("127.0.0.1")
    req = _request("127.0.0.1", x_forwarded_for="203.0.113.50")
    assert resolve_client_ip(req, trusted) == "203.0.113.50"


def test_trusted_peer_uses_x_real_ip_when_xff_missing():
    trusted = trusted_proxy_entries("127.0.0.1")
    req = _request("127.0.0.1", x_real_ip="203.0.113.50")
    assert resolve_client_ip(req, trusted) == "203.0.113.50"


def test_untrusted_peer_ignores_spoofed_headers():
    trusted = trusted_proxy_entries("127.0.0.1")
    req = _request("203.0.113.99", x_forwarded_for="1.2.3.4", x_real_ip="5.6.7.8")
    assert resolve_client_ip(req, trusted) == "203.0.113.99"


def test_xff_chain_skips_trusted_hops():
    trusted = trusted_proxy_entries("127.0.0.1,198.51.100.0/24")
    req = _request(
        "127.0.0.1",
        x_forwarded_for="203.0.113.50, 198.51.100.10",
    )
    assert resolve_client_ip(req, trusted) == "203.0.113.50"


def test_ipv6_trusted_proxy():
    trusted = trusted_proxy_entries("::1")
    req = _request("::1", x_forwarded_for="203.0.113.50")
    assert resolve_client_ip(req, trusted) == "203.0.113.50"


def test_is_trusted_proxy_cidr():
    trusted = trusted_proxy_entries("10.0.0.0/8")
    assert is_trusted_proxy("10.1.2.3", trusted)
    assert not is_trusted_proxy("203.0.113.1", trusted)


def test_invalid_trusted_proxy_entries_are_ignored():
    trusted = trusted_proxy_entries("127.0.0.1,not-an-ip,198.51.100.0/24")
    assert len(trusted) == 2


def test_client_ip_integration(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")
    get_settings.cache_clear()
    reset_trusted_proxy_cache()
    reset_rate_limiter()

    req = _request("127.0.0.1", x_forwarded_for="203.0.113.50")
    assert client_ip(req) == "203.0.113.50"

    req_direct = _request("203.0.113.60", x_forwarded_for="1.2.3.4")
    assert client_ip(req_direct) == "203.0.113.60"

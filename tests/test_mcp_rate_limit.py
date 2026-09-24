"""MCP and OAuth endpoint rate limits."""

from __future__ import annotations

from app.rate_limit import enforce_mcp_tool, limits_from_row, reset_rate_limiter
from tests.conftest import open_db, setup_admin
from tests.test_oauth_provider import REDIRECT_URI, _enable_oauth


def test_oauth_register_rate_limited(client, monkeypatch):
    _enable_oauth(client, monkeypatch)
    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_oauth_register_ip = 2
        row.rate_limit_oauth_register_global = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    body = {
        "client_name": "spam",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    assert client.post("/oauth/register", json=body).status_code == 201
    assert client.post("/oauth/register", json=body).status_code == 201
    blocked = client.post("/oauth/register", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.headers.get("Retry-After")


def test_mcp_transport_shares_bearer_api_limit(client, monkeypatch):
    from app.errors import ErrorCode
    from app.services.mcp_integration import _mcp_transport_rate_limit
    from tests.test_oauth_provider import _oauth_access_token

    access = _oauth_access_token(client, monkeypatch, scope="audio:read")

    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_api_user = 2
        row.rate_limit_api_ip = 0
        row.rate_limit_api_global = 0
        db.commit()
    finally:
        db.close()
    reset_rate_limiter()

    def mcp_scope() -> dict:
        return {
            "type": "http",
            "method": "POST",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"authorization", f"Bearer {access}".encode("ascii"))],
        }

    assert _mcp_transport_rate_limit(mcp_scope()) is None
    assert _mcp_transport_rate_limit(mcp_scope()) is None
    blocked = _mcp_transport_rate_limit(mcp_scope())
    assert blocked is not None
    assert blocked.status_code == 429
    assert blocked.code == ErrorCode.rate_limited


def test_mcp_get_task_poll_limit_unit(client):
    setup_admin(client)
    reset_rate_limiter()
    db = open_db()
    try:
        from app.models import InstanceSettings

        row = db.get(InstanceSettings, 1)
        assert row is not None
        row.rate_limit_mcp_poll_user = 2
        limits = limits_from_row(row)
    finally:
        db.close()
    user = "user-1"
    for _ in range(2):
        enforce_mcp_tool("get_task", user, "127.0.0.1", limits, "en")
    try:
        enforce_mcp_tool("get_task", user, "127.0.0.1", limits, "en")
        assert False, "expected rate limit"
    except Exception as exc:
        from app.errors import ApiError, ErrorCode

        assert isinstance(exc, ApiError)
        assert exc.code == ErrorCode.rate_limited

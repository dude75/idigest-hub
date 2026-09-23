"""Embedded MCP (Streamable HTTP) on the hub."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.server import MCPServer
from mcp_types import TextContent
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from app.config import get_settings
from app.db import SessionLocal, get_engine
from app.deps import AuthContext, load_org_bundle
from app.services.hub_mcp_token_verifier import HubMcpTokenVerifier
from app.services.mcp_library import list_transcriptions_payload
from app.services.oauth_provider import mcp_resource_url, oauth_provider_enabled, public_base_url
from app.services.oauth_scopes import normalize_scopes

if TYPE_CHECKING:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

log = logging.getLogger("app")

_mcp_server: MCPServer[dict[str, Any]] | None = None
_mcp_starlette: Starlette | None = None


def mcp_enabled() -> bool:
    return oauth_provider_enabled()


def _auth_settings(db) -> AuthSettings | None:
    base = public_base_url(db)
    resource = mcp_resource_url(db=db)
    if not base or not resource:
        return None
    return AuthSettings(
        issuer_url=AnyHttpUrl(base),
        resource_server_url=AnyHttpUrl(resource),
        required_scopes=["transcripts:read"],
        validate_token_resource=True,
    )


def _auth_context_from_token(db, user_id: str, scopes: frozenset[str]) -> AuthContext:
    from app.models import User

    user = db.get(User, user_id)
    if user is None or user.disabled_at is not None:
        raise PermissionError("user not found")
    org, membership = load_org_bundle(db, user)
    return AuthContext(
        user=user,
        actor=user,
        org=org,
        membership=membership,
        session=None,
        via_api_token=False,
        locale=user.locale or "en",
        impersonating=False,
        via_oauth_token=True,
        oauth_scopes=scopes,
    )


def get_mcp_server() -> MCPServer[dict[str, Any]]:
    global _mcp_server
    if _mcp_server is not None:
        return _mcp_server

    get_engine()
    if SessionLocal is None:
        raise RuntimeError("database not initialized")
    with SessionLocal() as db:
        auth = _auth_settings(db)
    if auth is None:
        raise RuntimeError("MCP auth settings missing (enable OAuth + Public URL)")

    server = MCPServer(
        name="idigest-hub",
        title="idigest",
        instructions="Read transcripts from your idigest library.",
        token_verifier=HubMcpTokenVerifier(),
        auth=auth,
        log_level="INFO",
    )

    @server.tool(name="list_transcriptions", description="List transcript metadata in your library (no utterances).")
    async def list_transcriptions(include_hidden: bool = False) -> str:
        access = get_access_token()
        if access is None or not access.subject:
            raise PermissionError("authentication required")
        scopes = normalize_scopes(" ".join(access.scopes))
        with SessionLocal() as db:
            ctx = _auth_context_from_token(db, access.subject, scopes)
            payload = list_transcriptions_payload(db, ctx, include_hidden=include_hidden)
        return json.dumps(payload, ensure_ascii=False)

    _mcp_server = server
    return server


def get_mcp_starlette_app() -> Starlette:
    global _mcp_starlette
    if _mcp_starlette is not None:
        return _mcp_starlette
    settings = get_settings()
    host = settings.HOST
    transport_security = None
    if host in ("127.0.0.1", "localhost", "::1"):
        from mcp.server.transport_security import TransportSecuritySettings

        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )
    server = get_mcp_server()
    _mcp_starlette = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=transport_security,
        host=host,
    )
    return _mcp_starlette


def get_mcp_session_manager() -> StreamableHTTPSessionManager:
    return get_mcp_server().session_manager


_MCP_HTTP_METHODS = frozenset({"GET", "POST", "DELETE", "OPTIONS", "HEAD"})


class McpHttpHandler:
    """Streamable HTTP MCP at /mcp (canonical resource URL has no trailing slash)."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await get_mcp_starlette_app()(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/mcp" or path.startswith("/mcp/"):
            inner = path.removeprefix("/mcp") or "/"
            scope = dict(scope)
            scope["path"] = inner
            scope["root_path"] = (scope.get("root_path") or "") + "/mcp"
        await get_mcp_starlette_app()(scope, receive, send)


def register_mcp_http_routes(application) -> None:
    """Register /mcp and /mcp/ (Mount alone does not match POST /mcp without trailing slash)."""
    handler = McpHttpHandler()
    for path in ("/mcp", "/mcp/"):
        application.router.add_route(path, handler, methods=sorted(_MCP_HTTP_METHODS))


@asynccontextmanager
async def mcp_session_manager_lifecycle():
    if not mcp_enabled():
        yield
        return
    try:
        get_mcp_starlette_app()
    except RuntimeError as exc:
        log.warning("MCP not started: %s", exc)
        yield
        return
    async with get_mcp_session_manager().run():
        yield

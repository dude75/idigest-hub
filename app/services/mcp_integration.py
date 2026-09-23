"""Embedded MCP (Streamable HTTP) on the hub."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.server import MCPServer
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from app.config import get_settings
import app.db as db
from app.deps import AuthContext, load_org_bundle
from app.errors import ApiError
from app.services.dispatcher import locked_tick_job
from app.services.hub_mcp_token_verifier import HubMcpTokenVerifier
from app.services.mcp_library import (
    delete_summary_payload,
    get_summary_payload,
    get_transcript_payload,
    list_skills_payload,
    list_summaries_payload,
    list_transcriptions_payload,
    summarize_transcript_payload,
    update_skill_payload,
)
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
        required_scopes=[],
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

    db.get_engine()
    if db.SessionLocal is None:
        raise RuntimeError("database not initialized")
    with db.SessionLocal() as session:
        auth = _auth_settings(session)
    if auth is None:
        raise RuntimeError("MCP auth settings missing (enable OAuth + Public URL)")

    server = MCPServer(
        name="idigest-hub",
        title="idigest",
        instructions=(
            "Access your idigest library: transcripts, summaries, and skills. "
            "OAuth scopes gate each tool (see oauth-protected-resource metadata)."
        ),
        token_verifier=HubMcpTokenVerifier(),
        auth=auth,
        log_level="INFO",
    )

    def _mcp_json_tool(
        fn: Callable[..., dict],
        *,
        commit: bool = False,
        post_commit: Callable[[dict], Any] | None = None,
    ):
        async def run(**kwargs) -> str:
            access = get_access_token()
            if access is None or not access.subject:
                raise PermissionError("authentication required")
            scopes = normalize_scopes(" ".join(access.scopes))
            try:
                with db.SessionLocal() as session:
                    ctx = _auth_context_from_token(session, access.subject, scopes)
                    payload = fn(session, ctx, **kwargs)
                    if commit:
                        session.commit()
            except ApiError as exc:
                _raise_from_api_error(exc)
            if post_commit is not None:
                post_commit(payload)
            return json.dumps(payload, ensure_ascii=False)

        return run

    def _raise_from_api_error(exc: ApiError) -> None:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        err = detail.get("error") if isinstance(detail.get("error"), dict) else {}
        message = err.get("message") or err.get("code") or "request failed"
        if exc.status_code in {401, 403}:
            raise PermissionError(message) from exc
        if exc.status_code == 404:
            raise ValueError("not found") from exc
        raise ValueError(message) from exc

    @server.tool(
        name="list_transcriptions",
        description="List transcript metadata in your library (no utterances). Requires transcripts:read.",
    )
    async def list_transcriptions(include_hidden: bool = False) -> str:
        return await _mcp_json_tool(list_transcriptions_payload)(include_hidden=include_hidden)

    @server.tool(
        name="get_transcript",
        description="Fetch one transcript with utterances. Requires transcripts:read.",
    )
    async def get_transcript(transcript_id: str) -> str:
        return await _mcp_json_tool(get_transcript_payload)(transcript_id=transcript_id)

    @server.tool(
        name="list_summaries",
        description="List summary metadata in your library (no body text). Requires summaries:read.",
    )
    async def list_summaries(include_hidden: bool = False) -> str:
        return await _mcp_json_tool(list_summaries_payload)(include_hidden=include_hidden)

    @server.tool(
        name="get_summary",
        description="Fetch one summary including body text. Requires summaries:read.",
    )
    async def get_summary(summary_id: str) -> str:
        return await _mcp_json_tool(get_summary_payload)(summary_id=summary_id)

    @server.tool(
        name="delete_summary",
        description="Delete a summary (owner or org admin). Requires summaries:write.",
    )
    async def delete_summary(summary_id: str) -> str:
        return await _mcp_json_tool(delete_summary_payload, commit=True)(summary_id=summary_id)

    @server.tool(
        name="list_skills",
        description="List skills visible to you (base, org, personal, shared). Requires skills:read.",
    )
    async def list_skills(scope: str | None = None) -> str:
        return await _mcp_json_tool(list_skills_payload)(scope=scope)

    @server.tool(
        name="update_skill",
        description=(
            "Update a skill name and body when permitted (personal, org admin for org skills, "
            "instance admin for base skills). Requires skills:write."
        ),
    )
    async def update_skill(skill_id: str, name: str, body: str) -> str:
        return await _mcp_json_tool(update_skill_payload, commit=True)(
            skill_id=skill_id, name=name, body=body
        )

    def _schedule_summarize(task_payload: dict) -> None:
        task_id = task_payload.get("id")
        if task_id:
            asyncio.create_task(locked_tick_job(str(task_id)))

    @server.tool(
        name="summarize_transcript",
        description="Queue a summarize task for a transcript with one or more skills. Requires tasks:write.",
    )
    async def summarize_transcript(transcript_id: str, skill_ids: list[str]) -> str:
        return await _mcp_json_tool(
            summarize_transcript_payload,
            commit=True,
            post_commit=_schedule_summarize,
        )(transcript_id=transcript_id, skill_ids=skill_ids)

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

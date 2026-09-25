"""Embedded MCP (Streamable HTTP) on the hub."""

from __future__ import annotations

import contextvars
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.server import MCPServer
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from app.config import get_settings
import app.db as db
from app.deps import AuthContext, load_org_bundle
from app.errors import ApiError, ErrorCode
from app.i18n import t
from app.proxy import asgi_headers, client_ip_from_asgi_scope
from app.rate_limit import enforce_api_limits, enforce_mcp_tool, get_rate_limits
from app.services.dispatcher import schedule_locked_tick_asyncio
from app.services.hub_mcp_token_verifier import HubMcpTokenVerifier
from app.services.mcp_library import (
    create_audio_import_payload,
    create_audio_upload_payload,
    create_skill_payload,
    create_summary_payload,
    create_transcribe_payload,
    get_task_payload,
    stop_capture_task_payload,
    delete_audio_payload,
    delete_skill_payload,
    delete_summary_payload,
    delete_transcript_payload,
    get_audio_payload,
    get_skill_payload,
    get_summary_payload,
    get_transcript_payload,
    list_audios_payload,
    list_skills_payload,
    list_summaries_payload,
    list_transcripts_payload,
    update_skill_payload,
    update_summary_payload,
    update_transcript_payload,
)
from app.services.oauth_provider import mcp_resource_url, oauth_provider_enabled, public_base_url
from app.services.oauth_scopes import scopes_from_bearer_metadata

if TYPE_CHECKING:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

log = logging.getLogger("app")

_mcp_client_ip: contextvars.ContextVar[str | None] = contextvars.ContextVar("mcp_client_ip", default=None)

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
            "idigest hub library (audio, transcripts, summaries, skills). OAuth scopes gate each tool.\n\n"
            "Meeting / conference capture (Jitsi and similar URLs via create_audio_import):\n"
            "- Call create_audio_import ONCE per meeting. That URL becomes a capture task (type=capture). "
            "Never call create_audio_import again for the same meeting to leave, stop, or transcribe — "
            "a second call starts a new bot join.\n"
            "- Optional bot_display_name on create_audio_import sets the bot name in the meeting for that job "
            "(overrides user profile and org default).\n"
            "- While recording: poll get_task(task_id) on the capture task; when the user should leave, "
            "call stop_capture_task(task_id) once, then keep polling the same task_id until status=success "
            "and audio_id is set.\n"
            "- Transcribe after capture: (A) set transcribe=true on the initial create_audio_import, then "
            "after capture succeeds poll meta.follow_up_task_id (transcribe task) until success and use "
            "transcript_id; or (B) after capture succeeds with transcribe=false, call create_transcribe(audio_id) "
            "— do not re-import the meeting URL.\n"
            "- Async jobs: create_audio_import, create_transcribe, and create_summary return task JSON; "
            "poll get_task until terminal status. List tools cap at 100 items (truncated=true means fetch by id).\n"
            "- Audio IDs (for get_audio / create_transcribe / delete_audio): do not invent ids. Valid sources: "
            "items[].id from list_audios; id from create_audio_upload; audio_id on get_task once import/capture "
            "status=success (may stay null while the job is queued or running). If get_audio or create_transcribe "
            "returns not found, re-check get_task or list_audios — the file may not exist yet or the id may be wrong."
        ),
        token_verifier=HubMcpTokenVerifier(),
        auth=auth,
        log_level="INFO",
    )

    def _mcp_tool_rate_limits(tool: str, user_id: str, locale: str) -> None:
        ip = _mcp_client_ip.get() or "unknown"
        with db.SessionLocal() as session:
            enforce_mcp_tool(tool, user_id, ip, get_rate_limits(session), locale)

    def _mcp_json_tool(
        fn: Callable[..., dict],
        *,
        tool: str,
        commit: bool = False,
        post_commit: Callable[[dict], Any] | None = None,
    ):
        async def run(**kwargs) -> str:
            try:
                access = get_access_token()
                if access is None or not access.subject:
                    raise ToolError("authentication required")
                claims = access.claims or {}
                scopes = scopes_from_bearer_metadata(
                    token_scopes=access.scopes,
                    scope_claim=claims.get("scope"),
                )
                with db.SessionLocal() as session:
                    ctx = _auth_context_from_token(session, access.subject, scopes)
                    _mcp_tool_rate_limits(tool, access.subject, ctx.locale)
                    payload = fn(session, ctx, **kwargs)
                    if commit:
                        session.commit()
            except PermissionError as exc:
                raise ToolError(str(exc)) from exc
            except ValueError as exc:
                raise ToolError(str(exc)) from exc
            except ApiError as exc:
                if exc.code == ErrorCode.rate_limited:
                    locale = "en"
                    detail = exc.detail if isinstance(exc.detail, dict) else {}
                    err = detail.get("error") if isinstance(detail.get("error"), dict) else {}
                    message = err.get("message")
                    raise ToolError(message or t(locale, ErrorCode.rate_limited.value)) from exc
                _raise_from_api_error(exc)
            if post_commit is not None:
                post_commit(payload)
            return json.dumps(payload, ensure_ascii=False)

        return run

    def _raise_from_api_error(exc: ApiError) -> None:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        err = detail.get("error") if isinstance(detail.get("error"), dict) else {}
        message = err.get("message") or err.get("code") or "request failed"
        raise ToolError(message) from exc

    def _schedule_task(task_payload: dict, *, refresh_health: bool = True) -> None:
        task_id = task_payload.get("task_id")
        if task_id:
            schedule_locked_tick_asyncio(str(task_id), refresh_health=refresh_health)

    @server.tool(
        name="list_audios",
        description=(
            "List audio metadata in your library (items[].id is the audio_id for get_audio and create_transcribe). "
            "Use to pick a valid id; truncated=true means more rows exist — do not guess ids. Requires audio:read."
        ),
    )
    async def list_audios(include_hidden: bool = False) -> str:
        return await _mcp_json_tool(list_audios_payload, tool="list_audios")(include_hidden=include_hidden)

    @server.tool(
        name="get_audio",
        description=(
            "Fetch one audio item with linked transcript metadata. Call before create_transcribe to confirm "
            "audio_id exists and is accessible; not found means wrong id, no access, or import/capture not finished. "
            "Requires audio:read."
        ),
    )
    async def get_audio(audio_id: str) -> str:
        return await _mcp_json_tool(get_audio_payload, tool="get_audio")(audio_id=audio_id)

    @server.tool(
        name="create_audio_upload",
        description=(
            "Upload an audio file (base64). Allowed: .wav, .mp3, .m4a. Response id is audio_id for create_transcribe. "
            "Requires audio:write."
        ),
    )
    async def create_audio_upload(filename: str, content_base64: str) -> str:
        return await _mcp_json_tool(create_audio_upload_payload, tool="create_audio_upload", commit=True)(
            filename=filename, content_base64=content_base64
        )

    @server.tool(
        name="create_audio_import",
        description=(
            "Start ONE async import or meeting capture from URL. Meeting links become type=capture "
            "(bot joins once). Do not call again for the same meeting — use stop_capture_task + get_task, "
            "then create_transcribe(audio_id) or set transcribe=true here and poll follow_up_task_id. "
            "Optional bot_display_name overrides user/org default for capture jobs. Requires tasks:write."
        ),
    )
    async def create_audio_import(
        url: str,
        transcribe: bool = False,
        skill_ids: list[str] | None = None,
        bot_display_name: str | None = None,
    ) -> str:
        return await _mcp_json_tool(
            create_audio_import_payload,
            tool="create_audio_import",
            commit=True,
            post_commit=lambda payload: _schedule_task(payload, refresh_health=False),
        )(url=url, transcribe=transcribe, skill_ids=skill_ids, bot_display_name=bot_display_name)

    @server.tool(
        name="get_task",
        description=(
            "Poll task JSON by task_id (import, capture, transcribe, summarize). "
            "For import/capture: when status=success, copy audio_id for create_transcribe (null until then). "
            "For capture: reuse the same id after stop_capture_task; check meta.follow_up_task_id when "
            "transcribe was requested upfront. Requires tasks:write."
        ),
    )
    async def get_task(task_id: str) -> str:
        locale = "en"
        try:
            access = get_access_token()
            if access is None or not access.subject:
                raise ToolError("authentication required")
            claims = access.claims or {}
            scopes = scopes_from_bearer_metadata(
                token_scopes=access.scopes,
                scope_claim=claims.get("scope"),
            )
            with db.SessionLocal() as session:
                ctx = _auth_context_from_token(session, access.subject, scopes)
                locale = ctx.locale
                _mcp_tool_rate_limits("get_task", access.subject, ctx.locale)
                payload, schedule, refresh_health = get_task_payload(
                    session, ctx, task_id=task_id
                )
        except PermissionError as exc:
            raise ToolError(str(exc)) from exc
        except ApiError as exc:
            if exc.code == ErrorCode.rate_limited:
                raise ToolError(t(locale, ErrorCode.rate_limited.value)) from exc
            raise
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        if schedule:
            schedule_locked_tick_asyncio(task_id, refresh_health=refresh_health, wait=False)
        return json.dumps(payload, ensure_ascii=False)

    @server.tool(
        name="stop_capture_task",
        description=(
            "Gracefully stop a running capture task (leave meeting, finalize recording). "
            "Use the capture task_id from the first create_audio_import; then poll get_task on that id. "
            "Do not start a new create_audio_import for the same meeting. Requires tasks:write."
        ),
    )
    async def stop_capture_task(task_id: str) -> str:
        locale = "en"
        try:
            access = get_access_token()
            if access is None or not access.subject:
                raise ToolError("authentication required")
            claims = access.claims or {}
            scopes = scopes_from_bearer_metadata(
                token_scopes=access.scopes,
                scope_claim=claims.get("scope"),
            )
            with db.SessionLocal() as session:
                ctx = _auth_context_from_token(session, access.subject, scopes)
                locale = ctx.locale
                _mcp_tool_rate_limits("stop_capture_task", access.subject, ctx.locale)
                payload, need_tick = await stop_capture_task_payload(
                    session, ctx, task_id=task_id
                )
                session.commit()
        except PermissionError as exc:
            raise ToolError(str(exc)) from exc
        except ApiError as exc:
            if exc.code == ErrorCode.rate_limited:
                raise ToolError(t(locale, ErrorCode.rate_limited.value)) from exc
            raise
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        if need_tick:
            schedule_locked_tick_asyncio(task_id, refresh_health=False, wait=False)
        return json.dumps(payload, ensure_ascii=False)

    @server.tool(
        name="delete_audio",
        description="Permanently delete an audio item (org admin). Requires audio:write.",
    )
    async def delete_audio(audio_id: str) -> str:
        return await _mcp_json_tool(delete_audio_payload, tool="delete_audio", commit=True)(audio_id=audio_id)

    @server.tool(
        name="list_transcripts",
        description="List transcript metadata (no utterances). Requires transcripts:read.",
    )
    async def list_transcripts(include_hidden: bool = False) -> str:
        return await _mcp_json_tool(list_transcripts_payload, tool="list_transcripts")(include_hidden=include_hidden)

    @server.tool(
        name="get_transcript",
        description="Fetch one transcript with utterances. Requires transcripts:read.",
    )
    async def get_transcript(transcript_id: str) -> str:
        return await _mcp_json_tool(get_transcript_payload, tool="get_transcript")(transcript_id=transcript_id)

    @server.tool(
        name="update_transcript",
        description="Rename a transcript (owner or org admin). Requires transcripts:write.",
    )
    async def update_transcript(transcript_id: str, title: str) -> str:
        return await _mcp_json_tool(update_transcript_payload, tool="update_transcript", commit=True)(
            transcript_id=transcript_id, title=title
        )

    @server.tool(
        name="delete_transcript",
        description="Permanently delete a transcript (org admin). Requires transcripts:write.",
    )
    async def delete_transcript(transcript_id: str) -> str:
        return await _mcp_json_tool(delete_transcript_payload, tool="delete_transcript", commit=True)(
            transcript_id=transcript_id
        )

    @server.tool(
        name="list_summaries",
        description="List summary metadata (no body text). Requires summaries:read.",
    )
    async def list_summaries(include_hidden: bool = False) -> str:
        return await _mcp_json_tool(list_summaries_payload, tool="list_summaries")(include_hidden=include_hidden)

    @server.tool(
        name="get_summary",
        description="Fetch one summary including body text. Requires summaries:read.",
    )
    async def get_summary(summary_id: str) -> str:
        return await _mcp_json_tool(get_summary_payload, tool="get_summary")(summary_id=summary_id)

    @server.tool(
        name="create_transcribe",
        description=(
            "Queue transcribe task for existing audio (async; returns task JSON with task_id). "
            "audio_id must come from get_task (import/capture success), create_audio_upload (id), or list_audios — "
            "verify with get_audio first. Poll get_task on the returned task_id until success (transcript_id). "
            "After capture/import without upfront transcribe, use this — never re-call create_audio_import with "
            "the meeting URL. not found: bad audio_id or file not ready. Requires tasks:write."
        ),
    )
    async def create_transcribe(
        audio_id: str,
        skill_ids: list[str] | None = None,
    ) -> str:
        return await _mcp_json_tool(
            create_transcribe_payload,
            tool="create_transcribe",
            commit=True,
            post_commit=_schedule_task,
        )(audio_id=audio_id, skill_ids=skill_ids)

    @server.tool(
        name="create_summary",
        description=(
            "Queue summarize task for a transcript (async; returns task JSON). "
            "Requires tasks:write."
        ),
    )
    async def create_summary(transcript_id: str, skill_ids: list[str]) -> str:
        return await _mcp_json_tool(
            create_summary_payload,
            tool="create_summary",
            commit=True,
            post_commit=_schedule_task,
        )(transcript_id=transcript_id, skill_ids=skill_ids)

    @server.tool(
        name="update_summary",
        description="Edit summary title and/or body (owner or org admin). Requires summaries:write.",
    )
    async def update_summary(
        summary_id: str,
        title: str | None = None,
        body: str | None = None,
    ) -> str:
        return await _mcp_json_tool(update_summary_payload, tool="update_summary", commit=True)(
            summary_id=summary_id, title=title, body=body
        )

    @server.tool(
        name="delete_summary",
        description="Delete a summary (owner or org admin). Requires summaries:write.",
    )
    async def delete_summary(summary_id: str) -> str:
        return await _mcp_json_tool(delete_summary_payload, tool="delete_summary", commit=True)(
            summary_id=summary_id
        )

    @server.tool(
        name="list_skills",
        description="List skills visible to you (base, org, personal, shared). Requires skills:read.",
    )
    async def list_skills(scope: str | None = None) -> str:
        return await _mcp_json_tool(list_skills_payload, tool="list_skills")(scope=scope)

    @server.tool(
        name="get_skill",
        description="Fetch one skill by id (includes body). Requires skills:read.",
    )
    async def get_skill(skill_id: str) -> str:
        return await _mcp_json_tool(get_skill_payload, tool="get_skill")(skill_id=skill_id)

    @server.tool(
        name="create_skill",
        description=(
            "Create a skill in catalog self (default), org (org admin), or base (instance admin). "
            "Requires skills:write."
        ),
    )
    async def create_skill(name: str, body: str, catalog: str = "self") -> str:
        return await _mcp_json_tool(create_skill_payload, tool="create_skill", commit=True)(
            name=name, body=body, catalog=catalog
        )

    @server.tool(
        name="update_skill",
        description=(
            "Update skill name and body (personal owner, org admin, instance admin for base). "
            "Requires skills:write."
        ),
    )
    async def update_skill(skill_id: str, name: str, body: str) -> str:
        return await _mcp_json_tool(update_skill_payload, tool="update_skill", commit=True)(
            skill_id=skill_id, name=name, body=body
        )

    @server.tool(
        name="delete_skill",
        description="Delete a skill when permitted for its catalog. Requires skills:write.",
    )
    async def delete_skill(skill_id: str) -> str:
        return await _mcp_json_tool(delete_skill_payload, tool="delete_skill", commit=True)(skill_id=skill_id)

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


def _bearer_token_from_scope(scope: dict) -> str | None:
    auth = asgi_headers(scope).get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    return token or None


def _mcp_transport_user_id(token: str | None) -> str | None:
    if not token:
        return None
    from app.services.oauth_provider import looks_like_jwt, verify_access_token

    if not looks_like_jwt(token):
        return None
    db.get_engine()
    if db.SessionLocal is None:
        return None
    with db.SessionLocal() as session:
        payload = verify_access_token(session, token)
        if payload is None:
            return None
        sub = payload.get("sub")
        return str(sub) if sub else None


def _mcp_transport_rate_limit(scope: dict) -> ApiError | None:
    method = scope.get("method", "GET")
    if method == "OPTIONS":
        return None
    ip = client_ip_from_asgi_scope(scope)
    user_id = _mcp_transport_user_id(_bearer_token_from_scope(scope))
    db.get_engine()
    if db.SessionLocal is None:
        return None
    try:
        with db.SessionLocal() as session:
            enforce_api_limits(user_id, ip, get_rate_limits(session), "en")
    except ApiError as exc:
        return exc
    return None


async def _asgi_json_response(
    send,
    status: int,
    body: dict,
    headers: dict[str, str] | None = None,
) -> None:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    header_list = [[b"content-type", b"application/json; charset=utf-8"]]
    for key, value in (headers or {}).items():
        header_list.append([key.lower().encode("latin-1"), value.encode("latin-1")])
    header_list.append([b"content-length", str(len(payload)).encode("ascii")])
    await send({"type": "http.response.start", "status": status, "headers": header_list})
    await send({"type": "http.response.body", "body": payload})


class McpHttpHandler:
    """Streamable HTTP MCP at /mcp (canonical resource URL has no trailing slash)."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await get_mcp_starlette_app()(scope, receive, send)
            return
        path = scope.get("path", "")
        is_mcp = path == "/mcp" or path.startswith("/mcp/")
        if is_mcp:
            limited = _mcp_transport_rate_limit(scope)
            if limited is not None:
                await _asgi_json_response(
                    send,
                    limited.status_code,
                    limited.detail if isinstance(limited.detail, dict) else {},
                    limited.headers,
                )
                return
        if is_mcp:
            inner = path.removeprefix("/mcp") or "/"
            scope = dict(scope)
            scope["path"] = inner
            scope["root_path"] = (scope.get("root_path") or "") + "/mcp"
        ip_token = _mcp_client_ip.set(client_ip_from_asgi_scope(scope))
        try:
            await get_mcp_starlette_app()(scope, receive, send)
        finally:
            _mcp_client_ip.reset(ip_token)


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

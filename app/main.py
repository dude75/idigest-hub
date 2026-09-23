"""HTTP API хаба. Uvicorn — один процесс."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.cookies import ensure_csrf_cookie, response_sets_csrf_cookie, set_session_cookie
from app.constants import COOKIE_NAME, CSRF_COOKIE_NAME
from app.csrf import enforce_csrf
from app.deps import cached_session_ttl_sec
from app.db import get_engine, init_database
from app.errors import ErrorCode, error_payload
from app.i18n import negotiate_locale, t
from app.logging_setup import setup_logging
from app.metrics_auth import require_metrics_token
from app.openapi import configure_openapi
from app.prometheus_metrics import (
    CONTENT_TYPE,
    create_metrics,
    http_path_template,
    observe_http,
    render,
    set_active,
)
from app.routers import auth, crypto, instance, library, oauth, org, public, skills, tasks
from app.services.dispatcher import dispatcher_loop
from app.rate_limit import rate_limit_sweeper
from app.version import read_version

log = logging.getLogger("app")
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

SpaResolution = Literal["not_found", "index"] | Path


def resolve_spa_path(web_dist: Path, full_path: str) -> SpaResolution:
    if full_path.startswith("api/"):
        return "not_found"
    if full_path.startswith((".well-known/", "oauth/")) or full_path == "mcp" or full_path.startswith("mcp/"):
        return "not_found"
    if full_path in {"docs", "redoc", "openapi.json"} or full_path.startswith(("docs/", "redoc/")):
        return "not_found"
    candidate = (web_dist / full_path).resolve()
    if not candidate.is_relative_to(web_dist.resolve()):
        return "not_found"
    if full_path and candidate.is_file():
        return candidate
    return "index"


def spa_response(web_dist: Path, full_path: str) -> FileResponse | JSONResponse:
    resolved = resolve_spa_path(web_dist, full_path)
    if resolved == "not_found":
        return JSONResponse(
            status_code=404,
            content=error_payload(ErrorCode.not_found, t("en", "not_found")),
        )
    if resolved == "index":
        return FileResponse(web_dist / "index.html", headers={"Cache-Control": "no-cache"})
    return FileResponse(resolved)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings)
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    init_database(engine)
    from app.services.storage_gc import drain_all_pending_storage_deletes

    await asyncio.to_thread(drain_all_pending_storage_deletes)
    metrics = create_metrics(settings)
    set_active(metrics)
    metrics.bind(settings=settings)
    app.state.metrics = metrics
    stop_event = asyncio.Event()
    task = asyncio.create_task(dispatcher_loop(stop_event))
    rate_limit_task = asyncio.create_task(rate_limit_sweeper(stop_event))
    app.state.dispatcher_stop = stop_event
    app.state.dispatcher_task = task
    app.state.rate_limit_task = rate_limit_task
    log.info("service start")
    from app.services.mcp_integration import get_mcp_starlette_app, mcp_enabled, mcp_session_manager_lifecycle

    try:
        async with mcp_session_manager_lifecycle():
            if mcp_enabled():
                try:
                    get_mcp_starlette_app()
                except RuntimeError as exc:
                    log.warning("MCP unavailable at startup: %s", exc)
            yield
    finally:
        set_active(None)
        stop_event.set()
        task.cancel()
        rate_limit_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await rate_limit_task
        except asyncio.CancelledError:
            pass
        log.info("service stop")


def _locale(request: Request) -> str:
    return negotiate_locale(request.headers.get("accept-language"))


def _register_middleware(application: FastAPI) -> None:
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and detail.get("status") == "error":
            return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
        locale = _locale(request)
        code = ErrorCode.not_found if exc.status_code == 404 else ErrorCode.validation_error
        return JSONResponse(status_code=exc.status_code, content=error_payload(code, t(locale, code.value)))

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
        locale = _locale(request)
        return JSONResponse(
            status_code=400,
            content=error_payload(ErrorCode.validation_error, t(locale, ErrorCode.validation_error.value)),
        )

    @application.middleware("http")
    async def csrf_middleware(request: Request, call_next):
        blocked = await enforce_csrf(request)
        if blocked is not None:
            return blocked
        return await call_next(request)

    @application.middleware("http")
    async def prometheus_http_middleware(request: Request, call_next):
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)
        started = time.perf_counter()
        status_code = 500
        route = http_path_template(request)
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            observe_http(request.method, route, status_code, time.perf_counter() - started)

    @application.middleware("http")
    async def slide_session_cookie(request: Request, call_next):
        response = await call_next(request)
        token = request.cookies.get(COOKIE_NAME)
        if not token or response.status_code >= 400:
            return response
        set_cookie_already = False
        for key, value in response.raw_headers:
            if key.lower() == b"set-cookie" and COOKIE_NAME.encode() in value:
                set_cookie_already = True
                break
        max_age = cached_session_ttl_sec()
        if not set_cookie_already:
            set_session_cookie(response, token, max_age=max_age)
        if not response_sets_csrf_cookie(response):
            ensure_csrf_cookie(
                response,
                has_session=True,
                csrf_present=bool(request.cookies.get(CSRF_COOKIE_NAME)),
                max_age=max_age,
            )
        return response


def _register_routes(application: FastAPI) -> None:
    @application.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok", "version": read_version()}

    @application.get("/metrics")
    def metrics(_: None = Depends(require_metrics_token)) -> Response:
        return Response(content=render(), media_type=CONTENT_TYPE)

    application.include_router(oauth.router)
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(instance.router, prefix="/api/v1")
    application.include_router(crypto.router, prefix="/api/v1")
    application.include_router(org.router, prefix="/api/v1")
    application.include_router(library.router, prefix="/api/v1")
    application.include_router(tasks.router, prefix="/api/v1")
    application.include_router(skills.router, prefix="/api/v1")
    application.include_router(public.router, prefix="/api/v1")

    from app.services.mcp_integration import LazyMcpMount, mcp_enabled

    if mcp_enabled():
        application.mount("/mcp", LazyMcpMount())

    if WEB_DIST.is_dir():
        assets = WEB_DIST / "assets"
        if assets.is_dir():
            application.mount("/assets", StaticFiles(directory=assets), name="assets")

        @application.get("/{full_path:path}")
        def spa(full_path: str):
            return spa_response(WEB_DIST, full_path)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    openapi_enabled = resolved.OPENAPI_ENABLED
    application = FastAPI(
        title="idigest-hub",
        version=read_version(),
        lifespan=lifespan,
        swagger_ui_parameters={"persistAuthorization": True},
        docs_url="/docs" if openapi_enabled else None,
        redoc_url="/redoc" if openapi_enabled else None,
        openapi_url="/openapi.json" if openapi_enabled else None,
    )
    configure_openapi(application)
    _register_middleware(application)
    _register_routes(application)
    return application


app = create_app()

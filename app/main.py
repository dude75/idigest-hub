"""HTTP API хаба. Uvicorn — один процесс."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.cookies import set_session_cookie
from app.constants import COOKIE_NAME
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
from app.routers import auth, instance, library, org, skills, tasks
from app.services.dispatcher import dispatcher_loop
from app.rate_limit import rate_limit_sweeper
from app.version import read_version

log = logging.getLogger("app")
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings)
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    init_database(engine)
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
    try:
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


app = FastAPI(
    title="idigest-hub",
    version=read_version(),
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)
configure_openapi(app)


def _locale(request: Request) -> str:
    return negotiate_locale(request.headers.get("accept-language"))


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and detail.get("status") == "error":
        return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
    locale = _locale(request)
    code = ErrorCode.not_found if exc.status_code == 404 else ErrorCode.validation_error
    return JSONResponse(status_code=exc.status_code, content=error_payload(code, t(locale, code.value)))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
    locale = _locale(request)
    return JSONResponse(
        status_code=400,
        content=error_payload(ErrorCode.validation_error, t(locale, ErrorCode.validation_error.value)),
    )


@app.middleware("http")
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


@app.middleware("http")
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
    if not set_cookie_already:
        set_session_cookie(response, token)
    return response


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "version": read_version()}


@app.get("/metrics")
def metrics(_: None = Depends(require_metrics_token)) -> Response:
    return Response(content=render(), media_type=CONTENT_TYPE)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(instance.router, prefix="/api/v1")
app.include_router(org.router, prefix="/api/v1")
app.include_router(library.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(skills.router, prefix="/api/v1")


if WEB_DIST.is_dir():
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content=error_payload(ErrorCode.not_found, t("en", "not_found")),
            )
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})

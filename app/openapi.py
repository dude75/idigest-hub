"""OpenAPI: схемы авторизации для Swagger / ReDoc."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.constants import COOKIE_NAME

# Публичные эндпоинты — без lock-иконки и без security в OpenAPI.
PUBLIC_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("get", "/api/v1/health"),
        ("get", "/api/v1/setup/status"),
        ("post", "/api/v1/setup"),
        ("get", "/api/v1/auth/signup-tariffs"),
        ("post", "/api/v1/auth/signup"),
        ("post", "/api/v1/auth/login"),
        ("post", "/api/v1/auth/password/reset/request"),
        ("post", "/api/v1/auth/password/reset/confirm"),
        ("post", "/api/v1/auth/logout"),
    }
)

SECURITY_SCHEMES = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "description": (
            "API token from POST /api/v1/auth/tokens (prefix `idg_`). "
            "Send as `Authorization: Bearer <token>`."
        ),
    },
    "SessionCookie": {
        "type": "apiKey",
        "in": "cookie",
        "name": COOKIE_NAME,
        "description": "Session cookie `hub_session` set by login or signup.",
    },
}

# Любой из способов (Bearer или cookie) достаточен.
AUTH_SECURITY = [{"BearerAuth": []}, {"SessionCookie": []}]


def configure_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description=getattr(app, "description", None),
        )
        components = schema.setdefault("components", {})
        components["securitySchemes"] = SECURITY_SCHEMES
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.startswith("x-"):
                    continue
                if (method.lower(), path) not in PUBLIC_OPERATIONS:
                    operation["security"] = AUTH_SECURITY
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

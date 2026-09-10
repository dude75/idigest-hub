"""Bearer auth for GET /metrics (Prometheus scrape)."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.config import get_settings


def metrics_token_is_valid(authorization: str | None) -> bool:
    settings = get_settings()
    expected = settings.METRICS_TOKEN.strip()
    if not expected:
        return True
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    return authorization[7:].strip() == expected


def require_metrics_token(request: Request) -> None:
    if not metrics_token_is_valid(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail={"status": "error", "error": {"code": "unauthorized"}})

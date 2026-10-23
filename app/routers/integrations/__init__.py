from __future__ import annotations

from app.routers.integrations._router import router
from app.routers.integrations import telegram as telegram  # noqa: F401 — register routes

__all__ = ["router"]

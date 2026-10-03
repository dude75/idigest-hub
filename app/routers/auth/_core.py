"""Auth route registration (split modules)."""

from app.routers.auth._router import router
from app.routers.auth import me, mfa, session, setup, tokens  # noqa: F401

__all__ = ["router"]

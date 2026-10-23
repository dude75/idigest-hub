"""Auth context for Telegram-linked users (internal bot actions)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.deps import AuthContext, load_org_bundle
from app.models import User


def auth_context_for_user(db: Session, user: User) -> AuthContext:
    if user.disabled_at is not None:
        raise ValueError("user disabled")
    org, membership = load_org_bundle(db, user)
    locale = user.locale or "en"
    return AuthContext(
        user=user,
        actor=user,
        org=org,
        membership=membership,
        session=None,
        via_api_token=False,
        locale=locale,
        impersonating=False,
    )

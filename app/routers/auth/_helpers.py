from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    DEFAULT_LOCALE,
    DEFAULT_ROUTE,
    DEFAULT_ROUTES,
    INSTANCE_TABS,
    LEGACY_DEFAULT_ROUTE,
    LEGACY_INSTANCE_ROUTE,
    SECURITY_TABS,
    SUPPORTED_LOCALES,
)
from app.deps import AuthContext
from app.errors import ErrorCode
from app.models import Membership, Organization, Tariff, User
from app.security import verify_password
from app.services.mfa import consume_recovery_code, totp_enabled, verify_user_totp

def _norm_email(email: str) -> str:
    return str(email).strip().lower()


def _locale(value: str) -> str:
    return value if value in SUPPORTED_LOCALES else DEFAULT_LOCALE


def _allowed_default_routes(ctx: AuthContext) -> set[str]:
    routes = {"tasks"}
    if ctx.org:
        routes.update(
            {
                "library/audio",
                "library/transcripts",
                "library/summaries",
                "skills",
                "org",
            }
        )
        if ctx.membership and ctx.membership.role == "org_admin":
            routes.add("stats")
    if ctx.user.is_instance_admin and not ctx.impersonating:
        routes.update(f"instance/{tab}" for tab in INSTANCE_TABS)
        routes.update(f"security/{tab}" for tab in SECURITY_TABS)
    return routes


def _default_route(value: str) -> str:
    if value == LEGACY_DEFAULT_ROUTE:
        value = DEFAULT_ROUTE
    if value == LEGACY_INSTANCE_ROUTE:
        value = "instance/stats"
    return value if value in DEFAULT_ROUTES else DEFAULT_ROUTE


def _login_membership_org(db: Session, user: User) -> tuple[Membership | None, Organization | None]:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    if membership is None:
        return None, None
    org = db.get(Organization, membership.org_id)
    return membership, org



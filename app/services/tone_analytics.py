"""Tone analytics: tariff + user gate and request validation."""

from __future__ import annotations

from app.deps import AuthContext
from app.errors import ApiError, ErrorCode
from app.models import Tariff, User


def resolve_tone_request(*, tariff: Tariff, user: User, requested: bool) -> bool:
    if not requested:
        return False
    if not tariff.tone_analytics_enabled:
        raise ApiError(ErrorCode.validation_error)
    if not user.tone_analytics_enabled:
        raise ApiError(ErrorCode.validation_error)
    return True


def validate_tone_for_ctx(ctx: AuthContext, requested: bool) -> bool:
    org, _ = ctx.require_org()
    return resolve_tone_request(tariff=org.tariff, user=ctx.user, requested=requested)

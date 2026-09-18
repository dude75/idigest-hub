"""Date/time display preferences: instance defaults and per-user overrides."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import InstanceSettings, User

DATE_TIME_FORMATS = frozenset({"eu_24h", "us_12h", "iso", "relative"})
DEFAULT_DATE_TIME_FORMAT = "eu_24h"
DEFAULT_TIMEZONE = "GMT+0"
_GMT_RE = re.compile(r"^GMT([+-])(\d{1,2})$")


def _gmt_options() -> frozenset[str]:
    items = [f"GMT-{hours}" for hours in range(12, 0, -1)]
    items.append("GMT+0")
    items.extend(f"GMT+{hours}" for hours in range(1, 15))
    return frozenset(items)


GMT_TIMEZONES = _gmt_options()


def legacy_timezone_to_gmt(value: str) -> str | None:
    text = (value or "").strip()
    if not text or text.upper() == "UTC":
        return DEFAULT_TIMEZONE
    if text in GMT_TIMEZONES:
        return text
    try:
        offset = datetime.now(ZoneInfo(text)).utcoffset()
    except ZoneInfoNotFoundError:
        return None
    if offset is None:
        return DEFAULT_TIMEZONE
    hours = int(offset.total_seconds() // 3600)
    if hours >= 0:
        return f"GMT+{hours}"
    return f"GMT{hours}"


def normalize_timezone(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return DEFAULT_TIMEZONE
    if text.upper() == "UTC" or text in {"GMT+0", "GMT-0"}:
        return DEFAULT_TIMEZONE
    match = _GMT_RE.match(text)
    if match:
        sign, hours_raw = match.group(1), int(match.group(2))
        if sign == "+" and hours_raw > 14:
            raise ValueError("invalid timezone")
        if sign == "-" and hours_raw > 12:
            raise ValueError("invalid timezone")
        if hours_raw == 0:
            return DEFAULT_TIMEZONE
        normalized = f"GMT{sign}{hours_raw}"
        if normalized not in GMT_TIMEZONES:
            raise ValueError("invalid timezone")
        return normalized
    raise ValueError("invalid timezone")


def normalize_date_time_format(value: str | None) -> str:
    text = (value or "").strip()
    if text in DATE_TIME_FORMATS:
        return text
    return DEFAULT_DATE_TIME_FORMAT


def resolve_date_time_prefs(user: User, settings: InstanceSettings) -> dict[str, Any]:
    instance_format = normalize_date_time_format(settings.date_time_format)
    instance_timezone = normalize_timezone(settings.timezone)
    user_format = (user.date_time_format or "").strip() or None
    user_timezone = (user.timezone or "").strip() or None
    if user_format and user_format not in DATE_TIME_FORMATS:
        user_format = None
    if user_timezone:
        try:
            user_timezone = normalize_timezone(user_timezone)
        except ValueError:
            user_timezone = None
    effective_format = user_format or instance_format
    effective_timezone = user_timezone or instance_timezone
    return {
        "format": effective_format,
        "timezone": effective_timezone,
        "format_source": "user" if user_format else "instance",
        "timezone_source": "user" if user_timezone else "instance",
        "instance_format": instance_format,
        "instance_timezone": instance_timezone,
    }

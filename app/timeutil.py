"""UTC timestamps."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite often returns naive UTC; comparisons must be tz-aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def isoformat_utc(value: datetime | None) -> str | None:
    """Serialize UTC for API/JSON (always ends with Z)."""
    if value is None:
        return None
    dt = as_utc(value)
    text = dt.isoformat(timespec="microseconds")
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text

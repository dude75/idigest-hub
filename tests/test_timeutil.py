from datetime import datetime, timezone

from app.timeutil import isoformat_utc


def test_isoformat_utc_from_aware_datetime():
    dt = datetime(2026, 9, 17, 23, 33, 35, 87736, tzinfo=timezone.utc)
    assert isoformat_utc(dt) == "2026-09-17T23:33:35.087736Z"


def test_isoformat_utc_from_naive_sqlite_datetime():
    dt = datetime(2026, 9, 17, 23, 33, 35, 87736)
    assert isoformat_utc(dt) == "2026-09-17T23:33:35.087736Z"


def test_isoformat_utc_none():
    assert isoformat_utc(None) is None

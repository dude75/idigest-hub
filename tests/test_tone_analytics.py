import pytest

from app.errors import ApiError
from app.models import Tariff, User
from app.services.tone_analytics import resolve_tone_request


def _tariff(**kwargs) -> Tariff:
    t = Tariff(
        id="t1",
        name="T",
        unlimited=True,
        available_on_signup=True,
        price_per_audio_sec=0,
        price_per_1k_summary_chars=0,
        audio_retention_days=0,
        api_enabled=True,
        signup_credit=0,
        max_upload_bytes=1024,
        tone_analytics_enabled=kwargs.get("tone_analytics_enabled", False),
        created_at=__import__("app.timeutil", fromlist=["utcnow"]).utcnow(),
        updated_at=__import__("app.timeutil", fromlist=["utcnow"]).utcnow(),
    )
    return t


def _user(**kwargs) -> User:
    from app.timeutil import utcnow

    return User(
        id="u1",
        email="u@test",
        locale="en",
        tone_analytics_enabled=kwargs.get("tone_analytics_enabled", True),
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def test_resolve_tone_false_when_not_requested():
    assert resolve_tone_request(tariff=_tariff(tone_analytics_enabled=True), user=_user(), requested=False) is False


def test_resolve_tone_true_when_allowed():
    assert resolve_tone_request(tariff=_tariff(tone_analytics_enabled=True), user=_user(), requested=True) is True


def test_resolve_tone_rejects_when_tariff_off():
    with pytest.raises(ApiError):
        resolve_tone_request(tariff=_tariff(tone_analytics_enabled=False), user=_user(), requested=True)


def test_resolve_tone_rejects_when_user_off():
    with pytest.raises(ApiError):
        resolve_tone_request(
            tariff=_tariff(tone_analytics_enabled=True),
            user=_user(tone_analytics_enabled=False),
            requested=True,
        )

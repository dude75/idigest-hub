"""i18n сообщений API: en / ru / es. Локаль из пользователя или Accept-Language."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.constants import DEFAULT_LOCALE, SUPPORTED_LOCALES

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@lru_cache
def _bundle(locale: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{locale}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def negotiate_locale(header: str | None, user_locale: str | None = None) -> str:
    if user_locale and user_locale in SUPPORTED_LOCALES:
        return user_locale
    if not header:
        return DEFAULT_LOCALE
    for part in header.split(","):
        tag = part.split(";")[0].strip().lower()
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE


def t(locale: str, key: str, **kwargs: object) -> str:
    loc = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    template = _bundle(loc).get(key) or _bundle(DEFAULT_LOCALE).get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template

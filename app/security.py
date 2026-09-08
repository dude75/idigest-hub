"""Пароли, сессии, API-токены. Секреты в логи не пишем."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def hash_secret(raw: str) -> str:
    pepper = get_settings().SESSION_SECRET.encode()
    return hashlib.sha256(pepper + raw.encode()).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_api_token() -> str:
    return "idg_" + secrets.token_urlsafe(32)


def new_reset_token() -> str:
    return secrets.token_urlsafe(32)


def random_password() -> str:
    return secrets.token_urlsafe(12)


def compare_digest(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)

"""Fernet at-rest: ключ = SHA-256(HUB_SECRET), как API_TOKEN у воркеров."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().HUB_SECRET
    if not secret:
        raise RuntimeError("HUB_SECRET is empty")
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_str(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_str(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def try_decrypt_str(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return decrypt_str(token)
    except InvalidToken:
        return None

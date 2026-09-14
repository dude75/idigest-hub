"""TOTP (RFC 6238) helpers for local-user 2FA."""

from __future__ import annotations

import pyotp

from app.constants import MFA_TOTP_ISSUER


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=MFA_TOTP_ISSUER)


def verify_code(*, secret: str, code: str) -> bool:
    normalized = (code or "").strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    return pyotp.TOTP(secret).verify(normalized, valid_window=1)

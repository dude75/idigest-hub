"""RSA signing keys for OAuth access tokens (JWT)."""

from __future__ import annotations

import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings, get_settings

log = logging.getLogger("app")

KID = "hub-oauth-1"


def _key_path(settings: Settings) -> Path:
    return Path(settings.DATA_DIR) / "oauth_signing_key.pem"


def _load_pem(settings: Settings) -> bytes:
    inline = (settings.OAUTH_SIGNING_KEY_PEM or "").strip()
    if inline:
        return inline.encode("utf-8")
    path = _key_path(settings)
    if path.is_file():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)
    log.info("generated OAuth signing key at %s", path)
    return pem


def get_private_key():
    settings = get_settings()
    pem = _load_pem(settings)
    return serialization.load_pem_private_key(pem, password=None)


def get_public_jwks() -> dict:
    private_key = get_private_key()
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()
    import base64

    def _b64_uint(val: int) -> str:
        length = (val.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(val.to_bytes(length, "big")).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64_uint(numbers.n),
                "e": _b64_uint(numbers.e),
            }
        ]
    }


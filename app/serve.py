"""Uvicorn launcher: HOST/PORT and optional TLS from `.env`."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from app.config import Settings, get_settings


def uvicorn_kwargs(settings: Settings) -> dict:
    cert = settings.SSL_CERTFILE.strip()
    key = settings.SSL_KEYFILE.strip()
    if bool(cert) != bool(key):
        msg = "SSL_CERTFILE and SSL_KEYFILE must both be set or both be empty"
        raise SystemExit(msg)

    kwargs: dict = {
        "host": settings.HOST,
        "port": settings.PORT,
        "workers": 1,
    }
    if not cert:
        return kwargs

    cert_path = Path(cert)
    key_path = Path(key)
    if not cert_path.is_file():
        raise SystemExit(f"SSL_CERTFILE not found: {cert}")
    if not key_path.is_file():
        raise SystemExit(f"SSL_KEYFILE not found: {key}")

    kwargs["ssl_certfile"] = cert
    kwargs["ssl_keyfile"] = key
    password = settings.SSL_KEYFILE_PASSWORD.strip()
    if password:
        kwargs["ssl_keyfile_password"] = password
    return kwargs


def main() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", **uvicorn_kwargs(settings))


if __name__ == "__main__":
    main()

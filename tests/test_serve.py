"""Uvicorn launcher (app.serve) settings."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.serve import uvicorn_kwargs


def _settings(**overrides: object) -> Settings:
    base = {
        "HUB_SECRET": "test",
        "INSTANCE_BOOTSTRAP_TOKEN": "test",
        "SESSION_SECRET": "test",
        "HOST": "127.0.0.1",
        "PORT": 8080,
        "SSL_CERTFILE": "",
        "SSL_KEYFILE": "",
        "SSL_KEYFILE_PASSWORD": "",
    }
    base.update(overrides)
    return Settings(**base)


def test_uvicorn_kwargs_http_by_default():
    kwargs = uvicorn_kwargs(_settings())
    assert kwargs == {"host": "127.0.0.1", "port": 8080, "workers": 1}


def test_uvicorn_kwargs_tls_when_both_ssl_paths_set(tmp_path: Path):
    cert = tmp_path / "hub.crt"
    key = tmp_path / "hub.key"
    cert.write_text("cert")
    key.write_text("key")

    kwargs = uvicorn_kwargs(
        _settings(
            SSL_CERTFILE=str(cert),
            SSL_KEYFILE=str(key),
            SSL_KEYFILE_PASSWORD="secret",
        )
    )
    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)
    assert kwargs["ssl_keyfile_password"] == "secret"


def test_uvicorn_kwargs_tls_without_password(tmp_path: Path):
    cert = tmp_path / "hub.crt"
    key = tmp_path / "hub.key"
    cert.write_text("cert")
    key.write_text("key")

    kwargs = uvicorn_kwargs(_settings(SSL_CERTFILE=str(cert), SSL_KEYFILE=str(key)))
    assert "ssl_keyfile_password" not in kwargs


def test_uvicorn_kwargs_rejects_cert_only():
    with pytest.raises(SystemExit, match="both be set"):
        uvicorn_kwargs(_settings(SSL_CERTFILE="/tmp/hub.crt"))


def test_uvicorn_kwargs_rejects_key_only():
    with pytest.raises(SystemExit, match="both be set"):
        uvicorn_kwargs(_settings(SSL_KEYFILE="/tmp/hub.key"))


def test_uvicorn_kwargs_missing_cert_file(tmp_path: Path):
    key = tmp_path / "hub.key"
    key.write_text("key")
    missing = tmp_path / "missing.crt"

    with pytest.raises(SystemExit, match="SSL_CERTFILE not found"):
        uvicorn_kwargs(_settings(SSL_CERTFILE=str(missing), SSL_KEYFILE=str(key)))


def test_uvicorn_kwargs_missing_key_file(tmp_path: Path):
    cert = tmp_path / "hub.crt"
    cert.write_text("cert")
    missing = tmp_path / "missing.key"

    with pytest.raises(SystemExit, match="SSL_KEYFILE not found"):
        uvicorn_kwargs(_settings(SSL_CERTFILE=str(cert), SSL_KEYFILE=str(missing)))


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")
def test_uvicorn_kwargs_accepts_openssl_self_signed(tmp_path: Path):
    cert = tmp_path / "hub.crt"
    key = tmp_path / "hub.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-days",
            "1",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )

    kwargs = uvicorn_kwargs(_settings(SSL_CERTFILE=str(cert), SSL_KEYFILE=str(key)))
    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)

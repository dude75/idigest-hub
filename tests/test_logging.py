"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.config import get_settings
from app.db import get_engine, init_database, reset_engine
from app.logging_setup import setup_logging


@pytest.fixture
def logging_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hub.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(log_dir))
    monkeypatch.setenv("LOG_ENABLED", "true")
    get_settings.cache_clear()
    reset_engine()
    yield log_dir
    get_settings.cache_clear()
    reset_engine()


def test_app_logger_survives_init_database(logging_env: Path):
    setup_logging(get_settings())
    init_database(get_engine())

    app_log = logging.getLogger("app")
    assert not app_log.disabled
    assert app_log.handlers

    app_log.info("logging smoke test")
    for handler in app_log.handlers:
        handler.flush()

    log_file = logging_env / "app.log"
    assert log_file.is_file()
    assert "logging smoke test" in log_file.read_text(encoding="utf-8")

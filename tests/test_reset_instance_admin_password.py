"""Break-glass instance admin password reset CLI."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login, open_db, setup_admin

ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = ROOT / "scripts" / "reset_instance_admin_password.py"


def _load_reset_module():
    spec = importlib.util.spec_from_file_location("reset_instance_admin_password", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reset_instance_admin_password(client):
    setup_admin(client)
    mod = _load_reset_module()
    db = open_db()
    try:
        email, plain = mod.reset_instance_admin_password(
            db,
            password="newadminpass1",
            email=ADMIN_EMAIL,
            clear_mfa=False,
            enable=False,
        )
    finally:
        db.close()
    assert email == ADMIN_EMAIL
    assert plain == "newadminpass1"
    login(client, ADMIN_EMAIL, "newadminpass1")


def test_reset_requires_confirm():
    mod = _load_reset_module()
    assert mod.main([]) == 2


def test_reset_email_mismatch(client):
    setup_admin(client)
    mod = _load_reset_module()
    db = open_db()
    try:
        with pytest.raises(SystemExit):
            mod.reset_instance_admin_password(
                db,
                password="newadminpass1",
                email="wrong@example.com",
                clear_mfa=False,
                enable=False,
            )
    finally:
        db.close()
    login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

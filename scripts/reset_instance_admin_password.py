#!/usr/bin/env python3
"""Break-glass reset of the instance admin password (requires host/DB access and app secrets)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _prepare_import_path() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def resolve_instance_admin(db):
    from sqlalchemy import select

    from app.deps import get_instance_settings
    from app.models import User

    settings = get_instance_settings(db)
    if not settings.bootstrap_done:
        raise SystemExit("bootstrap not done; create the instance admin via POST /api/v1/setup")
    user = None
    if settings.instance_admin_user_id:
        user = db.get(User, settings.instance_admin_user_id)
    if user is None or not user.is_instance_admin:
        user = db.scalar(select(User).where(User.is_instance_admin.is_(True)))
    if user is None:
        raise SystemExit("no instance admin user found in the database")
    return user


def reset_instance_admin_password(
    db,
    *,
    password: str | None,
    email: str | None,
    clear_mfa: bool,
    enable: bool,
) -> tuple[str, str]:
    """Returns (admin_email, password_used)."""
    from app.security import hash_password, random_password
    from app.services.audit import write_audit
    from app.services.auth_helpers import revoke_user_auth
    from app.services.mfa import disable_totp, totp_configured
    from app.timeutil import utcnow

    user = resolve_instance_admin(db)
    if email is not None and user.email.lower() != email.strip().lower():
        raise SystemExit(f"email mismatch: expected {user.email!r}, got {email!r}")

    plain = password if password is not None else random_password()
    if len(plain) < 8:
        raise SystemExit("password must be at least 8 characters")

    now = utcnow()
    user.password_hash = hash_password(plain)
    user.must_change_password = False
    user.password_changed_at = now
    user.updated_at = now
    if enable and user.disabled_at is not None:
        user.disabled_at = None
    if clear_mfa and totp_configured(user):
        disable_totp(db, user)
    revoke_user_auth(db, user.id)
    write_audit(
        db,
        "user.password_reset",
        actor_id=None,
        payload={
            "source": "cli",
            "user_id": user.id,
            "email": user.email,
            "clear_mfa": clear_mfa,
            "enable": enable,
        },
    )
    db.commit()
    return user.email, plain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset the instance admin password (offline break-glass; requires DATABASE_URL and secrets from .env).",
    )
    parser.add_argument(
        "--password",
        "-p",
        help="New password (min 8 chars). If omitted, a random password is generated and printed once.",
    )
    parser.add_argument(
        "--email",
        help="Verify the instance admin email before resetting (recommended).",
    )
    parser.add_argument(
        "--clear-mfa",
        action="store_true",
        help="Clear TOTP 2FA and recovery codes for the instance admin.",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Re-enable the account if it was disabled (clears disabled_at).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag to confirm this operation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.confirm:
        print("Refusing to run without --confirm (break-glass password reset).", file=sys.stderr)
        return 2

    _prepare_import_path()
    from app import db as hub_db

    hub_db.init_database(hub_db.get_engine())
    assert hub_db.SessionLocal is not None
    with hub_db.SessionLocal() as db:
        email, plain = reset_instance_admin_password(
            db,
            password=args.password,
            email=args.email,
            clear_mfa=args.clear_mfa,
            enable=args.enable,
        )
    print(f"instance admin password reset for {email}")
    print(plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

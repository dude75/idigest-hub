"""convert stored timezones to GMT offsets

Revision ID: n4d5e6f7a8b9
Revises: m3c4d5e6f7a8
Create Date: 2026-09-16 16:12:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "m3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_gmt(value: str | None) -> str:
    from app.datetime_format import DEFAULT_TIMEZONE, legacy_timezone_to_gmt

    return legacy_timezone_to_gmt(value or DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE


def upgrade() -> None:
    conn = op.get_bind()
    for row_id, timezone in conn.execute(sa.text("SELECT id, timezone FROM instance_settings")).fetchall():
        conn.execute(
            sa.text("UPDATE instance_settings SET timezone = :tz WHERE id = :id"),
            {"tz": _to_gmt(timezone), "id": row_id},
        )
    for user_id, timezone in conn.execute(
        sa.text("SELECT id, timezone FROM users WHERE timezone IS NOT NULL")
    ).fetchall():
        conn.execute(
            sa.text("UPDATE users SET timezone = :tz WHERE id = :id"),
            {"tz": _to_gmt(timezone), "id": user_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE instance_settings SET timezone = 'UTC' WHERE timezone = 'GMT+0'"))
    conn.execute(sa.text("UPDATE users SET timezone = 'UTC' WHERE timezone = 'GMT+0'"))

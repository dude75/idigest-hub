"""soft rate limit defaults (enable per-IP limits)

Revision ID: o5e6f7a8b9c0
Revises: n4d5e6f7a8b9
Create Date: 2026-09-17 11:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "n4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Old factory defaults from e1b4c7d902fa → new soft defaults.
_FIELD_UPDATES: tuple[tuple[str, int, int], ...] = (
    ("rate_limit_login_ip", 0, 60),
    ("rate_limit_signup_ip", 0, 20),
    ("rate_limit_reset_email", 10, 3),
    ("rate_limit_reset_ip", 0, 10),
    ("rate_limit_reset_confirm_ip", 0, 30),
    ("rate_limit_setup_ip", 0, 5),
    ("rate_limit_api_ip", 0, 300),
    ("rate_limit_api_tasks_ip", 0, 60),
)


def upgrade() -> None:
    for column, old_value, new_value in _FIELD_UPDATES:
        op.execute(
            sa.text(f"UPDATE instance_settings SET {column} = :new WHERE {column} = :old").bindparams(
                new=new_value,
                old=old_value,
            )
        )

    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.alter_column("rate_limit_login_ip", server_default="60")
        batch_op.alter_column("rate_limit_signup_ip", server_default="20")
        batch_op.alter_column("rate_limit_reset_email", server_default="3")
        batch_op.alter_column("rate_limit_reset_ip", server_default="10")
        batch_op.alter_column("rate_limit_reset_confirm_ip", server_default="30")
        batch_op.alter_column("rate_limit_setup_ip", server_default="5")
        batch_op.alter_column("rate_limit_api_ip", server_default="300")
        batch_op.alter_column("rate_limit_api_tasks_ip", server_default="60")


def downgrade() -> None:
    with op.batch_alter_table("instance_settings", schema=None) as batch_op:
        batch_op.alter_column("rate_limit_api_tasks_ip", server_default="0")
        batch_op.alter_column("rate_limit_api_ip", server_default="0")
        batch_op.alter_column("rate_limit_setup_ip", server_default="0")
        batch_op.alter_column("rate_limit_reset_confirm_ip", server_default="0")
        batch_op.alter_column("rate_limit_reset_ip", server_default="0")
        batch_op.alter_column("rate_limit_reset_email", server_default="10")
        batch_op.alter_column("rate_limit_signup_ip", server_default="0")
        batch_op.alter_column("rate_limit_login_ip", server_default="0")

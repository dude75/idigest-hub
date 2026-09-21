"""Capture worker settings and org Jitsi host maps."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instance_settings",
        sa.Column("capture_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "instance_settings",
        sa.Column("capture_allowed_connectors_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "worker_nodes",
        sa.Column("capture_connectors_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "org_capture_jitsi_hosts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("jwt_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("jwt_app_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["worker_id"], ["worker_nodes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "host", name="uq_org_capture_jitsi_host"),
    )
    op.create_index("ix_org_capture_jitsi_hosts_org", "org_capture_jitsi_hosts", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_org_capture_jitsi_hosts_org", table_name="org_capture_jitsi_hosts")
    op.drop_table("org_capture_jitsi_hosts")
    op.drop_column("worker_nodes", "capture_connectors_json")
    op.drop_column("instance_settings", "capture_allowed_connectors_json")
    op.drop_column("instance_settings", "capture_enabled")

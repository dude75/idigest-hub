"""audios.source_url for imported files

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
Create Date: 2026-09-15 17:40:00.000000

"""
from __future__ import annotations

import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "k1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _meta_url(meta: Any) -> str:
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return ""
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("url") or "").strip()[:2048]


def upgrade() -> None:
    with op.batch_alter_table("audios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(length=2048), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT audio_id, meta_json FROM tasks "
            "WHERE type = 'import' AND audio_id IS NOT NULL"
        )
    ).fetchall()
    for audio_id, meta_json in rows:
        url = _meta_url(meta_json)
        if not url:
            continue
        conn.execute(
            sa.text(
                "UPDATE audios SET source_url = :url "
                "WHERE id = :id AND source_url IS NULL"
            ),
            {"url": url, "id": audio_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("audios", schema=None) as batch_op:
        batch_op.drop_column("source_url")

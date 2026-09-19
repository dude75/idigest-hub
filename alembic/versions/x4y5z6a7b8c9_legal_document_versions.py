"""immutable legal document version snapshots

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-09-19 14:00:00.000000

"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "w3x4y5z6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOCUMENTS: tuple[tuple[str, str], ...] = (
    ("user_agreement", "user_agreement"),
    ("personal_data_consent", "personal_data_consent"),
    ("privacy_policy", "privacy_policy"),
)


def upgrade() -> None:
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_key", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("text_ru", sa.Text(), nullable=True),
        sa.Column("text_es", sa.Text(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key", "version", name="uq_legal_document_versions_key_version"),
    )
    with op.batch_alter_table("legal_document_versions", schema=None) as batch_op:
        batch_op.create_index("ix_legal_document_versions_document_key", ["document_key"], unique=False)

    conn = op.get_bind()
    settings = conn.execute(sa.text("SELECT * FROM instance_settings LIMIT 1")).mappings().first()
    if settings is None:
        return

    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    for key, prefix in _DOCUMENTS:
        version = int(settings.get(f"{prefix}_version") or 0)
        if version <= 0:
            continue
        texts = [
            (settings.get(f"{prefix}_text_en") or "").strip(),
            (settings.get(f"{prefix}_text_ru") or "").strip(),
            (settings.get(f"{prefix}_text_es") or "").strip(),
        ]
        if not any(texts):
            continue
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "document_key": key,
                "version": version,
                "text_en": texts[0] or None,
                "text_ru": texts[1] or None,
                "text_es": texts[2] or None,
                "published": bool(settings.get(f"{prefix}_published", True)),
                "created_at": now,
                "created_by_user_id": None,
            }
        )

    if rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO legal_document_versions
                    (id, document_key, version, text_en, text_ru, text_es, published, created_at, created_by_user_id)
                VALUES
                    (:id, :document_key, :version, :text_en, :text_ru, :text_es, :published, :created_at, :created_by_user_id)
                """
            ),
            rows,
        )


def downgrade() -> None:
    op.drop_table("legal_document_versions")

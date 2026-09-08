"""Модели БД (ТЗ §11). UUID как строки, деньги Numeric(12,2), без deleted_at."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class InstanceSettings(Base):
    __tablename__ = "instance_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bootstrap_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    instance_admin_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    allow_new_orgs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public_base_url: Mapped[str | None] = mapped_column(String(512))
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_user: Mapped[str | None] = mapped_column(String(255))
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text)
    smtp_from: Mapped[str | None] = mapped_column(String(255))
    smtp_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    asr_model: Mapped[str] = mapped_column(String(32), default="whisper", nullable=False)
    diarization_model: Mapped[str | None] = mapped_column(String(32), default="pyannote")
    rate_limit_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_login_email: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    rate_limit_login_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_login_global: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    rate_limit_signup_email: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    rate_limit_signup_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_signup_global: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    rate_limit_reset_email: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    rate_limit_reset_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_reset_global: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    rate_limit_reset_confirm_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_reset_confirm_global: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    rate_limit_setup_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_setup_global: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    rate_limit_api_user: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    rate_limit_api_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_api_global: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    rate_limit_api_tasks_user: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    rate_limit_api_tasks_ip: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_instance_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    membership: Mapped[Membership | None] = relationship(back_populates="user", uselist=False)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_personal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tariff_id: Mapped[str] = mapped_column(String(36), ForeignKey("tariffs.id"), nullable=False, index=True)
    password_ttl_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tariff: Mapped[Tariff] = relationship()
    memberships: Mapped[list[Membership]] = relationship(back_populates="org")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    user: Mapped[User] = relationship(back_populates="membership")
    org: Mapped[Organization] = relationship(back_populates="memberships")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    impersonate_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    unlimited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_on_signup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    price_per_audio_sec: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    price_per_summarize_job: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    price_per_1k_summary_chars: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    audio_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    signup_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    max_upload_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkerNode(Base):
    __tablename__ = "worker_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_health: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_seen_version: Mapped[str | None] = mapped_column(String(64))
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    org_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Audio(Base):
    __tablename__ = "audios"
    __table_args__ = (
        Index("ix_audios_org_created", "org_id", "created_at"),
        Index("ix_audios_owner_created", "owner_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_sec: Mapped[float | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_org_created", "org_id", "created_at"),
        Index("ix_transcripts_owner_created", "owner_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    source_audio_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("audios.id", ondelete="SET NULL")
    )
    utterances_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Summary(Base):
    __tablename__ = "summaries"
    __table_args__ = (
        Index("ix_summaries_org_created", "org_id", "created_at"),
        Index("ix_summaries_owner_created", "owner_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    source_transcript_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transcripts.id", ondelete="SET NULL")
    )
    skill_ids_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    body_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HiddenItem(Base):
    __tablename__ = "hidden_items"
    __table_args__ = (UniqueConstraint("user_id", "object_type", "object_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)


class Share(Base):
    __tablename__ = "shares"
    __table_args__ = (
        UniqueConstraint("object_type", "object_id", "to_user_id"),
        Index("ix_shares_to", "to_user_id", "object_type"),
        Index("ix_shares_from", "from_user_id", "object_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_org_status", "org_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    audio_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("audios.id", ondelete="SET NULL"))
    transcript_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transcripts.id", ondelete="SET NULL")
    )
    skill_ids_json: Mapped[list[Any] | None] = mapped_column(JSON)
    worker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("worker_nodes.id"))
    worker_task_id: Mapped[str | None] = mapped_column(String(64))
    produced_transcript_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transcripts.id", ondelete="SET NULL")
    )
    produced_summary_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("summaries.id", ondelete="SET NULL")
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    snap_unlimited: Mapped[bool] = mapped_column(Boolean, nullable=False)
    snap_price_per_audio_sec: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    snap_price_per_summarize_job: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    snap_price_per_1k_summary_chars: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    snap_max_upload_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    snap_asr_model: Mapped[str | None] = mapped_column(String(32))
    snap_diarization_model: Mapped[str | None] = mapped_column(String(32))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retry_without_timeout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_persist: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String(64))
    billed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    audio_sec: Mapped[float | None] = mapped_column()
    summary_chars: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unlimited_skip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    on_behalf_of_user_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

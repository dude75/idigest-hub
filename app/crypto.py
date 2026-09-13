"""Envelope encryption: KEK = SHA-256(HUB_SECRET), DEK stored wrapped in DB."""

from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DataEncryptionKey, EncryptionJob, InstanceSettings, Organization, Summary, Transcript, WorkerNode

V1_PREFIX = "v1:"
_DEK_ID_RE = re.compile(r"^[0-9a-f-]{36}$")

EncryptedColumn = tuple[str, str]


ENCRYPTED_COLUMNS: list[EncryptedColumn] = [
    ("worker_nodes", "api_token_encrypted"),
    ("instance_settings", "smtp_password_encrypted"),
    ("instance_settings", "download_proxy_password_encrypted"),
    ("organizations", "sso_client_secret_encrypted"),
    ("transcripts", "utterances_encrypted"),
    ("summaries", "body_encrypted"),
]


def _kek_fernet(secret: str | None = None) -> Fernet:
    raw = secret if secret is not None else get_settings().HUB_SECRET
    if not raw:
        raise RuntimeError("HUB_SECRET is empty")
    digest = hashlib.sha256(raw.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _legacy_fernet() -> Fernet:
    return _kek_fernet()


def wrap_dek(raw_dek: bytes) -> str:
    return _kek_fernet().encrypt(raw_dek).decode()


def _try_unwrap_with_current(wrapped: str) -> bytes | None:
    try:
        return _kek_fernet().decrypt(wrapped.encode())
    except InvalidToken:
        return None


def can_unwrap_dek(wrapped: str) -> bool:
    if _try_unwrap_with_current(wrapped) is not None:
        return True
    previous = (get_settings().HUB_SECRET_PREV or "").strip()
    if not previous:
        return False
    try:
        _kek_fernet(previous).decrypt(wrapped.encode())
        return True
    except InvalidToken:
        return False


def unwrap_dek(wrapped: str) -> bytes:
    raw = _try_unwrap_with_current(wrapped)
    if raw is not None:
        return raw
    previous = get_settings().HUB_SECRET_PREV
    if previous:
        return _kek_fernet(previous).decrypt(wrapped.encode())
    raise InvalidToken


def dek_needs_rewrap(wrapped: str) -> bool:
    if _try_unwrap_with_current(wrapped) is not None:
        return False
    previous = get_settings().HUB_SECRET_PREV
    if not previous:
        return False
    try:
        _kek_fernet(previous).decrypt(wrapped.encode())
    except InvalidToken:
        return False
    return True


def parse_token(token: str) -> tuple[str | None, str]:
    if token.startswith(V1_PREFIX):
        rest = token[len(V1_PREFIX) :]
        dek_id, sep, inner = rest.partition(":")
        if sep and _DEK_ID_RE.match(dek_id):
            return dek_id, inner
    return None, token


def token_dek_id(token: str | None) -> str | None:
    if not token:
        return None
    dek_id, _ = parse_token(token)
    return dek_id


def _dek_fernet(db: Session, dek_id: str) -> Fernet:
    row = db.get(DataEncryptionKey, dek_id)
    if row is None:
        raise RuntimeError(f"DEK not found: {dek_id}")
    raw = unwrap_dek(row.wrapped_key)
    return Fernet(raw)


def get_active_dek(db: Session) -> tuple[str, bytes]:
    settings = db.get(InstanceSettings, 1)
    if settings is None or not settings.active_dek_id:
        raise RuntimeError("no active DEK")
    row = db.get(DataEncryptionKey, settings.active_dek_id)
    if row is None:
        raise RuntimeError("active DEK missing")
    return row.id, unwrap_dek(row.wrapped_key)


def create_dek(db: Session, *, status: str = "active") -> DataEncryptionKey:
    from app.models import new_id
    from app.timeutil import utcnow

    raw_dek = Fernet.generate_key()
    now = utcnow()
    row = DataEncryptionKey(
        id=new_id(),
        wrapped_key=wrap_dek(raw_dek),
        status=status,
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row


def encrypt_with_dek(plain: str, dek_id: str, raw_dek: bytes) -> str:
    token = Fernet(raw_dek).encrypt(plain.encode()).decode()
    return f"{V1_PREFIX}{dek_id}:{token}"


def encrypt_str(plain: str, db: Session) -> str:
    dek_id, raw_dek = get_active_dek(db)
    return encrypt_with_dek(plain, dek_id, raw_dek)


def decrypt_str(token: str, db: Session) -> str:
    dek_id, inner = parse_token(token)
    if dek_id is None:
        return _legacy_fernet().decrypt(inner.encode()).decode()
    return _dek_fernet(db, dek_id).decrypt(inner.encode()).decode()


def try_decrypt_str(token: str | None, db: Session) -> str | None:
    if not token:
        return None
    try:
        return decrypt_str(token, db)
    except InvalidToken:
        return None


def count_deks_needing_rewrap(db: Session) -> int:
    return sum(1 for row in db.scalars(select(DataEncryptionKey)).all() if dek_needs_rewrap(row.wrapped_key))


def rewrap_pending_deks(db: Session) -> int:
    """Re-wrap DEKs still encrypted with HUB_SECRET_PREV. Commits after each DEK."""
    if not get_settings().HUB_SECRET:
        return 0
    rewrapped = 0
    for row in list(db.scalars(select(DataEncryptionKey)).all()):
        if not dek_needs_rewrap(row.wrapped_key):
            continue
        raw = unwrap_dek(row.wrapped_key)
        row.wrapped_key = wrap_dek(raw)
        db.commit()
        rewrapped += 1
    return rewrapped


def _count_column_usage(db: Session, table: str, column: str, dek_id: str) -> int:
    prefix = f"{V1_PREFIX}{dek_id}:"
    if table == "worker_nodes":
        return int(
            db.scalar(
                select(func.count())
                .select_from(WorkerNode)
                .where(WorkerNode.api_token_encrypted.like(f"{prefix}%"))
            )
            or 0
        )
    if table == "instance_settings":
        col = getattr(InstanceSettings, column)
        return int(db.scalar(select(func.count()).select_from(InstanceSettings).where(col.like(f"{prefix}%"))) or 0)
    if table == "organizations":
        return int(
            db.scalar(
                select(func.count())
                .select_from(Organization)
                .where(Organization.sso_client_secret_encrypted.like(f"{prefix}%"))
            )
            or 0
        )
    if table == "transcripts":
        return int(
            db.scalar(
                select(func.count())
                .select_from(Transcript)
                .where(Transcript.utterances_encrypted.like(f"{prefix}%"))
            )
            or 0
        )
    if table == "summaries":
        return int(
            db.scalar(
                select(func.count()).select_from(Summary).where(Summary.body_encrypted.like(f"{prefix}%"))
            )
            or 0
        )
    return 0


def delete_retiring_dek(db: Session, dek_id: str) -> bool:
    """Remove a retiring DEK with no ciphertext usage. Clears job FK refs; commits."""
    settings = db.get(InstanceSettings, 1)
    if settings is not None and settings.active_dek_id == dek_id:
        return False
    if count_dek_usage(db, dek_id) > 0:
        return False
    row = db.get(DataEncryptionKey, dek_id)
    if row is None or row.status != "retiring":
        return False
    db.execute(update(EncryptionJob).where(EncryptionJob.target_dek_id == dek_id).values(target_dek_id=None))
    db.delete(row)
    db.commit()
    return True


def count_dek_usage(db: Session, dek_id: str) -> int:
    total = 0
    for table, column in ENCRYPTED_COLUMNS:
        total += _count_column_usage(db, table, column, dek_id)
    return total


def dek_public(row: DataEncryptionKey, *, usage_count: int) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "retired_at": row.retired_at.isoformat() if row.retired_at else None,
        "usage_count": usage_count,
    }

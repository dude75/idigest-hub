"""One-time bootstrap: create first DEK and migrate legacy v0 ciphertext."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cryptography.fernet import InvalidToken

from app.config import get_settings
from app.crypto import (
    ENCRYPTED_COLUMNS,
    can_unwrap_dek,
    create_dek,
    decrypt_str,
    encrypt_str,
    rewrap_pending_deks,
)
import app.db as db_module
from app.db import get_engine
from app.models import (
    DataEncryptionKey,
    InstanceSettings,
    Organization,
    Summary,
    Transcript,
    WorkerNode,
)

log = logging.getLogger("app")


class CryptoConfigError(RuntimeError):
    """HUB_SECRET missing or cannot unwrap stored DEKs / ciphertext."""


def _has_encrypted_data(db: Session) -> bool:
    if db.scalar(select(func.count()).select_from(WorkerNode).where(WorkerNode.api_token_encrypted != "")):
        return True
    inst = db.get(InstanceSettings, 1)
    if inst is not None:
        if inst.smtp_password_encrypted or inst.download_proxy_password_encrypted:
            return True
    if db.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.sso_client_secret_encrypted.is_not(None))
    ):
        return True
    if db.scalar(select(func.count()).select_from(Transcript)):
        return True
    if db.scalar(select(func.count()).select_from(Summary)):
        return True
    return False


def validate_crypto_config(db: Session) -> None:
    """Fail closed when secrets cannot protect or read existing ciphertext."""
    from app.deps import get_instance_settings

    settings = get_settings()
    hub_secret = (settings.HUB_SECRET or "").strip()
    hub_prev = (settings.HUB_SECRET_PREV or "").strip()
    inst = get_instance_settings(db)
    deks = list(db.scalars(select(DataEncryptionKey)).all())
    has_data = _has_encrypted_data(db)

    needs_secret = inst.bootstrap_done or bool(deks) or has_data
    if needs_secret and not hub_secret:
        raise CryptoConfigError(
            "HUB_SECRET is empty but the database already contains instance or encrypted data. "
            "Set HUB_SECRET in .env and restart."
        )

    if deks:
        if not hub_secret and not hub_prev:
            raise CryptoConfigError(
                "HUB_SECRET is empty but data_encryption_keys exist. "
                "Set HUB_SECRET or HUB_SECRET_PREV during rotation and restart."
            )
        for row in deks:
            if not can_unwrap_dek(row.wrapped_key):
                raise CryptoConfigError(
                    f"HUB_SECRET cannot unwrap DEK {row.id}. "
                    "Use the correct HUB_SECRET or HUB_SECRET_PREV (during rotation) and restart."
                )

    if inst.bootstrap_done and has_data and hub_secret:
        if not _encrypted_sample_readable(db):
            raise CryptoConfigError(
                "HUB_SECRET cannot decrypt stored ciphertext. "
                "Restore the correct secret in .env and restart."
            )


def _encrypted_sample_readable(db: Session) -> bool:
    try:
        node = db.scalar(select(WorkerNode).limit(1))
        if node is not None and node.api_token_encrypted:
            decrypt_str(node.api_token_encrypted, db)
            return True
        inst = db.get(InstanceSettings, 1)
        if inst is not None and inst.smtp_password_encrypted:
            decrypt_str(inst.smtp_password_encrypted, db)
            return True
        org = db.scalar(
            select(Organization).where(Organization.sso_client_secret_encrypted.is_not(None)).limit(1)
        )
        if org is not None and org.sso_client_secret_encrypted:
            decrypt_str(org.sso_client_secret_encrypted, db)
            return True
        transcript = db.scalar(select(Transcript).limit(1))
        if transcript is not None:
            decrypt_str(transcript.utterances_encrypted, db)
            return True
        summary = db.scalar(select(Summary).limit(1))
        if summary is not None:
            decrypt_str(summary.body_encrypted, db)
            return True
    except InvalidToken:
        return False
    return True


def _migrate_table(db: Session, table: str, column: str, dek_id: str) -> int:
    migrated = 0
    if table == "worker_nodes":
        rows = list(db.scalars(select(WorkerNode)).all())
        for row in rows:
            value = getattr(row, column)
            if not value or value.startswith("v1:"):
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            migrated += 1
        return migrated
    if table == "instance_settings":
        row = db.get(InstanceSettings, 1)
        if row is None:
            return 0
        value = getattr(row, column)
        if not value or value.startswith("v1:"):
            return 0
        plain = decrypt_str(value, db)
        setattr(row, column, encrypt_str(plain, db))
        return 1
    if table == "organizations":
        rows = list(db.scalars(select(Organization)).all())
        for row in rows:
            value = getattr(row, column)
            if not value or value.startswith("v1:"):
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            migrated += 1
        return migrated
    if table == "transcripts":
        rows = list(db.scalars(select(Transcript)).all())
        for row in rows:
            value = getattr(row, column)
            if not value or value.startswith("v1:"):
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            migrated += 1
        return migrated
    if table == "summaries":
        rows = list(db.scalars(select(Summary)).all())
        for row in rows:
            value = getattr(row, column)
            if not value or value.startswith("v1:"):
                continue
            plain = decrypt_str(value, db)
            setattr(row, column, encrypt_str(plain, db))
            migrated += 1
        return migrated
    return migrated


def bootstrap_encryption_db(db: Session) -> bool:
    """Create first DEK and migrate legacy ciphertext. Returns True if bootstrap ran."""
    if not get_settings().HUB_SECRET:
        return False
    count = int(db.scalar(select(func.count()).select_from(DataEncryptionKey)) or 0)
    if count > 0:
        return False

    log.info("crypto bootstrap: creating initial DEK")
    from app.deps import get_instance_settings

    dek = create_dek(db, status="active")
    settings = get_instance_settings(db)
    settings.active_dek_id = dek.id

    total = 0
    for table, column in ENCRYPTED_COLUMNS:
        n = _migrate_table(db, table, column, dek.id)
        if n:
            log.info("crypto bootstrap: migrated %s.%s rows=%s", table, column, n)
        total += n

    db.commit()
    log.info("crypto bootstrap: done dek=%s migrated=%s", dek.id, total)
    return True


def bootstrap_encryption() -> None:
    get_engine()
    assert db_module.SessionLocal is not None
    db = db_module.SessionLocal()
    try:
        validate_crypto_config(db)
        bootstrap_encryption_db(db)
        rewrapped = rewrap_pending_deks(db)
        if rewrapped:
            log.info("crypto rewrap on startup: deks=%s", rewrapped)
    except CryptoConfigError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

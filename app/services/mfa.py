"""2FA policy, challenges, and recovery codes."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.constants import MFA_CHALLENGE_TTL_SEC, MFA_RECOVERY_CODE_COUNT
from app.crypto import decrypt_str, encrypt_str
from app.models import Membership, MfaChallenge, Organization, RecoveryCode, User, new_id
from app.security import hash_secret, new_mfa_challenge_token, new_recovery_code
from app.services.sso import AUTH_PROVIDER_OIDC, password_login_allowed
from app.services.totp import generate_secret, provisioning_uri, verify_code
from app.timeutil import utcnow

AUTH_PROVIDER_LOCAL = "local"


def totp_enabled(user: User) -> bool:
    return user.totp_enabled_at is not None


def totp_configured(user: User) -> bool:
    return user.totp_secret_encrypted is not None or user.totp_enabled_at is not None


def user_totp_secret(user: User, db: Session) -> str | None:
    if not user.totp_secret_encrypted:
        return None
    return decrypt_str(user.totp_secret_encrypted, db)


def verify_user_totp(user: User, code: str, db: Session) -> bool:
    secret = user_totp_secret(user, db)
    if secret is None:
        return False
    return verify_code(secret=secret, code=code)


def hub_local_auth_applies(*, user: User, org: Organization | None, membership: Membership | None) -> bool:
    """Hub password login and TOTP apply (SSO disabled or break-glass admin)."""
    if not user.password_hash:
        return False
    if not password_login_allowed(
        membership=membership,
        org=org,
        is_instance_admin=user.is_instance_admin,
    ):
        return False
    return user.auth_provider in (AUTH_PROVIDER_LOCAL, AUTH_PROVIDER_OIDC)


def hub_mfa_applies(*, user: User, org: Organization | None, membership: Membership | None) -> bool:
    return hub_local_auth_applies(user=user, org=org, membership=membership)


def org_mfa_required(*, user: User, org: Organization | None, membership: Membership | None) -> bool:
    if org is None or not org.mfa_required or org.sso_enabled:
        return False
    return hub_mfa_applies(user=user, org=org, membership=membership)


def mfa_enrollment_required(*, user: User, org: Organization | None, membership: Membership | None) -> bool:
    return org_mfa_required(user=user, org=org, membership=membership) and not totp_enabled(user)


def should_challenge_at_login(*, user: User, org: Organization | None, membership: Membership | None) -> bool:
    return totp_enabled(user) and hub_mfa_applies(user=user, org=org, membership=membership)


def create_mfa_challenge(db: Session, user_id: str) -> str:
    db.execute(delete(MfaChallenge).where(MfaChallenge.user_id == user_id))
    raw = new_mfa_challenge_token()
    now = utcnow()
    db.add(
        MfaChallenge(
            id=new_id(),
            user_id=user_id,
            token_hash=hash_secret(raw),
            expires_at=now + timedelta(seconds=MFA_CHALLENGE_TTL_SEC),
            created_at=now,
        )
    )
    db.flush()
    return raw


def resolve_mfa_challenge(db: Session, challenge_id: str) -> MfaChallenge | None:
    row = db.scalar(
        select(MfaChallenge).where(
            MfaChallenge.token_hash == hash_secret(challenge_id),
            MfaChallenge.expires_at > utcnow(),
        )
    )
    return row


def consume_mfa_challenge(db: Session, challenge: MfaChallenge) -> None:
    db.delete(challenge)


def start_totp_setup(db: Session, user: User) -> tuple[str, str]:
    secret = generate_secret()
    user.totp_secret_encrypted = encrypt_str(secret, db)
    user.totp_enabled_at = None
    user.updated_at = utcnow()
    db.flush()
    return secret, provisioning_uri(secret=secret, email=user.email)


def confirm_totp_setup(db: Session, user: User, code: str) -> list[str]:
    secret = user_totp_secret(user, db)
    if secret is None or not verify_code(secret=secret, code=code):
        return []
    now = utcnow()
    user.totp_enabled_at = now
    user.updated_at = now
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes: list[str] = []
    for _ in range(MFA_RECOVERY_CODE_COUNT):
        raw = new_recovery_code()
        codes.append(raw)
        db.add(
            RecoveryCode(
                id=new_id(),
                user_id=user.id,
                code_hash=hash_secret(raw),
                created_at=now,
            )
        )
    db.flush()
    return codes


def disable_totp(db: Session, user: User) -> None:
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    user.updated_at = utcnow()
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


def consume_recovery_code(db: Session, user: User, code: str) -> bool:
    normalized = (code or "").strip().replace(" ", "").upper()
    if not normalized:
        return False
    row = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == hash_secret(normalized),
            RecoveryCode.used_at.is_(None),
        )
    )
    if row is None:
        return False
    row.used_at = utcnow()
    return True

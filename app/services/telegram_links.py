"""Link hub users to Telegram chats."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import InstanceSettings, TelegramLink, TelegramLinkChallenge, User, new_id
from app.security import hash_secret
from app.timeutil import as_utc, utcnow

LINK_CODE_TTL = timedelta(minutes=15)
_CODE_RE = re.compile(r"^[A-Z2-9]{8}$")


def _normalize_code(raw: str) -> str:
    return raw.strip().upper().replace("-", "")


def clear_all_telegram_links(db: Session) -> None:
    db.execute(delete(TelegramLinkChallenge))
    db.execute(delete(TelegramLink))


def link_matches_current_bot(link: TelegramLink, settings: InstanceSettings) -> bool:
    current = settings.telegram_bot_id
    stored = link.instance_bot_id
    if current is None:
        return stored is None
    if stored is None:
        return False
    return stored == current


def generate_link_challenge(db: Session, user_id: str) -> tuple[str, str]:
    """Return (plain_code, expires_at_iso)."""
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
    now = utcnow()
    expires = now + LINK_CODE_TTL
    db.execute(delete(TelegramLinkChallenge).where(TelegramLinkChallenge.user_id == user_id))
    row = TelegramLinkChallenge(
        id=new_id(),
        user_id=user_id,
        code_hash=hash_secret(f"telegram-link:{code}"),
        expires_at=expires,
        created_at=now,
    )
    db.add(row)
    db.flush()
    return code, expires.isoformat()


def consume_link_code(
    db: Session,
    *,
    code: str,
    telegram_user_id: str,
    chat_id: str,
) -> User:
    normalized = _normalize_code(code)
    if not _CODE_RE.match(normalized):
        raise ValueError("invalid_code")
    now = utcnow()
    challenge = db.scalar(
        select(TelegramLinkChallenge).where(TelegramLinkChallenge.code_hash == hash_secret(f"telegram-link:{normalized}"))
    )
    if challenge is None or as_utc(challenge.expires_at) < now:
        raise ValueError("invalid_code")
    existing_tg = db.scalar(select(TelegramLink).where(TelegramLink.telegram_user_id == telegram_user_id))
    if existing_tg is not None and existing_tg.user_id != challenge.user_id:
        raise ValueError("telegram_taken")
    user = db.get(User, challenge.user_id)
    if user is None or user.disabled_at is not None:
        raise ValueError("invalid_code")
    from app.deps import get_instance_settings

    settings = get_instance_settings(db)
    db.execute(delete(TelegramLink).where(TelegramLink.user_id == challenge.user_id))
    db.add(
        TelegramLink(
            user_id=challenge.user_id,
            telegram_user_id=str(telegram_user_id),
            chat_id=str(chat_id),
            linked_at=now,
            instance_bot_id=settings.telegram_bot_id,
        )
    )
    db.delete(challenge)
    db.flush()
    return user


def unlink_user(db: Session, user_id: str) -> None:
    db.execute(delete(TelegramLink).where(TelegramLink.user_id == user_id))
    db.execute(delete(TelegramLinkChallenge).where(TelegramLinkChallenge.user_id == user_id))


def link_for_user(db: Session, user_id: str) -> TelegramLink | None:
    return db.scalar(select(TelegramLink).where(TelegramLink.user_id == user_id))


def effective_link_for_user(db: Session, user_id: str, settings: InstanceSettings) -> TelegramLink | None:
    link = link_for_user(db, user_id)
    if link is None:
        return None
    if not link_matches_current_bot(link, settings):
        unlink_user(db, user_id)
        return None
    return link


def link_for_telegram_user(db: Session, telegram_user_id: str) -> TelegramLink | None:
    return db.scalar(select(TelegramLink).where(TelegramLink.telegram_user_id == str(telegram_user_id)))

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import AuthContext, get_instance_settings, require_auth
from app.errors import ErrorCode
from app.routers.auth._router import router
from app.schemas.common import OkStatusResponse
from app.schemas.telegram import MeTelegramLinkResponse, MeTelegramStatusResponse
from app.services.telegram_identity import telegram_bot_public_fresh
from app.services.telegram_links import effective_link_for_user, generate_link_challenge, unlink_user


@router.get("/me/telegram", response_model=MeTelegramStatusResponse)
def me_telegram_status(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MeTelegramStatusResponse:
    ctx.require_org()
    settings = get_instance_settings(db)
    bot_on = bool(settings.telegram_enabled and (settings.telegram_bot_token_encrypted or "").strip())
    username, bot_url = telegram_bot_public_fresh(db, settings) if bot_on else (None, None)
    link = effective_link_for_user(db, ctx.user.id, settings)
    return MeTelegramStatusResponse(
        bot_enabled=bot_on,
        bot_instance_id=settings.telegram_bot_id,
        bot_username=username,
        bot_url=bot_url,
        linked=link is not None,
        linked_at=link.linked_at.isoformat() if link is not None else None,
    )


@router.post("/me/telegram/link", response_model=MeTelegramLinkResponse)
def me_telegram_link(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> MeTelegramLinkResponse:
    ctx.require_org()
    settings = get_instance_settings(db)
    if not settings.telegram_enabled or not (settings.telegram_bot_token_encrypted or "").strip():
        ctx.raise_error(ErrorCode.validation_error)
    code, expires_at = generate_link_challenge(db, ctx.user.id)
    username, bot_url = telegram_bot_public_fresh(db, settings)
    db.commit()
    return MeTelegramLinkResponse(
        code=code,
        expires_at=expires_at,
        start_command=f"/start {code}",
        bot_username=username,
        bot_url=bot_url,
    )


@router.delete("/me/telegram", response_model=OkStatusResponse)
def me_telegram_unlink(
    db: Session = Depends(get_session, scope="function"),
    ctx: AuthContext = Depends(require_auth),
) -> OkStatusResponse:
    unlink_user(db, ctx.user.id)
    db.commit()
    return OkStatusResponse()

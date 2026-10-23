"""Telegram Bot API webhook."""

from __future__ import annotations

import logging

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import get_instance_settings
from app.routers.integrations._router import router
from app.security import compare_digest
from app.services.telegram_bot import handle_update
from app.services.telegram_identity import bot_token

log = logging.getLogger("app")


@router.post("/integrations/telegram/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_session, scope="function"),
) -> JSONResponse:
    settings = get_instance_settings(db)
    secret = (settings.telegram_webhook_secret or "").strip()
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
    if not secret or not compare_digest(header, secret):
        return JSONResponse(status_code=403, content={"status": "forbidden"})
    token = bot_token(settings, db)
    if not token:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    try:
        update = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "bad_request"})
    if not isinstance(update, dict):
        return JSONResponse(status_code=400, content={"status": "bad_request"})
    try:
        await handle_update(db, update, token=token, settings=settings, bot_username=None)
        db.commit()
    except Exception:
        log.exception("telegram webhook handler failed")
        db.rollback()
    return JSONResponse(content={"status": "ok"})

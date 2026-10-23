"""Low-level Telegram Bot API client."""

from __future__ import annotations

import logging
from typing import Any

import httpx2

from app.models import InstanceSettings
from app.services.import_platforms import effective_telegram_proxy

log = logging.getLogger("app")

API_BASE = "https://api.telegram.org"
_TIMEOUT = httpx2.Timeout(connect=15.0, read=90.0, write=30.0, pool=10.0)


class TelegramApiError(Exception):
    def __init__(self, description: str, *, retry_after: int | None = None) -> None:
        super().__init__(description)
        self.description = description
        self.retry_after = retry_after


def _proxy_url(settings: InstanceSettings, db) -> str | None:
    return effective_telegram_proxy(settings, db)


async def _request(
    method: str,
    token: str,
    *,
    settings: InstanceSettings,
    db,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{API_BASE}/bot{token}/{method}"
    proxy = _proxy_url(settings, db)
    async with httpx2.AsyncClient(timeout=_TIMEOUT, proxy=proxy) as client:
        response = await client.post(url, json=json_body, params=params)
    try:
        payload = response.json()
    except ValueError:
        raise TelegramApiError(f"invalid response HTTP {response.status_code}") from None
    if not payload.get("ok"):
        desc = str(payload.get("description") or "telegram error")
        retry = None
        params_obj = payload.get("parameters")
        if isinstance(params_obj, dict) and params_obj.get("retry_after") is not None:
            try:
                retry = int(params_obj["retry_after"])
            except (TypeError, ValueError):
                retry = None
        raise TelegramApiError(desc, retry_after=retry)
    result = payload.get("result")
    return result if isinstance(result, dict) else {"result": result}


async def get_me(token: str, *, settings: InstanceSettings, db) -> dict[str, Any]:
    return await _request("getMe", token, settings=settings, db=db)


async def send_message(
    token: str,
    *,
    settings: InstanceSettings,
    db,
    chat_id: str,
    text: str,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
    if parse_mode:
        body["parse_mode"] = parse_mode
    return await _request("sendMessage", token, settings=settings, db=db, json_body=body)


async def get_updates(
    token: str,
    *,
    settings: InstanceSettings,
    db,
    offset: int | None,
    timeout: int = 50,
    secret_token: str | None = None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        body["offset"] = offset
    url = f"{API_BASE}/bot{token}/getUpdates"
    proxy = _proxy_url(settings, db)
    headers = {}
    if secret_token:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret_token
    async with httpx2.AsyncClient(timeout=httpx2.Timeout(connect=15.0, read=timeout + 15, write=30.0, pool=10.0), proxy=proxy) as client:
        response = await client.post(url, json=body, headers=headers or None)
    payload = response.json()
    if not payload.get("ok"):
        desc = str(payload.get("description") or "telegram error")
        raise TelegramApiError(desc)
    result = payload.get("result")
    return result if isinstance(result, list) else []


async def set_webhook(
    token: str,
    *,
    settings: InstanceSettings,
    db,
    webhook_url: str,
    secret_token: str,
) -> None:
    await _request(
        "setWebhook",
        token,
        settings=settings,
        db=db,
        json_body={
            "url": webhook_url,
            "secret_token": secret_token,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        },
    )


async def delete_webhook(token: str, *, settings: InstanceSettings, db) -> None:
    await _request("deleteWebhook", token, settings=settings, db=db, json_body={"drop_pending_updates": False})


async def get_file_path(token: str, *, settings: InstanceSettings, db, file_id: str) -> str:
    result = await _request("getFile", token, settings=settings, db=db, json_body={"file_id": file_id})
    path = result.get("file_path")
    if not isinstance(path, str) or not path.strip():
        raise TelegramApiError("missing file_path")
    return path.strip()


async def download_file_bytes(token: str, *, settings: InstanceSettings, db, file_path: str) -> bytes:
    url = f"{API_BASE}/file/bot{token}/{file_path}"
    proxy = _proxy_url(settings, db)
    async with httpx2.AsyncClient(timeout=_TIMEOUT, proxy=proxy) as client:
        response = await client.get(url)
    if response.status_code >= 400:
        raise TelegramApiError(f"file download HTTP {response.status_code}")
    return response.content

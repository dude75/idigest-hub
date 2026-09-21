"""HTTP client for icapture-worker."""

from __future__ import annotations

import logging
from typing import Any

import httpx2
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import decrypt_str
from app.db import release_connection
from app.models import WorkerNode
from app.services.workers import WorkerClientError, _parse_json, map_worker_error

log = logging.getLogger("app")

CAPTURE_WORKER_ERROR_MAP = {
    "unauthorized": "pipeline_error",
    "queue_full": "queue_full",
    "not_found": "not_found",
    "invalid_url": "invalid_url",
    "unsupported_connector": "pipeline_error",
    "join_failed": "pipeline_error",
    "invalid_file": "invalid_file",
    "task_timeout": "pipeline_error",
    "interrupted": "pipeline_error",
    "pipeline_error": "pipeline_error",
    "task_running": "task_running",
}


def map_capture_worker_error(code: str | None) -> str:
    if not code:
        return "pipeline_error"
    return CAPTURE_WORKER_ERROR_MAP.get(code, map_worker_error(code))


def _auth_header(db: Session, node: WorkerNode) -> dict[str, str]:
    token = decrypt_str(node.api_token_encrypted, db)
    return {"Authorization": f"Bearer {token}"}


def _timeout(*, upload: bool = False, capture_start: bool = False) -> httpx2.Timeout:
    settings = get_settings()
    if capture_start:
        read = settings.WORKER_CAPTURE_TIMEOUT_SEC
    elif upload:
        read = settings.WORKER_UPLOAD_TIMEOUT_SEC
    else:
        read = settings.WORKER_HTTP_TIMEOUT_SEC
    return httpx2.Timeout(connect=10.0, read=read, write=read, pool=10.0)


def _release(db: Session | None) -> None:
    if db is not None:
        release_connection(db)


async def post_capture(
    db: Session,
    node: WorkerNode,
    *,
    connector: str,
    meeting_url: str,
    pin: str,
    jwt: str | None,
    display_name: str,
) -> dict[str, Any]:
    url = node.base_url.rstrip("/") + "/capture"
    headers = {**_auth_header(db, node), "Content-Type": "application/json"}
    payload = {
        "connector": connector,
        "meeting_url": meeting_url,
        "pin": pin,
        "jwt": jwt,
        "display_name": display_name,
    }
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout(capture_start=True)) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    body = _parse_json(response)
    if response.status_code == 503:
        raise WorkerClientError("queue_full", 503, body)
    if response.status_code >= 500:
        raise WorkerClientError("http", response.status_code, body)
    if response.status_code >= 400:
        raise WorkerClientError("error_status", response.status_code, body)
    return body


async def get_capture_task(db: Session, node: WorkerNode, worker_task_id: str) -> tuple[int, dict[str, Any]]:
    url = node.base_url.rstrip("/") + f"/tasks/{worker_task_id}"
    headers = _auth_header(db, node)
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout()) as client:
            response = await client.get(url, headers=headers)
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    return response.status_code, _parse_json(response)


async def stop_capture_task(db: Session, node: WorkerNode, worker_task_id: str) -> tuple[int, dict[str, Any]]:
    url = node.base_url.rstrip("/") + f"/tasks/{worker_task_id}/stop"
    headers = _auth_header(db, node)
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout()) as client:
            response = await client.post(url, headers=headers)
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    return response.status_code, _parse_json(response)


async def delete_capture_task(db: Session, node: WorkerNode, worker_task_id: str) -> int:
    url = node.base_url.rstrip("/") + f"/tasks/{worker_task_id}"
    headers = _auth_header(db, node)
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout()) as client:
            response = await client.delete(url, headers=headers)
    except httpx2.HTTPError:
        log.info("capture worker delete failed node=%s task=%s", node.id, worker_task_id)
        return 0
    return response.status_code


async def download_capture_artifact(
    db: Session,
    node: WorkerNode,
    worker_task_id: str,
) -> tuple[int, bytes, dict[str, str]]:
    url = node.base_url.rstrip("/") + f"/tasks/{worker_task_id}/download"
    headers = _auth_header(db, node)
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout(upload=True)) as client:
            response = await client.get(url, headers=headers)
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    hdrs = {
        k.lower(): v
        for k, v in response.headers.items()
        if k.lower() in {"content-type", "content-disposition", "content-length"}
    }
    return response.status_code, response.content, hdrs

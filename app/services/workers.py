"""HTTP-клиент к itranscribe-worker / isummarize-worker. URL и токены наружу не светятся."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx2
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import decrypt_str
from app.db import release_connection
from app.models import WorkerNode

log = logging.getLogger("app")

WORKER_ERROR_MAP = {
    "unauthorized": "pipeline_error",
    "payload_too_large": "payload_too_large",
    "queue_full": "queue_full",
    "invalid_file": "invalid_file",
    "not_found": "not_found",
    "task_running": "task_running",
    "missing_upload": "pipeline_error",
    "ffmpeg_timeout": "pipeline_error",
    "task_timeout": "pipeline_error",
    "zero_duration": "pipeline_error",
    "pipeline_error": "pipeline_error",
    "engine_unavailable": "engine_unavailable",
    "interrupted": "pipeline_error",
    "process_killed": "pipeline_error",
    "missing_payload": "pipeline_error",
    "llm_unconfigured": "pipeline_error",
    "llm_unavailable": "pipeline_error",
    "llm_timeout": "pipeline_error",
    "llm_bad_response": "pipeline_error",
    "text_too_long": "text_too_long",
}


def map_worker_error(code: str | None) -> str:
    if not code:
        return "pipeline_error"
    return WORKER_ERROR_MAP.get(code, "pipeline_error")


def _auth_header(db: Session, node: WorkerNode) -> dict[str, str]:
    token = decrypt_str(node.api_token_encrypted, db)
    return {"Authorization": f"Bearer {token}"}


def _timeout(upload: bool = False) -> httpx2.Timeout:
    settings = get_settings()
    read = settings.WORKER_UPLOAD_TIMEOUT_SEC if upload else settings.WORKER_HTTP_TIMEOUT_SEC
    return httpx2.Timeout(connect=10.0, read=read, write=read, pool=10.0)


def _release(db: Session | None) -> None:
    if db is not None:
        release_connection(db)


class WorkerClientError(Exception):
    def __init__(self, kind: str, status_code: int | None = None, body: dict | None = None) -> None:
        super().__init__(kind)
        self.kind = kind  # http, timeout, queue_full, payload_too_large, not_found, error_status
        self.status_code = status_code
        self.body = body or {}

    @property
    def worker_code(self) -> str | None:
        err = self.body.get("error") if isinstance(self.body, dict) else None
        if isinstance(err, dict):
            return err.get("code")
        return None


def _parse_json(response: httpx2.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def get_health(db: Session | None, node: WorkerNode) -> tuple[int, dict[str, Any]]:
    url = node.base_url.rstrip("/") + "/health"
    _release(db)
    async with httpx2.AsyncClient(timeout=_timeout()) as client:
        response = await client.get(url)
    return response.status_code, _parse_json(response)


async def get_health_url(base_url: str) -> tuple[int, dict[str, Any]]:
    url = base_url.rstrip("/") + "/health"
    async with httpx2.AsyncClient(timeout=_timeout()) as client:
        response = await client.get(url)
    return response.status_code, _parse_json(response)


async def verify_worker_token(base_url: str, api_token: str) -> None:
    """Raise WorkerClientError if the worker rejects the Bearer token."""
    url = base_url.rstrip("/") + "/tasks"
    headers = {"Authorization": f"Bearer {api_token}"}
    try:
        async with httpx2.AsyncClient(timeout=_timeout()) as client:
            response = await client.get(url, headers=headers)
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    if response.status_code == 401:
        raise WorkerClientError("error_status", 401, _parse_json(response))
    if response.status_code >= 500:
        raise WorkerClientError("http", response.status_code, _parse_json(response))


async def get_ready(db: Session | None, node: WorkerNode) -> int:
    url = node.base_url.rstrip("/") + "/ready"
    _release(db)
    async with httpx2.AsyncClient(timeout=_timeout()) as client:
        response = await client.get(url)
    return response.status_code


async def post_transcribe(
    db: Session,
    node: WorkerNode,
    path: Path,
    filename: str,
    asr_model: str,
    diarization_model: str | None,
) -> dict[str, Any]:
    url = node.base_url.rstrip("/") + "/transcribe"
    headers = _auth_header(db, node)
    suffix = path.suffix.lower()
    mime = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}.get(suffix, "application/octet-stream")
    data = {"asr_model": asr_model, "diarization_model": diarization_model or ""}
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout(upload=True)) as client:
            with path.open("rb") as handle:
                response = await client.post(
                    url,
                    headers=headers,
                    data=data,
                    files={"file": (filename, handle, mime)},
                )
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    body = _parse_json(response)
    if response.status_code == 503:
        raise WorkerClientError("queue_full", 503, body)
    if response.status_code == 413:
        raise WorkerClientError("payload_too_large", 413, body)
    if response.status_code >= 500:
        raise WorkerClientError("http", response.status_code, body)
    if response.status_code >= 400:
        raise WorkerClientError("error_status", response.status_code, body)
    return body


async def post_summarize(db: Session, node: WorkerNode, text: str, skill: str) -> dict[str, Any]:
    url = node.base_url.rstrip("/") + "/summarize"
    headers = {**_auth_header(db, node), "Content-Type": "application/json"}
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout(upload=True)) as client:
            response = await client.post(url, headers=headers, json={"text": text, "skill": skill})
    except httpx2.TimeoutException as exc:
        raise WorkerClientError("timeout") from exc
    except httpx2.HTTPError as exc:
        raise WorkerClientError("http") from exc
    body = _parse_json(response)
    if response.status_code == 503:
        raise WorkerClientError("queue_full", 503, body)
    if response.status_code == 413:
        raise WorkerClientError("payload_too_large", 413, body)
    if response.status_code >= 500:
        raise WorkerClientError("http", response.status_code, body)
    if response.status_code >= 400:
        raise WorkerClientError("error_status", response.status_code, body)
    return body


async def get_task(db: Session, node: WorkerNode, worker_task_id: str) -> tuple[int, dict[str, Any]]:
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


async def delete_task(db: Session, node: WorkerNode, worker_task_id: str) -> int:
    url = node.base_url.rstrip("/") + f"/tasks/{worker_task_id}"
    headers = _auth_header(db, node)
    _release(db)
    try:
        async with httpx2.AsyncClient(timeout=_timeout()) as client:
            response = await client.delete(url, headers=headers)
    except httpx2.HTTPError:
        log.info("worker delete failed node=%s task=%s", node.id, worker_task_id)
        return 0
    return response.status_code

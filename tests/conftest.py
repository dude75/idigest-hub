"""Shared fixtures and helpers for hub API tests (SPEC §14)."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.workers import WorkerClientError

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "adminpass1"
LOADED_ENGINES = {
    "whisper": "loaded",
    "gigaam": "loaded",
    "nemo": "loaded",
    "pyannote": "loaded",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("INSTANCE_BOOTSTRAP_TOKEN", "boot")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hub.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("DISPATCH_NO_CANDIDATE_SEC", "1")
    # Keep the background dispatcher quiet so request-path ticks stay deterministic.
    monkeypatch.setenv("DISPATCH_POLL_SEC", "3600")

    from app.config import get_settings
    from app.db import get_engine, reset_engine
    from app.models import Base

    from app.services.storage import reset_storage

    get_settings.cache_clear()
    reset_storage()
    reset_engine()
    Base.metadata.create_all(get_engine())

    from app.rate_limit import reset_rate_limiter

    reset_rate_limiter()

    import app.services.dispatcher as dispatcher

    dispatcher._tick_lock = None

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    from app.services.storage import reset_storage

    get_settings.cache_clear()
    reset_storage()
    reset_engine()
    dispatcher._tick_lock = None

    from app.rate_limit import reset_rate_limiter

    reset_rate_limiter()


def err_code(response) -> str:
    return response.json()["error"]["code"]


def setup_admin(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> dict:
    response = client.post(
        "/api/v1/setup",
        json={"email": email, "password": password, "bootstrap_token": "boot"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def signup(client: TestClient, email: str, password: str, tariff_id: str):
    return client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "tariff_id": tariff_id},
    )


def login(client: TestClient, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def login_ready(client: TestClient, email: str, password: str) -> dict:
    """Login and clear must_change_password for org-created users."""
    login(client, email, password)
    payload = client.get("/api/v1/me").json()
    if payload.get("must_change_password"):
        changed = client.post("/api/v1/auth/password/change", json={"new_password": password})
        assert changed.status_code == 200, changed.text
        payload = me(client)
    return payload


def logout(client: TestClient):
    return client.post("/api/v1/auth/logout")


def default_tariff_id(client: TestClient) -> str:
    response = client.get("/api/v1/tariffs")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    unlimited = next(item for item in items if item["unlimited"])
    return unlimited["id"]


def me(client: TestClient) -> dict:
    response = client.get("/api/v1/me")
    assert response.status_code == 200, response.text
    return response.json()


def create_tariff(client: TestClient, **overrides) -> dict:
    body = {
        "name": "Paid",
        "unlimited": False,
        "available_on_signup": True,
        "price_per_audio_sec": "1.000000",
        "price_per_summarize_job": "1.00",
        "price_per_1k_summary_chars": "0",
        "audio_retention_days": 0,
        "api_enabled": True,
        "signup_credit": "0",
        "max_upload_bytes": 1024 * 1024,
    }
    body.update(overrides)
    response = client.post("/api/v1/tariffs", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def upload_audio(client: TestClient, name: str = "clip.wav", data: bytes | None = None):
    payload = data if data is not None else b"RIFF" + b"\x00" * 64
    return client.post(
        "/api/v1/audios",
        files={"file": (name, BytesIO(payload), "audio/wav")},
    )


def add_worker(
    client: TestClient,
    *,
    type: str = "transcribe",
    name: str = "worker-1",
    base_url: str = "http://worker.test",
    api_token: str = "tok",
) -> dict:
    response = client.post(
        "/api/v1/workers",
        json={
            "type": type,
            "name": name,
            "base_url": base_url,
            "api_token": api_token,
            "weight": 1,
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def open_db():
    from app.db import SessionLocal, get_engine

    get_engine()
    assert SessionLocal is not None
    return SessionLocal()


def seed_node_health(node_id: str, health: dict[str, Any] | None = None, *, ready_http: int | None = None) -> None:
    from app.models import WorkerNode
    from app.timeutil import utcnow

    payload = dict(health or {"status": "ok", "version": "x", "engines": dict(LOADED_ENGINES)})
    payload["_http"] = 200
    if ready_http is not None:
        payload["_ready_http"] = ready_http
    db = open_db()
    try:
        node = db.get(WorkerNode, node_id)
        assert node is not None
        node.last_health = payload
        node.last_health_at = utcnow()
        node.last_seen_version = payload.get("version")
        db.commit()
    finally:
        db.close()


def set_task_queued_at_past(task_id: str, seconds: int = 7200) -> None:
    from app.models import Task
    from app.timeutil import utcnow

    db = open_db()
    try:
        task = db.get(Task, task_id)
        assert task is not None
        task.queued_at = utcnow() - timedelta(seconds=seconds)
        db.commit()
    finally:
        db.close()


def get_task_row(task_id: str):
    from app.models import Task

    db = open_db()
    try:
        task = db.get(Task, task_id)
        if task is not None:
            db.expunge(task)
        return task
    finally:
        db.close()


class FakeWorkers:
    """In-process stand-in for itranscribe / isummarize HTTP."""

    def __init__(self) -> None:
        self.health_status = 200
        self.health: dict[str, Any] = {
            "status": "ok",
            "version": "x",
            "engines": dict(LOADED_ENGINES),
        }
        self.ready_status = 200
        self.transcribe_mode = "queued"
        self.summarize_mode = "success"
        self.poll_mode = "success"
        self.poll_queue: list[Any] | None = None
        self.transcript = [{"speaker": "A", "start": 0.0, "end": 1.5, "text": "hello"}]
        self.summary_text = "ok"
        self.audio_duration_sec = 10.0
        self.worker_task_id = "w1"
        self.error_code = "ffmpeg_timeout"
        self.asr_models_seen: list[str] = []
        self.post_count = 0
        self.poll_count = 0
        self.nodes_posted: list[str] = []
        self.nodes_polled: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (
            "get_health",
            "get_ready",
            "post_transcribe",
            "post_summarize",
            "get_task",
            "delete_task",
        ):
            monkeypatch.setattr(f"app.services.dispatcher.{name}", getattr(self, name))
            monkeypatch.setattr(f"app.services.workers.{name}", getattr(self, name))

    async def get_health(self, node) -> tuple[int, dict[str, Any]]:
        return self.health_status, dict(self.health)

    async def get_ready(self, node) -> int:
        return self.ready_status

    async def post_transcribe(self, node, path, filename, asr_model, diarization_model) -> dict[str, Any]:
        self.asr_models_seen.append(asr_model)
        self.post_count += 1
        self.nodes_posted.append(node.id)
        if self.transcribe_mode == "queue_full":
            raise WorkerClientError("queue_full", 503, {"error": {"code": "queue_full"}})
        if self.transcribe_mode == "network":
            raise WorkerClientError("http")
        if self.transcribe_mode == "error":
            return {
                "status": "error",
                "error": {"code": self.error_code},
                "meta": {"task_id": self.worker_task_id},
            }
        body = {
            "status": "success" if self.transcribe_mode == "success" else "queued",
            "transcript": self.transcript if self.transcribe_mode == "success" else [],
            "meta": {
                "task_id": self.worker_task_id,
                "audio_duration_sec": self.audio_duration_sec,
                "asr_model": asr_model,
            },
        }
        return body

    async def post_summarize(self, node, text, skill) -> dict[str, Any]:
        if self.summarize_mode == "queue_full":
            raise WorkerClientError("queue_full", 503, {"error": {"code": "queue_full"}})
        return {
            "status": "success" if self.summarize_mode == "success" else "queued",
            "summary": self.summary_text,
            "meta": {"task_id": "s1"},
        }

    async def get_task(self, node, worker_task_id) -> tuple[int, dict[str, Any]]:
        self.poll_count += 1
        self.nodes_polled.append(node.id)
        mode = self.poll_mode
        if self.poll_queue:
            mode = self.poll_queue.pop(0)
        if mode == "network":
            raise WorkerClientError("http")
        if mode == "404":
            return 404, {}
        if mode == "error":
            return 200, {"status": "error", "error": {"code": self.error_code}}
        if mode in {"queued", "running"}:
            return 200, {"status": mode}
        return 200, {
            "status": "success",
            "transcript": self.transcript,
            "summary": self.summary_text,
            "meta": {"task_id": worker_task_id, "audio_duration_sec": self.audio_duration_sec},
        }

    async def delete_task(self, node, worker_task_id) -> int:
        return 200


@pytest.fixture
def fake_workers(client, monkeypatch) -> FakeWorkers:
    fake = FakeWorkers()
    fake.install(monkeypatch)
    return fake

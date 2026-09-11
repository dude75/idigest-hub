from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from tests.conftest import (
    FakeWorkers,
    add_worker,
    login,
    setup_admin,
    signup,
    upload_audio,
)


def _sample(text: str, name: str, labels: dict[str, str] | None = None) -> float | None:
    wanted = labels or {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name != name:
                continue
            if all(sample.labels.get(key) == value for key, value in wanted.items()):
                return float(sample.value)
    return None


def _metrics_headers(token: str = "") -> dict[str, str]:
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def metrics_client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("INSTANCE_BOOTSTRAP_TOKEN", "boot")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hub.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("DISPATCH_NO_CANDIDATE_SEC", "1")
    monkeypatch.setenv("DISPATCH_POLL_SEC", "0.05")
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "metrics-secret")

    from app.config import get_settings
    from app.db import reset_engine
    from app.rate_limit import reset_rate_limiter
    from app.services.storage import reset_storage
    import app.services.dispatcher as dispatcher

    get_settings.cache_clear()
    reset_storage()
    reset_engine()
    reset_rate_limiter()
    dispatcher._tick_lock = None

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    reset_storage()
    reset_engine()
    reset_rate_limiter()
    dispatcher._tick_lock = None


def test_metrics_requires_token(metrics_client: TestClient):
    denied = metrics_client.get("/metrics")
    assert denied.status_code == 401

    body = metrics_client.get("/metrics", headers=_metrics_headers("metrics-secret"))
    assert body.status_code == 200
    assert "idigest_hub_up" in body.text
    assert "python_info" in body.text


def test_metrics_denied_when_token_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("INSTANCE_BOOTSTRAP_TOKEN", "boot")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'open.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("DISPATCH_POLL_SEC", "3600")
    monkeypatch.setenv("METRICS_TOKEN", "")

    from app.config import get_settings
    from app.db import reset_engine
    import app.services.dispatcher as dispatcher

    get_settings.cache_clear()
    reset_engine()
    dispatcher._tick_lock = None

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/metrics")
        assert response.status_code == 401

    get_settings.cache_clear()
    reset_engine()


def test_metrics_disabled_keeps_process_collectors(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRET", "test-secret")
    monkeypatch.setenv("INSTANCE_BOOTSTRAP_TOKEN", "boot")
    monkeypatch.setenv("SESSION_SECRET", "sess")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'hub.db'}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("DISPATCH_POLL_SEC", "3600")
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("METRICS_TOKEN", "metrics-secret")

    from app.config import get_settings
    from app.db import reset_engine
    import app.services.dispatcher as dispatcher

    get_settings.cache_clear()
    reset_engine()
    dispatcher._tick_lock = None

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/metrics", headers=_metrics_headers("metrics-secret"))
        assert response.status_code == 200
        assert "python_info" in response.text
        assert "idigest_hub_up" not in response.text
        assert _sample(response.text, "idigest_hub_tasks_total") is None

    get_settings.cache_clear()
    reset_engine()


def test_task_counters_and_queue_gauges(metrics_client: TestClient, fake_workers: FakeWorkers):
    from tests.conftest import default_tariff_id, logout, seed_node_health, signup

    setup_admin(metrics_client)
    tariff_id = default_tariff_id(metrics_client)
    worker = add_worker(metrics_client)
    seed_node_health(worker["id"])
    logout(metrics_client)
    assert signup(metrics_client, "user@example.com", "userpass1", tariff_id).status_code == 200
    fake_workers.transcribe_mode = "success"
    upload = upload_audio(metrics_client)
    assert upload.status_code == 200, upload.text
    created = metrics_client.post("/api/v1/tasks/transcribe", json={"audio_id": upload.json()["id"]})
    assert created.status_code == 202

    deadline = time.time() + 5
    success_count = None
    while time.time() < deadline:
        body = metrics_client.get("/metrics", headers=_metrics_headers("metrics-secret")).text
        success_count = _sample(
            body,
            "idigest_hub_tasks_total",
            {"type": "transcribe", "status": "success", "error_code": ""},
        )
        if success_count == 1.0:
            break
        time.sleep(0.05)
    assert success_count == 1.0

    queued = _sample(body, "idigest_hub_tasks_queued", {"type": "transcribe"})
    running = _sample(body, "idigest_hub_tasks_running", {"type": "transcribe"})
    assert queued == 0.0
    assert running == 0.0


def test_worker_up_gauge(metrics_client: TestClient, fake_workers: FakeWorkers):
    setup_admin(metrics_client)
    worker = add_worker(metrics_client, name="t1")
    from tests.conftest import seed_node_health

    seed_node_health(worker["id"])

    body = metrics_client.get("/metrics", headers=_metrics_headers("metrics-secret")).text
    assert (
        _sample(body, "idigest_hub_worker_up", {"node_id": worker["id"], "type": "transcribe", "name": "t1"})
        == 1.0
    )


def test_http_metrics_exclude_scrape(metrics_client: TestClient):
    metrics_client.get("/metrics", headers=_metrics_headers("metrics-secret"))
    metrics_client.get("/api/v1/health")

    body = metrics_client.get("/metrics", headers=_metrics_headers("metrics-secret")).text
    scrape_hits = 0.0
    health_hits = 0.0
    for family in text_string_to_metric_families(body):
        for sample in family.samples:
            if sample.name != "idigest_hub_http_requests_total":
                continue
            if sample.labels.get("route") == "/metrics":
                scrape_hits += sample.value
            if sample.labels.get("route") == "/api/v1/health":
                health_hits += sample.value
    assert scrape_hits == 0.0
    assert health_hits >= 1.0

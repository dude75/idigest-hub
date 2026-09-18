"""Dispatcher must not hold a DB connection across worker HTTP."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from tests.conftest import setup_admin


class _FakeResponse:
    status_code = 200

    def json(self) -> dict:
        return {"version": "test"}


def test_sqlite_engine_uses_null_pool(client):
    from app.db import get_engine

    assert isinstance(get_engine().pool, NullPool)


@pytest.mark.asyncio
async def test_get_health_releases_connection_during_http(client, monkeypatch):
    from app.db import SessionLocal
    from app.services.workers import get_health

    db = SessionLocal()
    during: list[bool] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            during.append(db.in_transaction())
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr("app.services.workers.httpx2.AsyncClient", FakeClient)
    try:
        db.execute(text("SELECT 1"))
        assert db.in_transaction()
        node = SimpleNamespace(base_url="http://127.0.0.1:9", id="n1")
        status, body = await get_health(db, node)
        assert status == 200
        assert body["version"] == "test"
        assert during == [False]
        assert not db.in_transaction()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_locked_tick_job_coalesces_duplicate_polls(client, monkeypatch):
    from app.services import dispatcher

    setup_admin(client)
    started = asyncio.Event()
    release = asyncio.Event()
    runs = {"n": 0}

    async def slow_tick(db, task_id=None, *, refresh_health=True):
        runs["n"] += 1
        started.set()
        await release.wait()

    monkeypatch.setattr(dispatcher, "tick_once", slow_tick)

    first = asyncio.create_task(dispatcher.locked_tick_job("task-a"))
    await started.wait()
    second = asyncio.create_task(dispatcher.locked_tick_job("task-a"))
    await asyncio.sleep(0)
    assert second.done()
    release.set()
    await first
    await second
    assert runs["n"] == 1


def _node(*, last_http: int = 200, age_sec: float = 1.0) -> SimpleNamespace:
    from app.timeutil import utcnow

    return SimpleNamespace(
        id="n1",
        type="transcribe",
        last_health={"_http": last_http, "engines": {"whisper": "loaded"}},
        last_health_at=utcnow() - timedelta(seconds=age_sec),
        last_seen_version="1",
        updated_at=utcnow(),
    )


@pytest.mark.asyncio
async def test_transient_health_error_keeps_last_good_health(client, monkeypatch):
    from app.services.dispatcher import _probe_node_health

    async def boom(_db, _node):
        raise TimeoutError("event loop stalled")

    monkeypatch.setattr("app.services.dispatcher.get_health", boom)
    node = _node(age_sec=2)
    await _probe_node_health(node)
    assert node.last_health["_http"] == 200
    assert node.last_health["engines"]["whisper"] == "loaded"


@pytest.mark.asyncio
async def test_stale_health_error_marks_unreachable(client, monkeypatch):
    from app.services.dispatcher import _probe_node_health

    async def boom(_db, _node):
        raise TimeoutError("event loop stalled")

    monkeypatch.setattr("app.services.dispatcher.get_health", boom)
    node = _node(age_sec=120)
    await _probe_node_health(node)
    assert node.last_health == {"_http": 0, "status": "unreachable"}

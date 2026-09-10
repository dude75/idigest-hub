"""Prometheus registry and scrape-time gauges for idigest-hub."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    Info,
    generate_latest,
)
from prometheus_client.gc_collector import GCCollector
from prometheus_client.metrics_core import GaugeMetricFamily
from prometheus_client.platform_collector import PlatformCollector
from prometheus_client.process_collector import ProcessCollector
from prometheus_client.registry import Collector
from sqlalchemy import func, select, text
from starlette.requests import Request
from starlette.routing import Match

from app.timeutil import as_utc, utcnow
from app.version import read_version

if TYPE_CHECKING:
    from app.config import Settings

CONTENT_TYPE = CONTENT_TYPE_LATEST

TASK_DURATION_BUCKETS = (1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0, 3600.0, 7200.0)
DISPATCHER_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

POOL_STATES = ("ready", "waiting", "empty")
TASK_TYPES = ("transcribe", "summarize")

_active: Metrics | None = None


def http_path_template(request: Request) -> str:
    for route in request.app.router.routes:
        if not hasattr(route, "matches"):
            continue
        match, _child = route.matches(request.scope)
        if match == Match.FULL:
            path = getattr(route, "path", None)
            if isinstance(path, str) and path:
                return path
    return "unknown"


@dataclass
class RuntimeState:
    settings: Settings | None = None
    dispatcher_started: bool = False
    dispatcher_last_success_at: float | None = None


class ScrapeCollector(Collector):
    def __init__(self, state: RuntimeState) -> None:
        self.state = state

    def collect(self):
        yield GaugeMetricFamily("idigest_hub_up", "Process is serving /metrics", value=1.0)
        yield GaugeMetricFamily(
            "idigest_hub_ready",
            "Database reachable and dispatcher loop is healthy",
            value=1.0 if _ready(self.state) else 0.0,
        )
        yield from _task_gauges()
        yield from _worker_gauges()
        yield from _pool_gauges()


def _ready(state: RuntimeState) -> bool:
    if not state.dispatcher_started or state.dispatcher_last_success_at is None:
        return False
    settings = state.settings
    poll = settings.DISPATCH_POLL_SEC if settings is not None else 1.0
    stale_after = max(5.0, poll * 3.0)
    if time.monotonic() - state.dispatcher_last_success_at > stale_after:
        return False
    return _db_ping_ok()


def _db_ping_ok() -> bool:
    from app.db import SessionLocal, get_engine

    try:
        get_engine()
        if SessionLocal is None:
            return False
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            return True
        finally:
            session.close()
    except Exception:
        return False


def _task_gauges():
    from app.db import SessionLocal, get_engine
    from app.models import Task

    queued = GaugeMetricFamily("idigest_hub_tasks_queued", "Tasks waiting for dispatch", labels=["type"])
    running = GaugeMetricFamily("idigest_hub_tasks_running", "Tasks dispatched to workers", labels=["type"])
    oldest = GaugeMetricFamily(
        "idigest_hub_oldest_queued_age_seconds",
        "Age of the oldest queued task",
        labels=["type"],
    )
    counts: dict[str, dict[str, int]] = {kind: {"queued": 0, "running": 0} for kind in TASK_TYPES}
    oldest_age: dict[str, float] = {kind: 0.0 for kind in TASK_TYPES}
    try:
        get_engine()
        if SessionLocal is not None:
            session = SessionLocal()
            try:
                rows = session.execute(
                    select(Task.type, Task.status, func.count(), func.min(Task.queued_at)).group_by(
                        Task.type, Task.status
                    )
                ).all()
                for task_type, status, count, min_queued in rows:
                    if task_type not in counts:
                        continue
                    if status == "queued":
                        counts[task_type]["queued"] = int(count)
                        if min_queued is not None:
                            oldest_age[task_type] = max(
                                0.0, (utcnow() - as_utc(min_queued)).total_seconds()
                            )
                    elif status == "running":
                        counts[task_type]["running"] = int(count)
            finally:
                session.close()
    except Exception:
        pass
    for kind in TASK_TYPES:
        queued.add_metric([kind], float(counts[kind]["queued"]))
        running.add_metric([kind], float(counts[kind]["running"]))
        oldest.add_metric([kind], oldest_age[kind])
    yield queued
    yield running
    yield oldest


def _worker_node_up(node) -> float:
    health = node.last_health or {}
    if health.get("_http") != 200:
        return 0.0
    if node.type == "summarize":
        return 1.0 if health.get("_ready_http") == 200 else 0.0
    return 1.0


def _worker_gauges():
    from app.db import SessionLocal, get_engine
    from app.models import WorkerNode

    up = GaugeMetricFamily(
        "idigest_hub_worker_up",
        "Registered worker reachable from the hub dispatcher",
        labels=["node_id", "type", "name"],
    )
    age = GaugeMetricFamily(
        "idigest_hub_worker_health_age_seconds",
        "Seconds since last health poll",
        labels=["node_id"],
    )
    now = utcnow()
    try:
        get_engine()
        if SessionLocal is not None:
            session = SessionLocal()
            try:
                nodes = list(session.scalars(select(WorkerNode)).all())
                for node in nodes:
                    if not node.enabled:
                        continue
                    up.add_metric([node.id, node.type, node.name or node.id], _worker_node_up(node))
                    if node.last_health_at is not None:
                        seconds = max(0.0, (now - as_utc(node.last_health_at)).total_seconds())
                        age.add_metric([node.id], seconds)
            finally:
                session.close()
    except Exception:
        pass
    yield up
    yield age


def _pool_gauges():
    from app.db import SessionLocal, get_engine
    from app.deps import get_instance_settings
    from app.models import WorkerNode
    from app.services.dispatcher import summarize_pool_state, transcribe_pool_state

    pool = GaugeMetricFamily(
        "idigest_hub_worker_pool_state",
        "1 when the pool is in the given state",
        labels=["type", "state"],
    )
    transcribe_state = "empty"
    summarize_state = "empty"
    try:
        get_engine()
        if SessionLocal is not None:
            session = SessionLocal()
            try:
                nodes = list(session.scalars(select(WorkerNode)).all())
                settings = get_instance_settings(session)
                transcribe_state = transcribe_pool_state(
                    nodes, settings.asr_model, settings.diarization_model
                )
                summarize_state = summarize_pool_state(nodes)
            finally:
                session.close()
    except Exception:
        pass
    for kind, current in (("transcribe", transcribe_state), ("summarize", summarize_state)):
        for state in POOL_STATES:
            pool.add_metric([kind, state], 1.0 if current == state else 0.0)
    yield pool


class Metrics:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        self.runtime = RuntimeState()
        self._info: Info | None = None
        if not enabled:
            return
        self.registry.register(ScrapeCollector(self.runtime))
        self._info = Info("idigest_hub", "Hub version", registry=self.registry)
        self._info.info({"version": read_version()})
        self.tasks_total = Counter(
            "idigest_hub_tasks_total",
            "Tasks reaching a terminal status",
            ["type", "status", "error_code"],
            registry=self.registry,
        )
        self.task_duration = Histogram(
            "idigest_hub_task_duration_seconds",
            "Wall time from queued_at to terminal status",
            ["type"],
            buckets=TASK_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.dispatcher_tick = Histogram(
            "idigest_hub_dispatcher_tick_seconds",
            "Dispatcher tick duration",
            buckets=DISPATCHER_BUCKETS,
            registry=self.registry,
        )
        self.dispatcher_tick_errors = Counter(
            "idigest_hub_dispatcher_tick_errors_total",
            "Dispatcher tick failures",
            registry=self.registry,
        )
        self.http_requests = Counter(
            "idigest_hub_http_requests_total",
            "HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "idigest_hub_http_request_duration_seconds",
            "HTTP request duration",
            ["method", "route"],
            buckets=HTTP_BUCKETS,
            registry=self.registry,
        )

    def bind(self, *, settings: Settings) -> None:
        self.runtime.settings = settings


def create_metrics(settings: Settings) -> Metrics:
    return Metrics(enabled=settings.METRICS_ENABLED)


def get_active() -> Metrics | None:
    return _active


def set_active(metrics: Metrics | None) -> None:
    global _active
    _active = metrics


def render() -> bytes:
    metrics = _active
    if metrics is None:
        return b""
    return generate_latest(metrics.registry)


def mark_dispatcher_started() -> None:
    metrics = _active
    if metrics is None:
        return
    metrics.runtime.dispatcher_started = True


def mark_dispatcher_tick_success() -> None:
    metrics = _active
    if metrics is None:
        return
    metrics.runtime.dispatcher_last_success_at = time.monotonic()


def observe_dispatcher_tick(duration_sec: float) -> None:
    metrics = _active
    if metrics is None or not metrics.enabled:
        return
    metrics.dispatcher_tick.observe(duration_sec)


def observe_dispatcher_tick_error() -> None:
    metrics = _active
    if metrics is None or not metrics.enabled:
        return
    metrics.dispatcher_tick_errors.inc()


def observe_task_terminal(task) -> None:
    metrics = _active
    if metrics is None or not metrics.enabled:
        return
    if task.status not in {"success", "error"}:
        return
    error_code = task.error_code or ""
    metrics.tasks_total.labels(type=task.type, status=task.status, error_code=error_code).inc()
    duration = (as_utc(task.updated_at) - as_utc(task.queued_at)).total_seconds()
    if duration >= 0:
        metrics.task_duration.labels(type=task.type).observe(duration)


def observe_http(method: str, route: str, status_code: int, duration_sec: float) -> None:
    metrics = _active
    if metrics is None or not metrics.enabled:
        return
    metrics.http_requests.labels(method=method, route=route, status=str(status_code)).inc()
    metrics.http_duration.labels(method=method, route=route).observe(duration_sec)

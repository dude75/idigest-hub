"""Capture tasks retry when workers become available after waiting."""


def test_mark_capture_waiting_requeues_without_worker_task(monkeypatch):
    from app.models import Task
    from app.services.capture_runner import _mark_capture_waiting, reset_capture_runner

    reset_capture_runner()

    task = Task(
        id="t1",
        type="capture",
        status="running",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
        worker_task_id=None,
        meta_json={"stage": "joining"},
    )

    class Session:
        def flush(self) -> None:
            return None

    _mark_capture_waiting(Session(), task, "unreachable")

    assert task.status == "queued"
    assert task.meta_json["stage"] == "queued"
    assert task.worker_id == "cap1"
    assert task.retry_without_timeout is True


def test_maybe_start_capture_recovers_after_worker_health_improves(monkeypatch):
    from app.models import Task, WorkerNode
    from app.services.capture_runner import maybe_start_capture, reset_capture_runner

    reset_capture_runner()
    monkeypatch.setattr("app.services.capture_runner._spawn_capture_thread", lambda _task_id: None)

    class Settings:
        capture_enabled = True

    monkeypatch.setattr("app.deps.get_instance_settings", lambda _db: Settings())
    monkeypatch.setattr("app.services.capture_platforms.allowed_connectors", lambda _s: ["jitsi"])

    worker = WorkerNode(
        id="cap1",
        type="capture",
        name="cap",
        base_url="http://cap",
        api_token_encrypted="x",
        weight=1,
        enabled=True,
        capture_connectors_json=["jitsi"],
        last_health={"_http": 0, "status": "unreachable"},
    )
    task = Task(
        id="t1",
        type="capture",
        status="queued",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
        meta_json={"stage": "queue_full", "meeting_url": "https://meet.example.com/room"},
    )

    class Session:
        def get(self, model, key):
            if model is WorkerNode and key == "cap1":
                return worker
            if model is Task and key == "t1":
                return task
            return None

        def scalars(self, _stmt):
            class Result:
                def first(self):
                    return None

                def all(self):
                    return []

            return Result()

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

    db = Session()
    maybe_start_capture(db, task)
    assert task.meta_json["stage"] == "queued"

    worker.last_health = {
        "_http": 200,
        "connectors": {"jitsi": {"status": "loaded"}},
        "workers": {"max": 4, "active": 0, "available": 4},
    }
    maybe_start_capture(db, task)
    assert task.status == "running"

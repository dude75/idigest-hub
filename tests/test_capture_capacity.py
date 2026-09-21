"""Capture dispatch: health.workers pool or one job per hub node fallback."""


def test_capture_worker_capacity_available_uses_workers_pool(monkeypatch):
    from app.models import Task, WorkerNode
    from app.services.capture_runner import capture_worker_capacity_available, reset_capture_runner

    reset_capture_runner()

    class Settings:
        pass

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
        last_health={
            "_http": 200,
            "connectors": {"jitsi": {"status": "loaded"}},
            "workers": {"max": 4, "active": 4, "available": 0},
        },
    )
    task = Task(
        id="t1",
        type="capture",
        status="queued",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
    )

    class Session:
        def get(self, model, key):
            if model is WorkerNode and key == "cap1":
                return worker
            return None

    assert capture_worker_capacity_available(Session(), task) is False
    worker.last_health["workers"] = {"max": 4, "active": 1, "available": 3}
    assert capture_worker_capacity_available(Session(), task) is True


def test_capture_worker_capacity_available_hub_node_fallback_when_no_workers(monkeypatch):
    from app.models import Task, WorkerNode
    from app.services.capture_runner import capture_worker_capacity_available, reset_capture_runner

    reset_capture_runner()

    class Settings:
        pass

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
        last_health={
            "_http": 200,
            "connectors": {"jitsi": {"status": "loaded"}},
        },
    )
    task = Task(
        id="t1",
        type="capture",
        status="queued",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
    )
    other = Task(
        id="t2",
        type="capture",
        status="running",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
    )

    class BusySession:
        def get(self, model, key):
            if model is WorkerNode and key == "cap1":
                return worker
            if model is Task:
                return other if key == "t2" else None
            return None

        def scalars(self, _stmt):
            class Result:
                def first(self):
                    return other

            return Result()

    assert capture_worker_capacity_available(BusySession(), task) is False

    class FreeSession:
        def get(self, model, key):
            if model is WorkerNode and key == "cap1":
                return worker
            return None

        def scalars(self, _stmt):
            class Result:
                def first(self):
                    return None

            return Result()

    assert capture_worker_capacity_available(FreeSession(), task) is True

    reset_capture_runner()

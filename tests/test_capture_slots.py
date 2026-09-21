"""Capture dispatch gated on icapture-worker health slots."""


def test_capture_worker_slot_available_uses_worker_health():
    from app.services.capture_runner import capture_worker_slot_available
    from app.models import Task, WorkerNode

    worker = WorkerNode(
        id="cap1",
        type="capture",
        name="cap",
        base_url="http://cap",
        api_token_encrypted="x",
        weight=1,
        enabled=True,
        last_health={"_http": 200, "slots": {"max": 50, "active": 50, "available": 0}},
    )
    task = Task(
        id="t1",
        type="capture",
        status="queued",
        org_id="o1",
        user_id="u1",
        worker_id="cap1",
    )

    class FakeSession:
        def get(self, _model, key):
            return worker if key == "cap1" else None

    assert capture_worker_slot_available(FakeSession(), task) is False
    worker.last_health = {"_http": 200, "slots": {"max": 50, "active": 1, "available": 49}}
    assert capture_worker_slot_available(FakeSession(), task) is True

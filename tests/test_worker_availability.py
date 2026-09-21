"""Dispatch-ready worker counts."""

from app.models import WorkerNode
from app.services.worker_availability import worker_is_dispatch_available, workers_availability_summary


def _node(**kwargs) -> WorkerNode:
    defaults = {
        "type": "transcribe",
        "enabled": True,
        "last_health": {"_http": 200, "engines": {"whisper": "loaded", "nemo": "loaded"}},
        "asr_models_json": ["whisper"],
        "diarization_models_json": ["nemo"],
    }
    defaults.update(kwargs)
    node = WorkerNode(
        id="w1",
        type=defaults["type"],
        name="w",
        base_url="http://w",
        api_token_encrypted="x",
        weight=1,
        enabled=defaults["enabled"],
        last_health=defaults["last_health"],
        asr_models_json=defaults.get("asr_models_json"),
        diarization_models_json=defaults.get("diarization_models_json"),
        capture_connectors_json=defaults.get("capture_connectors_json"),
    )
    return node


def test_transcribe_available_when_engines_loaded():
    node = _node()
    assert worker_is_dispatch_available(node, capture_connectors=["jitsi"]) is True


def test_transcribe_unavailable_when_health_down():
    node = _node(last_health={"_http": 503, "engines": {"whisper": "loaded"}})
    assert worker_is_dispatch_available(node, capture_connectors=["jitsi"]) is False


def test_summarize_available_on_ready():
    node = _node(type="summarize", last_health={"_http": 200, "_ready_http": 200})
    assert worker_is_dispatch_available(node, capture_connectors=["jitsi"]) is True


def test_workers_summary_counts():
    nodes = [
        _node(),
        _node(id="w2", enabled=False),
        _node(
            id="w3",
            type="capture",
            last_health={
                "_http": 200,
                "connectors": {"jitsi": {"status": "loaded"}},
            },
            capture_connectors_json=["jitsi"],
            asr_models_json=None,
            diarization_models_json=None,
        ),
    ]
    summary = workers_availability_summary(
        nodes,
        capture_connectors=["jitsi"],
        import_max_concurrent=4,
    )
    assert summary["available"] == 2
    assert summary["by_type"]["transcribe"]["available"] == 1
    assert summary["by_type"]["capture"]["available"] == 1
    assert summary["hub_limits"]["import_max_concurrent"] == 4
    assert summary["capture_capacity"] == {"max": 1, "active": 0, "available": 1}


def test_capture_capacity_from_health_workers_pool():
    nodes = [
        _node(
            id="w3",
            type="capture",
            last_health={
                "_http": 200,
                "connectors": {"jitsi": {"status": "loaded"}},
                "workers": {"max": 4, "active": 1, "available": 3},
            },
            capture_connectors_json=["jitsi"],
            asr_models_json=None,
            diarization_models_json=None,
        ),
    ]
    summary = workers_availability_summary(
        nodes,
        capture_connectors=["jitsi"],
        import_max_concurrent=4,
    )
    assert summary["capture_capacity"] == {"max": 4, "active": 1, "available": 3}


def test_transcribe_capacity_from_health_workers_pool():
    nodes = [
        _node(
            last_health={
                "_http": 200,
                "engines": {"whisper": "loaded", "nemo": "loaded"},
                "workers": {"max": 2, "active": 0, "available": 2},
            },
        ),
    ]
    summary = workers_availability_summary(
        nodes,
        capture_connectors=["jitsi"],
        import_max_concurrent=4,
    )
    assert summary["transcribe_capacity"] == {"max": 2, "active": 0, "available": 2}


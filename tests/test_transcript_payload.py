from app.services.transcript_payload import (
    build_worker_payload,
    export_json_payload,
    extract_utterances,
    is_worker_payload,
    summarize_input_text,
)


def test_extract_utterances_from_worker_payload():
    payload = {
        "status": "success",
        "meta": {"asr_model": "whisper"},
        "transcript": [{"speaker": "A", "text": "hi"}],
        "error": None,
    }
    assert extract_utterances(payload) == [{"speaker": "A", "text": "hi"}]
    assert is_worker_payload(payload) is True


def test_extract_utterances_from_legacy_array():
    legacy = [{"speaker": "A", "text": "hi"}]
    assert extract_utterances(legacy) == legacy
    assert is_worker_payload(legacy) is False


def test_build_worker_payload():
    body = {
        "status": "success",
        "meta": {"audio_duration_sec": 12.5, "asr_model": "whisper"},
        "error": None,
    }
    utterances = [{"speaker": "A", "text": "hi"}]
    payload = build_worker_payload(body, utterances)
    assert payload["status"] == "success"
    assert payload["meta"]["audio_duration_sec"] == 12.5
    assert payload["transcript"] == utterances
    assert payload["error"] is None


def test_summarize_and_export_use_stored_payload():
    payload = build_worker_payload({"status": "success", "meta": {"task_id": "t1"}}, [])
    exported = export_json_payload(payload)
    assert exported == payload
    assert '"task_id": "t1"' in summarize_input_text(payload)

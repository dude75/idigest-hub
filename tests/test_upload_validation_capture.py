"""Capture artifact validation."""

import pytest

from app.services.upload_validation import (
    InvalidAudioContent,
    validate_capture_artifact_against_poll,
    validate_capture_download,
)


def test_validate_capture_rejects_size_mismatch_with_poll():
    content = b"ID3" + b"\x03\x00" + b"\x00" * 9 + b"\x00" * 498
    poll = {
        "artifact": {"size_bytes": len(content) + 100},
        "meta": {"duration_sec": 60.0},
    }
    validate_capture_download(content, {"content-type": "audio/mpeg"})
    with pytest.raises(InvalidAudioContent):
        validate_capture_artifact_against_poll(content, poll)


def test_validate_capture_accepts_matching_poll():
    content = b"ID3" + b"\x03\x00" + b"\x00" * 9 + b"\x00" * 498
    poll = {
        "artifact": {"size_bytes": len(content)},
        "meta": {"duration_sec": 60.0},
    }
    validate_capture_download(content, {"content-type": "audio/mpeg"})
    validate_capture_artifact_against_poll(content, poll)

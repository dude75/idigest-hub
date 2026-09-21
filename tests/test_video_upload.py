"""Video upload → MP3 extract."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from tests.conftest import (
    SAMPLE_MP3_BYTES,
    default_tariff_id,
    logout,
    setup_admin,
    signup,
    upload_audio,
)


def _login_org_uploader(client) -> None:
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    logout(client)
    assert signup(client, "vidup@example.com", "viduppass1", tariff_id).status_code == 200


def test_upload_rejects_unknown_suffix(client):
    _login_org_uploader(client)
    response = client.post(
        "/api/v1/audios",
        files={"file": ("clip.exe", BytesIO(b"data"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file"


def test_upload_video_extracts_mp3(client, tmp_path):
    _login_org_uploader(client)
    fake_mp3 = tmp_path / "out.mp3"
    fake_mp3.write_bytes(SAMPLE_MP3_BYTES + b"extracted")

    def _fake_extract(file, *, suffix: str, max_bytes: int) -> Path:
        return fake_mp3

    with patch("app.routers.library.video_upload_to_mp3_temp", side_effect=_fake_extract):
        with patch("app.routers.library.cleanup_extract_temp"):
            response = client.post(
                "/api/v1/audios",
                files={"file": ("talk.mp4", BytesIO(b"\x00" * 64), "video/mp4")},
            )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == "talk.mp3"
    assert body["id"]


def test_upload_video_extract_failure(client):
    _login_org_uploader(client)
    from app.services.video_extract import VideoExtractError

    with patch(
        "app.routers.library.video_upload_to_mp3_temp",
        side_effect=VideoExtractError("no_audio"),
    ):
        response = client.post(
            "/api/v1/audios",
            files={"file": ("silent.mp4", BytesIO(b"\x00" * 8), "video/mp4")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file"


def test_audio_upload_unchanged(client):
    _login_org_uploader(client)
    response = upload_audio(client, name="clip.wav")
    assert response.status_code == 200
    assert response.json()["filename"] == "clip.wav"

from tests.conftest import default_tariff_id, setup_admin, signup, upload_audio


def _tag_names(client, audio_id: str) -> set[str]:
    detail = client.get(f"/api/v1/audios/{audio_id}")
    assert detail.status_code == 200, detail.text
    return {t["name"] for t in detail.json().get("user_tags") or []}


def test_upload_auto_tags_file(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "uploadtag@example.com", "uploadtagpass1", tariff_id).status_code == 200

    created = upload_audio(client)
    assert created.status_code == 200, created.text
    body = created.json()
    assert {t["name"] for t in body.get("user_tags") or []} == {"upload"}
    assert _tag_names(client, body["id"]) == {"upload"}


def test_upload_auto_tags_mic(client, tmp_path):
    from io import BytesIO
    from unittest.mock import patch

    from tests.conftest import SAMPLE_MP3_BYTES

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "mictag@example.com", "mictagpass1", tariff_id).status_code == 200

    fake_mp3 = tmp_path / "mic.mp3"
    fake_mp3.write_bytes(SAMPLE_MP3_BYTES)

    def _fake_extract(file, *, suffix: str, max_bytes: int):
        return fake_mp3

    with patch("app.services.library_helpers.video_upload_to_mp3_temp", side_effect=_fake_extract):
        with patch("app.services.library_helpers.cleanup_extract_temp"):
            response = client.post(
                "/api/v1/audios",
                data={"from_microphone": "true"},
                files={"file": ("recording.webm", BytesIO(b"\x00" * 64), "audio/webm")},
            )
    assert response.status_code == 200, response.text
    audio_id = response.json()["id"]
    assert _tag_names(client, audio_id) == {"mic"}


def test_append_object_tags_keeps_existing(client, db):
    from sqlalchemy import select

    from app.models import User
    from app.services.user_tags import append_object_tags

    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "append@example.com", "appendpass1", tariff_id).status_code == 200
    audio_id = upload_audio(client).json()["id"]
    assert _tag_names(client, audio_id) == {"upload"}

    user = db.scalar(select(User).where(User.email == "append@example.com"))
    assert user is not None
    append_object_tags(
        db,
        user_id=user.id,
        object_type="audio",
        object_id=audio_id,
        tag_names=["Project", "upload"],
    )
    db.commit()

    assert _tag_names(client, audio_id) == {"Project", "upload"}

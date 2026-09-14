"""Storage backend unit tests."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import UploadFile

from app.services.storage import (
    LocalStorageBackend,
    PayloadTooLarge,
    S3StorageBackend,
    audio_object_key,
    get_storage,
    is_s3_ref,
    reset_storage,
)
from app.services.upload_validation import InvalidAudioContent
from tests.conftest import SAMPLE_MP3_BYTES, SAMPLE_WAV_BYTES


class _Upload(UploadFile):
    def __init__(self, data: bytes, filename: str = "clip.wav") -> None:
        super().__init__(file=BytesIO(data), filename=filename)

    async def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self.file.read(size)  # type: ignore[union-attr]


@pytest.fixture
def local_backend(tmp_path):
    return LocalStorageBackend(str(tmp_path))


@pytest.mark.asyncio
async def test_local_save_exists_delete_download(local_backend, tmp_path):
    upload = _Upload(SAMPLE_WAV_BYTES + b"audio-bytes")
    ref = await local_backend.save_upload("a1", ".wav", upload, max_bytes=1024)
    assert not is_s3_ref(ref)
    assert local_backend.exists(ref)
    response = local_backend.download_response(ref, "clip.wav", download=True)
    assert response.headers["content-disposition"].startswith("attachment")
    local_backend.delete(ref)
    assert not local_backend.exists(ref)


@pytest.mark.asyncio
async def test_local_save_file_path(local_backend, tmp_path):
    source = tmp_path / "source.mp3"
    source.write_bytes(SAMPLE_MP3_BYTES)
    ref = await local_backend.save_file_path("a2", ".mp3", source, max_bytes=1024)
    assert local_backend.exists(ref)


@pytest.mark.asyncio
async def test_local_payload_too_large(local_backend):
    upload = _Upload(SAMPLE_WAV_BYTES + b"x" * 32)
    with pytest.raises(PayloadTooLarge):
        await local_backend.save_upload("a2", ".wav", upload, max_bytes=16)


@pytest.mark.asyncio
async def test_local_path_for_worker(local_backend):
    payload = SAMPLE_WAV_BYTES + b"worker-bytes"
    upload = _Upload(payload)
    ref = await local_backend.save_upload("a3", ".wav", upload, max_bytes=1024)
    async with local_backend.local_path_for_worker(ref) as path:
        assert path.is_file()
        assert path.read_bytes() == payload


def test_audio_object_key():
    assert audio_object_key("id1", ".mp3") == "uploads/id1/original.mp3"


@pytest.mark.asyncio
async def test_local_rejects_invalid_magic(local_backend):
    upload = _Upload(b"MZ" + b"\x00" * 32, filename="clip.wav")
    with pytest.raises(InvalidAudioContent):
        await local_backend.save_upload("bad", ".wav", upload, max_bytes=1024)


@pytest.mark.asyncio
async def test_s3_save_and_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY", "key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret")
    monkeypatch.setenv("S3_SSE", "AES256")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_storage()

    client = MagicMock()
    with patch("boto3.client", return_value=client):
        backend = S3StorageBackend(get_settings())
        upload = _Upload(SAMPLE_WAV_BYTES + b"s3-payload")
        ref = await backend.save_upload("s3a", ".wav", upload, max_bytes=1024)

    assert ref == "s3://test-bucket/uploads/s3a/original.wav"
    client.upload_fileobj.assert_called_once()
    args, kwargs = client.upload_fileobj.call_args
    assert args[1] == "test-bucket"
    assert args[2] == "uploads/s3a/original.wav"
    assert kwargs["ExtraArgs"] == {"ServerSideEncryption": "AES256"}

    client.head_object.return_value = {}
    assert backend.exists(ref)

    from botocore.exceptions import ClientError

    client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
    assert not backend.exists(ref)
    client.head_object.side_effect = None
    client.head_object.return_value = {}

    def _download(_bucket, _key, dest):
        from pathlib import Path

        Path(dest).write_bytes(b"worker-bytes")

    client.download_file.side_effect = _download
    async with backend.local_path_for_worker(ref) as path:
        assert path.read_bytes() == b"worker-bytes"
    client.download_file.assert_called_once()
    assert client.download_file.call_args[0][0] == "test-bucket"
    assert client.download_file.call_args[0][1] == "uploads/s3a/original.wav"

    backend.delete(ref)
    client.delete_object.assert_called_with(
        Bucket="test-bucket", Key="uploads/s3a/original.wav"
    )

    get_settings.cache_clear()
    reset_storage()


def test_get_storage_local_default(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()
    reset_storage()
    storage = get_storage()
    assert isinstance(storage, LocalStorageBackend)
    get_settings.cache_clear()
    reset_storage()


@pytest.mark.asyncio
async def test_s3_upload_without_sse_header(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_SSE", "")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_storage()

    client = MagicMock()
    with patch("boto3.client", return_value=client):
        backend = S3StorageBackend(get_settings())
        upload = _Upload(SAMPLE_WAV_BYTES + b"plain")
        await backend.save_upload("y1", ".wav", upload, max_bytes=1024)

    _, kwargs = client.upload_fileobj.call_args
    assert kwargs["ExtraArgs"] is None

    get_settings.cache_clear()
    reset_storage()


@pytest.mark.asyncio
async def test_s3_multipart_upload(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_storage()

    client = MagicMock()
    client.create_multipart_upload.return_value = {"UploadId": "mpu-1"}
    client.upload_part.side_effect = lambda **kwargs: {
        "ETag": f"etag-{kwargs['PartNumber']}"
    }

    with patch("boto3.client", return_value=client):
        backend = S3StorageBackend(get_settings())
        payload = SAMPLE_WAV_BYTES + b"x" * (5 * 1024 * 1024 + 1024)
        upload = _Upload(payload)
        ref = await backend.save_upload("mp1", ".wav", upload, max_bytes=len(payload) + 1)

    assert ref == "s3://test-bucket/uploads/mp1/original.wav"
    client.create_multipart_upload.assert_called_once()
    assert client.upload_part.call_count == 2
    client.complete_multipart_upload.assert_called_once()
    client.upload_fileobj.assert_not_called()
    parts = client.complete_multipart_upload.call_args.kwargs["MultipartUpload"]["Parts"]
    assert len(parts) == 2
    assert parts[0]["PartNumber"] == 1
    assert parts[1]["PartNumber"] == 2

    get_settings.cache_clear()
    reset_storage()


@pytest.mark.asyncio
async def test_s3_upload_aws_kms(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_SSE", "aws:kms")
    monkeypatch.setenv("S3_SSE_KMS_KEY_ID", "abj123")
    from app.config import get_settings

    get_settings.cache_clear()
    reset_storage()

    client = MagicMock()
    with patch("boto3.client", return_value=client):
        backend = S3StorageBackend(get_settings())
        upload = _Upload(SAMPLE_MP3_BYTES + b"kms")
        await backend.save_upload("y2", ".mp3", upload, max_bytes=1024)

    _, kwargs = client.upload_fileobj.call_args
    assert kwargs["ExtraArgs"] == {
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": "abj123",
    }

    get_settings.cache_clear()
    reset_storage()

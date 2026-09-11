"""Audio blob storage: local filesystem or S3-compatible object storage."""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import unquote, urlparse

from fastapi import UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from app.config import Settings, get_settings
from app.services.export import safe_filename

log = logging.getLogger("app")

S3_SCHEME = "s3://"
_AUDIO_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def audio_object_key(audio_id: str, suffix: str) -> str:
    return f"uploads/{audio_id}/original{suffix}"


def is_s3_ref(storage_path: str) -> bool:
    return storage_path.startswith(S3_SCHEME)


def _mime_for_suffix(suffix: str) -> str:
    return _AUDIO_MIME.get(suffix.lower(), "application/octet-stream")


class StorageBackend(ABC):
    @abstractmethod
    async def save_upload(
        self,
        audio_id: str,
        suffix: str,
        file: UploadFile,
        *,
        max_bytes: int,
    ) -> str:
        """Persist upload; return opaque storage_path reference."""

    @abstractmethod
    async def save_file_path(
        self,
        audio_id: str,
        suffix: str,
        source: Path,
        *,
        max_bytes: int,
    ) -> str:
        """Copy a local file into storage; return opaque storage_path reference."""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        ...

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        ...

    @abstractmethod
    def download_response(
        self, storage_path: str, filename: str, *, download: bool
    ) -> Response:
        ...

    @abstractmethod
    @asynccontextmanager
    async def local_path_for_worker(self, storage_path: str) -> AsyncIterator[Path]:
        """Yield a local Path suitable for multipart upload to a worker."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, data_dir: str) -> None:
        self._root = Path(data_dir).expanduser().resolve()

    def _absolute_path(self, storage_path: str) -> Path:
        path = Path(storage_path)
        if not path.is_absolute():
            path = (self._root / path).resolve()
        return path

    async def save_upload(
        self,
        audio_id: str,
        suffix: str,
        file: UploadFile,
        *,
        max_bytes: int,
    ) -> str:
        dest_dir = self._root / "uploads" / audio_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"original{suffix}"
        size = 0
        try:
            with dest.open("wb") as handle:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        handle.close()
                        dest.unlink(missing_ok=True)
                        raise PayloadTooLarge()
                    handle.write(chunk)
        except PayloadTooLarge:
            raise
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        return str(dest)

    async def save_file_path(
        self,
        audio_id: str,
        suffix: str,
        source: Path,
        *,
        max_bytes: int,
    ) -> str:
        dest_dir = self._root / "uploads" / audio_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"original{suffix}"
        size = source.stat().st_size
        if size > max_bytes:
            raise PayloadTooLarge()
        dest.write_bytes(source.read_bytes())
        return str(dest)

    def exists(self, storage_path: str) -> bool:
        return self._absolute_path(storage_path).is_file()

    def delete(self, storage_path: str) -> None:
        path = self._absolute_path(storage_path)
        if path.is_file():
            path.unlink(missing_ok=True)
        parent = path.parent
        if parent.is_dir():
            try:
                next(parent.iterdir())
            except StopIteration:
                parent.rmdir()
            except OSError:
                pass

    def download_response(
        self, storage_path: str, filename: str, *, download: bool
    ) -> Response:
        path = self._absolute_path(storage_path)
        headers: dict[str, str] = {}
        if download:
            headers["Content-Disposition"] = (
                f'attachment; filename="{safe_filename(filename)}"'
            )
        return FileResponse(path, filename=filename, headers=headers)

    @asynccontextmanager
    async def local_path_for_worker(self, storage_path: str) -> AsyncIterator[Path]:
        yield self._absolute_path(storage_path)


class S3StorageBackend(StorageBackend):
    def __init__(self, settings: Settings) -> None:
        import boto3
        from botocore.config import Config

        if not settings.S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        self._bucket = settings.S3_BUCKET
        self._sse = settings.S3_SSE.strip() or None
        self._sse_kms_key_id = settings.S3_SSE_KMS_KEY_ID.strip() or None
        kwargs: dict = {
            "service_name": "s3",
            "aws_access_key_id": settings.S3_ACCESS_KEY or None,
            "aws_secret_access_key": settings.S3_SECRET_KEY or None,
            "region_name": settings.S3_REGION or None,
            "config": Config(signature_version="s3v4"),
        }
        if settings.S3_ENDPOINT:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT
        self._client = boto3.client(**kwargs)

    def _parse_ref(self, storage_path: str) -> tuple[str, str]:
        if not is_s3_ref(storage_path):
            raise ValueError(f"not an s3 storage ref: {storage_path!r}")
        parsed = urlparse(storage_path)
        bucket = parsed.netloc
        key = unquote(parsed.path.lstrip("/"))
        if bucket != self._bucket:
            raise ValueError(f"s3 ref bucket {bucket!r} != configured {self._bucket!r}")
        return bucket, key

    def _ref(self, key: str) -> str:
        return f"{S3_SCHEME}{self._bucket}/{key}"

    def _upload_extra_args(self) -> dict[str, str] | None:
        if not self._sse:
            return None
        extra: dict[str, str] = {"ServerSideEncryption": self._sse}
        if self._sse == "aws:kms" and self._sse_kms_key_id:
            extra["SSEKMSKeyId"] = self._sse_kms_key_id
        return extra

    async def save_upload(
        self,
        audio_id: str,
        suffix: str,
        file: UploadFile,
        *,
        max_bytes: int,
    ) -> str:
        key = audio_object_key(audio_id, suffix)
        extra_args = self._upload_extra_args()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise PayloadTooLarge()
                buffer.write(chunk)
            buffer.seek(0)
            self._client.upload_fileobj(buffer, self._bucket, key, ExtraArgs=extra_args)
        return self._ref(key)

    async def save_file_path(
        self,
        audio_id: str,
        suffix: str,
        source: Path,
        *,
        max_bytes: int,
    ) -> str:
        key = audio_object_key(audio_id, suffix)
        size = source.stat().st_size
        if size > max_bytes:
            raise PayloadTooLarge()
        extra_args = self._upload_extra_args()
        with source.open("rb") as handle:
            self._client.upload_fileobj(handle, self._bucket, key, ExtraArgs=extra_args)
        return self._ref(key)

    def exists(self, storage_path: str) -> bool:
        from botocore.exceptions import ClientError

        _, key = self._parse_ref(storage_path)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def delete(self, storage_path: str) -> None:
        _, key = self._parse_ref(storage_path)
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def download_response(
        self, storage_path: str, filename: str, *, download: bool
    ) -> Response:
        _, key = self._parse_ref(storage_path)
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        body = obj["Body"]
        suffix = Path(key).suffix
        media_type = obj.get("ContentType") or _mime_for_suffix(suffix)
        headers: dict[str, str] = {}
        if download:
            headers["Content-Disposition"] = (
                f'attachment; filename="{safe_filename(filename)}"'
            )

        def _iter():
            try:
                yield from body.iter_chunks()
            finally:
                body.close()

        return StreamingResponse(_iter(), media_type=media_type, headers=headers)

    @asynccontextmanager
    async def local_path_for_worker(self, storage_path: str) -> AsyncIterator[Path]:
        _, key = self._parse_ref(storage_path)
        suffix = Path(key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        try:
            tmp.close()
            self._client.download_file(self._bucket, key, str(tmp_path))
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)


class PayloadTooLarge(Exception):
    """Upload exceeded configured max_bytes."""


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.STORAGE_BACKEND == "s3":
            _storage = S3StorageBackend(settings)
        else:
            _storage = LocalStorageBackend(settings.DATA_DIR)
    return _storage


def reset_storage() -> None:
    """Test helper: drop cached backend after env changes."""
    global _storage
    _storage = None

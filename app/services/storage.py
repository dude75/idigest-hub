"""Audio blob storage: local filesystem or S3-compatible object storage."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from abc import ABC, abstractmethod
from io import BytesIO
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import unquote, urlparse

from fastapi import UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from app.config import Settings, get_settings
from app.services.export import content_disposition_attachment, safe_filename
from app.services.upload_validation import InvalidAudioContent, validate_audio_header

log = logging.getLogger("app")

S3_SCHEME = "s3://"
# S3 multipart minimum part size (except the trailing part).
_S3_PART_SIZE = 5 * 1024 * 1024
_S3_CONNECT_TIMEOUT_SEC = 5
_S3_READ_TIMEOUT_SEC = 30
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


def _parse_byte_range(range_header: str, total: int) -> tuple[int, int] | None:
    """Parse a single HTTP Range value; return inclusive (start, end) or None."""
    spec = range_header.strip()
    if not spec.lower().startswith("bytes="):
        return None
    spec = spec[6:].strip()
    if not spec or "," in spec:
        return None
    if spec.startswith("-"):
        try:
            suffix_len = int(spec[1:])
        except ValueError:
            return None
        if suffix_len <= 0:
            return None
        start = max(0, total - suffix_len)
        end = total - 1
    else:
        start_str, _, end_str = spec.partition("-")
        try:
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else total - 1
        except ValueError:
            return None
    if start < 0 or end < start or start >= total:
        return None
    return start, min(end, total - 1)


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
    def save_bytes(
        self,
        audio_id: str,
        suffix: str,
        data: bytes,
        *,
        max_bytes: int,
    ) -> str:
        """Persist raw bytes; return opaque storage_path reference."""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        ...

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        ...

    @abstractmethod
    def download_response(
        self,
        storage_path: str,
        filename: str,
        *,
        download: bool,
        range_header: str | None = None,
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
        try:
            with dest.open("wb") as handle:
                await _stream_upload_with_magic_check(
                    file,
                    suffix=suffix,
                    max_bytes=max_bytes,
                    write_bytes=handle.write,
                )
        except (PayloadTooLarge, InvalidAudioContent):
            dest.unlink(missing_ok=True)
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
        data = source.read_bytes()
        if len(data) > max_bytes:
            raise PayloadTooLarge()
        validate_audio_header(suffix, data[:_MAGIC_HEADER_LEN])
        dest.write_bytes(data)
        return str(dest)

    def save_bytes(
        self,
        audio_id: str,
        suffix: str,
        data: bytes,
        *,
        max_bytes: int,
    ) -> str:
        if len(data) > max_bytes:
            raise PayloadTooLarge()
        validate_audio_header(suffix, data[:_MAGIC_HEADER_LEN])
        dest_dir = self._root / "uploads" / audio_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"original{suffix}"
        dest.write_bytes(data)
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
        self,
        storage_path: str,
        filename: str,
        *,
        download: bool,
        range_header: str | None = None,
    ) -> Response:
        path = self._absolute_path(storage_path)
        headers: dict[str, str] = {}
        if download:
            return FileResponse(path, filename=safe_filename(filename))
        return FileResponse(path, headers=headers)

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
            "config": Config(
                signature_version="s3v4",
                connect_timeout=_S3_CONNECT_TIMEOUT_SEC,
                read_timeout=_S3_READ_TIMEOUT_SEC,
            ),
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

    def _create_multipart_upload(self, key: str) -> str:
        kwargs: dict = {"Bucket": self._bucket, "Key": key}
        extra = self._upload_extra_args()
        if extra:
            kwargs.update(extra)
        return self._client.create_multipart_upload(**kwargs)["UploadId"]

    def _upload_part_sync(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> dict:
        resp = self._client.upload_part(
            Bucket=self._bucket,
            Key=key,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=data,
        )
        return {"PartNumber": part_number, "ETag": resp["ETag"]}

    def _complete_multipart_sync(
        self, key: str, upload_id: str, parts: list[dict]
    ) -> None:
        self._client.complete_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": sorted(parts, key=lambda part: part["PartNumber"])},
        )

    def _abort_multipart_sync(self, key: str, upload_id: str) -> None:
        try:
            self._client.abort_multipart_upload(
                Bucket=self._bucket, Key=key, UploadId=upload_id
            )
        except Exception:
            log.exception(
                "abort_multipart_upload failed key=%s upload_id=%s", key, upload_id
            )

    def _upload_fileobj_sync(self, fileobj, key: str) -> None:
        self._client.upload_fileobj(
            fileobj, self._bucket, key, ExtraArgs=self._upload_extra_args()
        )

    async def save_upload(
        self,
        audio_id: str,
        suffix: str,
        file: UploadFile,
        *,
        max_bytes: int,
    ) -> str:
        key = audio_object_key(audio_id, suffix)
        header = await file.read(_MAGIC_HEADER_LEN)
        if not header:
            raise InvalidAudioContent()
        validate_audio_header(suffix, header)
        size = len(header)
        pending = bytearray(header)
        upload_id: str | None = None
        parts: list[dict] = []
        part_number = 1

        async def abort_if_needed() -> None:
            if upload_id:
                await asyncio.to_thread(self._abort_multipart_sync, key, upload_id)

        try:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    await abort_if_needed()
                    raise PayloadTooLarge()
                pending.extend(chunk)

                while len(pending) >= _S3_PART_SIZE:
                    if upload_id is None:
                        upload_id = await asyncio.to_thread(
                            self._create_multipart_upload, key
                        )
                    part_data = bytes(pending[:_S3_PART_SIZE])
                    del pending[:_S3_PART_SIZE]
                    part = await asyncio.to_thread(
                        self._upload_part_sync, key, upload_id, part_number, part_data
                    )
                    parts.append(part)
                    part_number += 1

            if upload_id is None:
                await asyncio.to_thread(
                    self._upload_fileobj_sync, BytesIO(bytes(pending)), key
                )
            else:
                if pending:
                    part = await asyncio.to_thread(
                        self._upload_part_sync,
                        key,
                        upload_id,
                        part_number,
                        bytes(pending),
                    )
                    parts.append(part)
                await asyncio.to_thread(
                    self._complete_multipart_sync, key, upload_id, parts
                )
        except (PayloadTooLarge, InvalidAudioContent):
            raise
        except Exception:
            await abort_if_needed()
            raise

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
        data = source.read_bytes()
        if len(data) > max_bytes:
            raise PayloadTooLarge()
        validate_audio_header(suffix, data[:_MAGIC_HEADER_LEN])

        def _upload() -> None:
            with source.open("rb") as handle:
                self._client.upload_fileobj(
                    handle, self._bucket, key, ExtraArgs=self._upload_extra_args()
                )

        await asyncio.to_thread(_upload)
        return self._ref(key)

    def save_bytes(
        self,
        audio_id: str,
        suffix: str,
        data: bytes,
        *,
        max_bytes: int,
    ) -> str:
        if len(data) > max_bytes:
            raise PayloadTooLarge()
        validate_audio_header(suffix, data[:_MAGIC_HEADER_LEN])
        key = audio_object_key(audio_id, suffix)
        self._upload_fileobj_sync(BytesIO(data), key)
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
        self,
        storage_path: str,
        filename: str,
        *,
        download: bool,
        range_header: str | None = None,
    ) -> Response:
        _, key = self._parse_ref(storage_path)
        head = self._client.head_object(Bucket=self._bucket, Key=key)
        total = int(head["ContentLength"])
        suffix = Path(key).suffix
        media_type = head.get("ContentType") or _mime_for_suffix(suffix)
        headers: dict[str, str] = {"Accept-Ranges": "bytes"}
        if download:
            headers["Content-Disposition"] = content_disposition_attachment(filename)

        byte_range = (
            _parse_byte_range(range_header, total) if range_header else None
        )
        if range_header and byte_range is None:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{total}"},
            )

        get_kwargs: dict = {"Bucket": self._bucket, "Key": key}
        status_code = 200
        content_length = total
        if byte_range is not None:
            start, end = byte_range
            get_kwargs["Range"] = f"bytes={start}-{end}"
            status_code = 206
            content_length = end - start + 1
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        obj = self._client.get_object(**get_kwargs)
        body = obj["Body"]
        headers["Content-Length"] = str(content_length)

        def _iter():
            try:
                yield from body.iter_chunks()
            finally:
                body.close()

        return StreamingResponse(
            _iter(), status_code=status_code, media_type=media_type, headers=headers
        )

    @asynccontextmanager
    async def local_path_for_worker(self, storage_path: str) -> AsyncIterator[Path]:
        _, key = self._parse_ref(storage_path)
        suffix = Path(key).suffix or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        try:
            tmp.close()
            await asyncio.to_thread(
                self._client.download_file, self._bucket, key, str(tmp_path)
            )
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)


class PayloadTooLarge(Exception):
    """Upload exceeded configured max_bytes."""


_MAGIC_HEADER_LEN = 12


async def _stream_upload_with_magic_check(
    file: UploadFile,
    *,
    suffix: str,
    max_bytes: int,
    write_bytes,
) -> None:
    header = await file.read(_MAGIC_HEADER_LEN)
    if not header:
        raise InvalidAudioContent()
    validate_audio_header(suffix, header)
    size = len(header)
    write_bytes(header)
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise PayloadTooLarge()
        write_bytes(chunk)


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

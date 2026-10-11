"""Shared helpers for offline S3 ↔ local uploads migration scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from app.config import Settings

UPLOADS_PREFIX = "uploads/"


def prepare_script_env() -> Path:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def data_dir_path(settings: Settings) -> Path:
    return Path(settings.DATA_DIR).expanduser().resolve()


def uploads_dir(settings: Settings) -> Path:
    return data_dir_path(settings) / "uploads"


def require_s3_bucket(settings: Settings) -> str:
    bucket = settings.S3_BUCKET.strip()
    if not bucket:
        raise SystemExit("S3_BUCKET is required (set in .env)")
    return bucket


def s3_client(settings: Settings):
    import boto3
    from botocore.config import Config

    kwargs: dict = {
        "service_name": "s3",
        "aws_access_key_id": settings.S3_ACCESS_KEY or None,
        "aws_secret_access_key": settings.S3_SECRET_KEY or None,
        "region_name": settings.S3_REGION or None,
        "config": Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=120,
        ),
    }
    endpoint = settings.S3_ENDPOINT.strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(**kwargs)


def s3_upload_extra_args(settings: Settings) -> dict[str, str] | None:
    sse = settings.S3_SSE.strip()
    if not sse:
        return None
    extra: dict[str, str] = {"ServerSideEncryption": sse}
    kms_id = settings.S3_SSE_KMS_KEY_ID.strip()
    if sse == "aws:kms" and kms_id:
        extra["SSEKMSKeyId"] = kms_id
    return extra


def normalize_prefix(prefix: str) -> str:
    p = prefix.strip().lstrip("/")
    if p and not p.endswith("/"):
        p += "/"
    return p


def iter_s3_objects(
    client,
    bucket: str,
    prefix: str,
) -> Iterator[tuple[str, int]]:
    """Yield (key, size_bytes) for all objects under prefix."""
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents") or ():
            key = item["Key"]
            if key.endswith("/"):
                continue
            yield key, int(item["Size"])


def iter_local_upload_files(uploads_root: Path) -> Iterator[tuple[str, Path, int]]:
    """Yield (s3_key, path, size_bytes) for files under uploads/."""
    if not uploads_root.is_dir():
        return
    for path in uploads_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(uploads_root).as_posix()
        yield f"{UPLOADS_PREFIX}{rel}", path, path.stat().st_size


def local_path_for_key(data_root: Path, key: str) -> Path:
    if key.startswith(UPLOADS_PREFIX):
        return data_root / key
    return data_root / UPLOADS_PREFIX / key.lstrip("/")


def should_skip_existing(*, dest_size: int, source_size: int, overwrite: bool) -> bool:
    if overwrite:
        return False
    return dest_size == source_size

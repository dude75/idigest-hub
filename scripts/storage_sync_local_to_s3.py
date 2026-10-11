#!/usr/bin/env python3
"""Upload audio files from {DATA_DIR}/uploads/ to S3-compatible storage."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy local {DATA_DIR}/uploads/ files into the configured S3 bucket. "
            "Credentials and bucket come from .env (S3_* and DATA_DIR). "
            "Honours S3_SSE / S3_SSE_KMS_KEY_ID on upload when set."
        ),
    )
    parser.add_argument(
        "--prefix",
        default="uploads/",
        help="Only upload files whose S3 key starts with this prefix (default: 'uploads/').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned transfers without uploading.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Upload even when remote object size matches local.",
    )
    return parser


def remote_size(client, bucket: str, key: str) -> int | None:
    from botocore.exceptions import ClientError

    try:
        head = client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    return int(head["ContentLength"])


def main(argv: list[str] | None = None) -> int:
    from storage_migrate_lib import prepare_script_env

    prepare_script_env()
    from storage_migrate_lib import (
        iter_local_upload_files,
        normalize_prefix,
        require_s3_bucket,
        s3_client,
        s3_upload_extra_args,
        should_skip_existing,
        uploads_dir,
    )
    args = build_parser().parse_args(argv)

    from app.config import get_settings

    settings = get_settings()
    bucket = require_s3_bucket(settings)
    prefix = normalize_prefix(args.prefix)
    uploads_root = uploads_dir(settings)
    if not uploads_root.is_dir():
        print(f"no local uploads directory: {uploads_root}", file=sys.stderr)
        return 0

    client = s3_client(settings)
    extra = s3_upload_extra_args(settings)

    copied = skipped = errors = 0
    for key, path, local_size in iter_local_upload_files(uploads_root):
        if not key.startswith(prefix):
            continue
        if not args.overwrite:
            try:
                existing = remote_size(client, bucket, key)
            except Exception as exc:
                errors += 1
                print(f"error head {key}: {exc}", file=sys.stderr)
                continue
            if existing is not None and should_skip_existing(
                dest_size=existing,
                source_size=local_size,
                overwrite=False,
            ):
                skipped += 1
                continue
        if args.dry_run:
            print(f"PUT {path} -> s3://{bucket}/{key}")
            copied += 1
            continue
        try:
            client.upload_file(
                str(path),
                bucket,
                key,
                ExtraArgs=extra,
            )
            copied += 1
            print(f"ok {key} ({local_size} bytes)")
        except OSError as exc:
            errors += 1
            print(f"error {key}: {exc}", file=sys.stderr)

    print(
        f"done bucket={bucket!r} prefix={prefix!r} uploads={uploads_root} "
        f"uploaded={copied} skipped={skipped} errors={errors}"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Download audio uploads from S3-compatible storage into {DATA_DIR}/uploads/."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy objects from the configured S3 bucket into local {DATA_DIR}/uploads/. "
            "Credentials and bucket come from .env (S3_* and DATA_DIR)."
        ),
    )
    parser.add_argument(
        "--prefix",
        default="uploads/",
        help="S3 key prefix to sync (default: 'uploads/').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned transfers without writing files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download even when local file size matches S3.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from storage_migrate_lib import prepare_script_env

    prepare_script_env()
    from storage_migrate_lib import (
        data_dir_path,
        iter_s3_objects,
        local_path_for_key,
        normalize_prefix,
        require_s3_bucket,
        s3_client,
        should_skip_existing,
    )
    args = build_parser().parse_args(argv)

    from app.config import get_settings

    settings = get_settings()
    bucket = require_s3_bucket(settings)
    prefix = normalize_prefix(args.prefix)
    data_root = data_dir_path(settings)
    client = s3_client(settings)

    copied = skipped = errors = 0
    for key, remote_size in iter_s3_objects(client, bucket, prefix):
        dest = local_path_for_key(data_root, key)
        if dest.is_file() and should_skip_existing(
            dest_size=dest.stat().st_size,
            source_size=remote_size,
            overwrite=args.overwrite,
        ):
            skipped += 1
            continue
        if args.dry_run:
            print(f"GET s3://{bucket}/{key} -> {dest}")
            copied += 1
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(dest))
            copied += 1
            print(f"ok {key} ({remote_size} bytes)")
        except OSError as exc:
            errors += 1
            print(f"error {key}: {exc}", file=sys.stderr)

    print(
        f"done bucket={bucket!r} prefix={prefix!r} data_dir={data_root} "
        f"copied={copied} skipped={skipped} errors={errors}"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

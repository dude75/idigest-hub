"""Persistent data paths under DATA_DIR (uploads, logs, ephemeral tmp)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.config import Settings

HUB_IMPORT_TMP_PREFIX = "hub-import-"
HUB_VIDEO_UPLOAD_TMP_PREFIX = "hub-video-upload-"
YTDLP_CACHE_DIRNAME = "yt-dlp"


def hub_data_dir(settings: Settings) -> Path:
    return Path(settings.DATA_DIR).expanduser().resolve()


def hub_tmp_root(settings: Settings) -> Path:
    return hub_data_dir(settings) / "tmp"


def hub_ytdlp_cache_dir(settings: Settings) -> Path:
    return hub_tmp_root(settings) / YTDLP_CACHE_DIRNAME


def ensure_hub_tmp(settings: Settings) -> Path:
    root = hub_tmp_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_hub_import_tmpdir(settings: Settings) -> Path:
    root = ensure_hub_tmp(settings)
    return Path(tempfile.mkdtemp(prefix=HUB_IMPORT_TMP_PREFIX, dir=str(root)))


def make_hub_video_upload_tmpdir(settings: Settings) -> Path:
    root = ensure_hub_tmp(settings)
    return Path(tempfile.mkdtemp(prefix=HUB_VIDEO_UPLOAD_TMP_PREFIX, dir=str(root)))


def is_hub_import_tmpdir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith(HUB_IMPORT_TMP_PREFIX)


def import_tmpdir_for_path(path: Path) -> Path | None:
    """Return hub-import temp dir containing path, if any."""
    current = path.resolve()
    while True:
        if is_hub_import_tmpdir(current):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent

"""Persistent data paths under DATA_DIR (uploads, logs, ephemeral tmp)."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.config import Settings

log = logging.getLogger("app")

HUB_IMPORT_TMP_PREFIX = "hub-import-"
HUB_VIDEO_UPLOAD_TMP_PREFIX = "hub-video-upload-"
YTDLP_CACHE_DIRNAME = "yt-dlp"


def hub_data_dir(settings: Settings) -> Path:
    return Path(settings.DATA_DIR).expanduser().resolve()


def hub_tmp_root(settings: Settings) -> Path:
    return hub_data_dir(settings) / "tmp"


def hub_xdg_cache_home(settings: Settings) -> Path:
    return hub_tmp_root(settings) / "cache"


def hub_ytdlp_cache_dir(settings: Settings) -> Path:
    return hub_xdg_cache_home(settings) / YTDLP_CACHE_DIRNAME


def ensure_hub_tmp(settings: Settings) -> Path:
    root = hub_tmp_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    return root


def configure_ytdlp_cache_environment(settings: Settings) -> Path:
    """yt-dlp reads XDG_CACHE_HOME/yt-dlp; migrate legacy caches from local dev / first deploy."""
    ensure_hub_tmp(settings)
    xdg = hub_xdg_cache_home(settings)
    xdg.mkdir(parents=True, exist_ok=True)
    os.environ["XDG_CACHE_HOME"] = str(xdg)

    dest = hub_ytdlp_cache_dir(settings)
    if dest.is_dir() and any(dest.iterdir()):
        return dest

    legacy_paths = (
        Path.home() / ".cache" / YTDLP_CACHE_DIRNAME,
        hub_tmp_root(settings) / YTDLP_CACHE_DIRNAME,
    )
    for legacy in legacy_paths:
        if not legacy.is_dir() or not any(legacy.iterdir()):
            continue
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(legacy, dest)
            log.info("migrated yt-dlp cache from %s to %s", legacy, dest)
            return dest
        except OSError:
            log.exception("yt-dlp cache migration failed from %s", legacy)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


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

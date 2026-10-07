"""Extract MP3 audio from uploaded video via ffmpeg."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings
from app.paths import HUB_VIDEO_UPLOAD_TMP_PREFIX, make_hub_video_upload_tmpdir
from app.constants import DEFAULT_VIDEO_EXTRACT_FFMPEG_TIMEOUT_SEC
from app.services.import_platforms import DEFAULT_IMPORT_AUDIO_BITRATE_KBPS
from app.services.storage import PayloadTooLarge
from app.services.upload_validation import validate_audio_header

log = logging.getLogger("app")

_CHUNK = 1024 * 1024


class VideoExtractError(Exception):
    """Video could not be converted to MP3 (missing audio, corrupt file, ffmpeg failure)."""


async def stream_upload_to_file(file: UploadFile, dest: Path, *, max_bytes: int) -> None:
    size = 0
    with dest.open("wb") as handle:
        while True:
            chunk = await file.read(_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise PayloadTooLarge()
            handle.write(chunk)
    if size == 0:
        raise VideoExtractError("empty_file")


def _ffmpeg_timeout_sec() -> float:
    settings = get_settings()
    try:
        value = int(settings.VIDEO_EXTRACT_FFMPEG_TIMEOUT_SEC)
    except (TypeError, ValueError):
        value = DEFAULT_VIDEO_EXTRACT_FFMPEG_TIMEOUT_SEC
    return float(max(1, value))


def _run_probe(source: Path, timeout: float) -> None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoExtractError("timeout") from exc
    if proc.returncode != 0:
        raise VideoExtractError("probe_failed")
    if proc.stdout.strip().lower() != b"audio":
        raise VideoExtractError("no_audio")


def _run_extract(source: Path, dest: Path, *, bitrate_kbps: int, timeout: float) -> None:
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-b:a",
                f"{bitrate_kbps}k",
                str(dest),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoExtractError("timeout") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or b"")[-500:]
        log.warning("ffmpeg extract failed rc=%s stderr=%s", proc.returncode, detail)
        raise VideoExtractError("ffmpeg_failed")
    if not dest.is_file() or dest.stat().st_size == 0:
        raise VideoExtractError("empty_output")
    header = dest.read_bytes()[:12]
    validate_audio_header(".mp3", header)


def media_file_to_mp3(
    source: Path,
    dest: Path,
    *,
    bitrate_kbps: int = 0,
) -> None:
    """Extract/normalize any media file with an audio stream to MP3 on disk."""
    timeout = _ffmpeg_timeout_sec()
    kbps = bitrate_kbps if bitrate_kbps > 0 else DEFAULT_IMPORT_AUDIO_BITRATE_KBPS
    try:
        _run_probe(source, timeout=timeout)
        _run_extract(source, dest, bitrate_kbps=kbps, timeout=timeout)
    except FileNotFoundError as exc:
        raise VideoExtractError("ffmpeg_missing") from exc


def _extract_sync(source: Path, mp3_path: Path) -> None:
    media_file_to_mp3(source, mp3_path)


async def video_upload_to_mp3_temp(
    file: UploadFile,
    *,
    suffix: str,
    max_bytes: int,
) -> Path:
    """Stream video upload to a temp file, return path to extracted MP3 (caller cleans up parent dir)."""
    tmpdir = make_hub_video_upload_tmpdir(get_settings())
    source = tmpdir / f"source{suffix.lower()}"
    mp3_path = tmpdir / "extracted.mp3"
    try:
        await stream_upload_to_file(file, source, max_bytes=max_bytes)
        await asyncio.to_thread(_extract_sync, source, mp3_path)
        source.unlink(missing_ok=True)
        return mp3_path
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def cleanup_extract_temp(mp3_path: Path) -> None:
    parent = mp3_path.parent
    if mp3_path.is_file():
        mp3_path.unlink(missing_ok=True)
    if parent.is_dir() and parent.name.startswith(HUB_VIDEO_UPLOAD_TMP_PREFIX):
        shutil.rmtree(parent, ignore_errors=True)

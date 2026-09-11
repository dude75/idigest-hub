"""Download audio from supported URLs via yt-dlp."""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.services.export import safe_filename
from app.services.import_platforms import (
    DEFAULT_IMPORT_AUDIO_BITRATE_KBPS,
    allowed_extractors,
    catalog_entry,
    catalog_platform_for_host,
    host_from_url,
)

log = logging.getLogger("app.import")

ProgressCallback = Callable[[str, dict[str, Any]], None]

_ERROR_DETAIL_MAX_LEN = 500

# YouTube player clients to try when the default path returns HTTP 403.
_YOUTUBE_CLIENT_FALLBACKS: tuple[list[str], ...] = (
    ["default", "web_embedded"],
    ["android"],
    ["ios"],
    ["web"],
    ["mweb"],
)


@dataclass
class ImportResult:
    source_path: Path
    suffix: str
    original_filename: str
    title: str | None
    duration_sec: float | None
    extractor_key: str
    host: str
    platform_label: str


class UrlImportError(Exception):
    def __init__(self, code: str, *, meta: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.meta = meta or {}


_URL_RE = re.compile(r"^https?://", re.I)


def _is_youtube_host(host: str) -> bool:
    return host in {"youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com"} or host.endswith(
        ".youtube.com"
    )


def _is_403_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "403" in msg or "forbidden" in msg


def _clear_ytdl_cache() -> None:
    try:
        from yt_dlp.cache import Cache

        Cache().remove()
    except Exception:
        pass


def _cookies_file(cookies_path: str | None) -> str | None:
    if not cookies_path:
        return None
    path = Path(cookies_path.strip()).expanduser()
    if path.is_file():
        return str(path.resolve())
    return None


def _error_detail(exc: BaseException, *, max_len: int = _ERROR_DETAIL_MAX_LEN) -> str:
    msg = str(exc).strip()
    if len(msg) <= max_len:
        return msg
    return msg[: max_len - 3] + "..."


def _ydl_error_meta(
    exc: BaseException,
    *,
    host: str,
    proxy: str | None,
    youtube_client: list[str] | None = None,
    youtube_clients_tried: list[list[str] | None] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"host": host, "error_detail": _error_detail(exc)}
    if youtube_client is not None:
        meta["youtube_client"] = youtube_client
    if youtube_clients_tried:
        meta["youtube_clients_tried"] = youtube_clients_tried
    if proxy:
        meta["proxy_used"] = True
    return meta


def _raise_ydl_error(
    exc: BaseException,
    *,
    host: str,
    proxy: str | None,
    default_code: str = "download_failed",
    youtube_client: list[str] | None = None,
    youtube_clients_tried: list[list[str] | None] | None = None,
) -> None:
    meta = _ydl_error_meta(
        exc,
        host=host,
        proxy=proxy,
        youtube_client=youtube_client,
        youtube_clients_tried=youtube_clients_tried,
    )
    msg = str(exc).lower()
    if proxy and "port" in msg:
        meta["reason"] = "proxy_misconfigured"
        raise UrlImportError("download_failed", meta=meta) from exc
    if _is_403_error(exc):
        meta["reason"] = "blocked_403"
        raise UrlImportError("video_unavailable", meta=meta) from exc
    raise UrlImportError(default_code, meta=meta) from exc


def _audio_format_selector(max_bitrate_kbps: int) -> str:
    if max_bitrate_kbps > 0:
        return f"bestaudio[abr<={max_bitrate_kbps}]/bestaudio/best"
    return "bestaudio/best"


def _ydl_opts(
    proxy: str | None,
    *,
    cookies_path: str | None = None,
    max_audio_bitrate_kbps: int = 0,
    youtube_clients: list[str] | None = None,
    outtmpl: str | None = None,
    download: bool = False,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "skip_download": not download,
    }
    if proxy:
        opts["proxy"] = proxy
    cookiefile = _cookies_file(cookies_path)
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if outtmpl:
        opts["outtmpl"] = outtmpl
        opts["format"] = _audio_format_selector(max_audio_bitrate_kbps)
        quality = (
            str(max_audio_bitrate_kbps)
            if max_audio_bitrate_kbps > 0
            else str(DEFAULT_IMPORT_AUDIO_BITRATE_KBPS)
        )
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }
        ]
    if youtube_clients:
        opts["extractor_args"] = {"youtube": {"player_client": youtube_clients}}
    return opts


def _youtube_client_attempts(host: str) -> tuple[list[str] | None, ...]:
    if not _is_youtube_host(host):
        return (None,)
    return _YOUTUBE_CLIENT_FALLBACKS


def _run_ytdl(
    url: str,
    *,
    host: str,
    proxy: str | None,
    cookies_path: str | None,
    max_audio_bitrate_kbps: int,
    download: bool,
    outtmpl: str | None = None,
) -> dict[str, Any]:
    import yt_dlp
    from yt_dlp.utils import DownloadError, ExtractorError

    attempts = _youtube_client_attempts(host)
    last_exc: BaseException | None = None
    cleared_cache = False
    clients_tried: list[list[str] | None] = []

    for index, clients in enumerate(attempts):
        clients_tried.append(clients)
        if index > 0 and not cleared_cache:
            _clear_ytdl_cache()
            cleared_cache = True
        opts = _ydl_opts(
            proxy,
            cookies_path=cookies_path,
            max_audio_bitrate_kbps=max_audio_bitrate_kbps,
            youtube_clients=clients,
            outtmpl=outtmpl,
            download=download,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
            if not isinstance(info, dict):
                raise UrlImportError("download_failed", meta={"host": host})
            return info
        except UrlImportError:
            raise
        except (ExtractorError, DownloadError) as exc:
            last_exc = exc
            if _is_403_error(exc) and index + 1 < len(attempts):
                log.warning(
                    "yt-dlp blocked host=%s client=%s detail=%s; trying next client",
                    host,
                    clients,
                    _error_detail(exc),
                )
                continue
            if isinstance(exc, ExtractorError):
                msg = str(exc).lower()
                if "unsupported url" in msg or "no suitable extractor" in msg:
                    platform = catalog_platform_for_host(host)
                    raise UrlImportError(
                        "unsupported_host",
                        meta={
                            "host": host,
                            "platform": (platform or {}).get("label") or host,
                            "reason": "not_in_catalog",
                            "error_detail": _error_detail(exc),
                        },
                    ) from exc
                _raise_ydl_error(
                    exc,
                    host=host,
                    proxy=proxy,
                    default_code="video_unavailable",
                    youtube_client=clients,
                    youtube_clients_tried=clients_tried,
                )
            _raise_ydl_error(
                exc,
                host=host,
                proxy=proxy,
                youtube_client=clients,
                youtube_clients_tried=clients_tried,
            )
        except Exception as exc:
            last_exc = exc
            if _is_403_error(exc) and index + 1 < len(attempts):
                log.warning(
                    "yt-dlp blocked host=%s client=%s detail=%s; trying next client",
                    host,
                    clients,
                    _error_detail(exc),
                )
                continue
            _raise_ydl_error(
                exc,
                host=host,
                proxy=proxy,
                default_code="video_unavailable",
                youtube_client=clients,
                youtube_clients_tried=clients_tried,
            )

    if last_exc is not None:
        _raise_ydl_error(
            last_exc,
            host=host,
            proxy=proxy,
            default_code="video_unavailable",
            youtube_client=clients_tried[-1] if clients_tried else None,
            youtube_clients_tried=clients_tried,
        )
    raise UrlImportError("download_failed", meta={"host": host})


def validate_import_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned or not _URL_RE.match(cleaned):
        raise UrlImportError("invalid_url")
    host = host_from_url(cleaned)
    if not host:
        raise UrlImportError("invalid_url")
    return cleaned


def _check_extractor(
    extractor_key: str | None,
    *,
    settings_allowed: list[str],
    host: str,
) -> tuple[str, str, str]:
    key = (extractor_key or "").strip()
    catalog = catalog_entry(key) if key else None
    platform = catalog_platform_for_host(host)
    platform_label = (catalog or platform or {}).get("label") or host or "unknown"
    if not key:
        raise UrlImportError(
            "unsupported_host",
            meta={"host": host, "platform": platform_label, "reason": "not_in_catalog"},
        )
    if catalog is None:
        raise UrlImportError(
            "unsupported_host",
            meta={
                "host": host,
                "platform": platform_label,
                "extractor": key,
                "reason": "not_in_catalog",
            },
        )
    if key not in settings_allowed:
        raise UrlImportError(
            "unsupported_host",
            meta={
                "host": host,
                "platform": catalog["label"],
                "extractor": key,
                "reason": "disabled_by_admin",
            },
        )
    return key, catalog["label"], host


def probe_url(
    url: str,
    *,
    settings_allowed: list[str],
    proxy: str | None,
    cookies_path: str | None = None,
    max_audio_bitrate_kbps: int = 0,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    cleaned = validate_import_url(url)
    host = host_from_url(cleaned)
    if on_progress:
        on_progress("probing", {"host": host})

    info = _run_ytdl(
        cleaned,
        host=host,
        proxy=proxy,
        cookies_path=cookies_path,
        max_audio_bitrate_kbps=max_audio_bitrate_kbps,
        download=False,
    )

    extractor_key, platform_label, host = _check_extractor(
        info.get("extractor_key") or info.get("extractor"),
        settings_allowed=settings_allowed,
        host=host,
    )
    title = info.get("title")
    duration = info.get("duration")
    duration_sec = float(duration) if duration is not None else None
    return {
        "extractor_key": extractor_key,
        "platform_label": platform_label,
        "host": host,
        "title": title if isinstance(title, str) else None,
        "duration_sec": duration_sec,
    }


def download_audio(
    url: str,
    *,
    settings_allowed: list[str],
    proxy: str | None,
    cookies_path: str | None = None,
    max_audio_bitrate_kbps: int = 0,
    max_bytes: int,
    on_progress: ProgressCallback | None = None,
    is_canceled: Callable[[], bool] | None = None,
) -> ImportResult:
    cleaned = validate_import_url(url)
    meta = probe_url(
        cleaned,
        settings_allowed=settings_allowed,
        proxy=proxy,
        cookies_path=cookies_path,
        max_audio_bitrate_kbps=max_audio_bitrate_kbps,
        on_progress=on_progress,
    )
    if is_canceled and is_canceled():
        raise UrlImportError("canceled")

    if on_progress:
        on_progress(
            "downloading",
            {
                "host": meta["host"],
                "platform": meta["platform_label"],
                "title": meta.get("title"),
                "duration_sec": meta.get("duration_sec"),
            },
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="hub-import-"))
    outtmpl = str(tmpdir / "%(id)s.%(ext)s")

    _run_ytdl(
        cleaned,
        host=meta["host"],
        proxy=proxy,
        cookies_path=cookies_path,
        max_audio_bitrate_kbps=max_audio_bitrate_kbps,
        download=True,
        outtmpl=outtmpl,
    )

    if is_canceled and is_canceled():
        raise UrlImportError("canceled")

    files = sorted(tmpdir.glob("*.mp3"))
    if not files:
        files = sorted(p for p in tmpdir.iterdir() if p.is_file())
    if not files:
        raise UrlImportError("download_failed", meta={"host": meta["host"]})

    source = files[0]
    size = source.stat().st_size
    if size > max_bytes:
        source.unlink(missing_ok=True)
        tmpdir.rmdir()
        raise UrlImportError("payload_too_large", meta={"host": meta["host"], "bytes": size})

    title = meta.get("title")
    stem = safe_filename(title if isinstance(title, str) and title.strip() else source.stem)
    filename = f"{stem}.mp3"

    if on_progress:
        on_progress(
            "converting",
            {
                "host": meta["host"],
                "platform": meta["platform_label"],
                "title": title,
            },
        )

    return ImportResult(
        source_path=source,
        suffix=".mp3",
        original_filename=filename,
        title=title if isinstance(title, str) else None,
        duration_sec=meta.get("duration_sec"),
        extractor_key=meta["extractor_key"],
        host=meta["host"],
        platform_label=meta["platform_label"],
    )


def cleanup_import_path(path: Path) -> None:
    if path.is_file():
        path.unlink(missing_ok=True)
    parent = path.parent
    if parent.name.startswith("hub-import-") and parent.is_dir():
        try:
            next(parent.iterdir())
        except StopIteration:
            parent.rmdir()

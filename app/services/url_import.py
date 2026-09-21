"""Download audio from supported URLs via yt-dlp."""

from __future__ import annotations

import concurrent.futures
import contextlib
import ipaddress
import logging
import re
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

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
_DNS_RESOLUTION_TIMEOUT_SEC = 5.0

# YouTube player clients to try when android returns HTTP 403.
_YOUTUBE_CLIENT_FALLBACKS: tuple[list[str], ...] = (
    ["android"],
    ["default", "web_embedded"],
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


_IMPORT_AUDIO_SUFFIXES = frozenset({".mp3", ".m4a", ".opus", ".ogg", ".wav", ".webm", ".mp4", ".mkv", ".aac"})


def _effective_import_bitrate_kbps(max_audio_bitrate_kbps: int) -> int:
    if max_audio_bitrate_kbps > 0:
        return max_audio_bitrate_kbps
    return DEFAULT_IMPORT_AUDIO_BITRATE_KBPS


def _estimated_import_audio_bytes(duration_sec: float, max_audio_bitrate_kbps: int) -> int:
    kbps = _effective_import_bitrate_kbps(max_audio_bitrate_kbps)
    # VBR MP3 can exceed nominal bitrate briefly; small fixed overhead for tags.
    return int(duration_sec * kbps * 1000 / 8 * 1.1) + 4096


def _positive_duration(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _duration_sec_from_info(info: dict[str, Any]) -> float | None:
    """Duration from yt-dlp info (Rutube HLS often omits per-format duration)."""
    direct = _positive_duration(info.get("duration"))
    if direct is not None:
        return direct
    best: float | None = None
    for fmt in info.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        parsed = _positive_duration(fmt.get("duration"))
        if parsed is not None:
            best = parsed if best is None else max(best, parsed)
    return best


def _estimated_source_bytes_from_info(info: dict[str, Any], max_audio_bitrate_kbps: int) -> int | None:
    """Upper-bound hint when duration is missing (e.g. progressive URL with filesize)."""
    best = 0
    for fmt in info.get("formats") or []:
        if not isinstance(fmt, dict):
            continue
        raw = fmt.get("filesize") or fmt.get("filesize_approx")
        if isinstance(raw, (int, float)) and raw > best:
            best = int(raw)
    if best > 0:
        return best
    duration = _duration_sec_from_info(info)
    if duration is not None:
        return _estimated_import_audio_bytes(duration, max_audio_bitrate_kbps)
    return None


def _import_progress_hook(
    *,
    host: str,
    max_bytes: int,
    is_canceled: Callable[[], bool] | None,
) -> ProgressCallback:
    """Abort yt-dlp on user cancel or when downloaded bytes exceed tariff cap."""

    def hook(progress: dict[str, Any]) -> None:
        if is_canceled and is_canceled():
            raise UrlImportError("canceled")
        if max_bytes <= 0:
            return
        status = progress.get("status")
        if status not in {"downloading", "finished"}:
            return
        raw = progress.get("downloaded_bytes")
        if not isinstance(raw, (int, float)):
            return
        downloaded = int(raw)
        if downloaded > max_bytes:
            raise UrlImportError(
                "payload_too_large",
                meta={"host": host, "bytes": downloaded, "reason": "download_byte_cap"},
            )

    return hook


def _is_filesize_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "max-filesize" in msg
        or "max filesize" in msg
        or ("filesize" in msg and ("larger" in msg or "exceed" in msg or "too big" in msg))
    )


def _min_expected_import_bytes(duration_sec: float, max_audio_bitrate_kbps: int) -> int:
    """Detect truncated HLS/mp3 when yt-dlp stops early without raising."""
    kbps = _effective_import_bitrate_kbps(max_audio_bitrate_kbps)
    floor_kbps = max(16, min(32, kbps // 2))
    return int(duration_sec * floor_kbps * 1000 / 8)


def _reject_incomplete_import_artifact(
    *,
    size: int,
    duration_sec: float | None,
    max_audio_bitrate_kbps: int,
    host: str,
    max_bytes: int,
) -> None:
    if max_bytes <= 0 or duration_sec is None or duration_sec < 60:
        return
    minimum = _min_expected_import_bytes(duration_sec, max_audio_bitrate_kbps)
    if size < minimum and size <= max_bytes:
        raise UrlImportError(
            "download_failed",
            meta={
                "host": host,
                "bytes": size,
                "duration_sec": duration_sec,
                "reason": "incomplete_download",
            },
        )


def _reject_import_over_size_limit(
    *,
    max_bytes: int,
    duration_sec: float | None,
    max_audio_bitrate_kbps: int,
    host: str,
    estimated_source_bytes: int | None = None,
) -> None:
    if max_bytes <= 0:
        return
    if duration_sec is not None and duration_sec > 0:
        estimated = _estimated_import_audio_bytes(duration_sec, max_audio_bitrate_kbps)
        if estimated > max_bytes:
            raise UrlImportError(
                "payload_too_large",
                meta={"host": host, "bytes": estimated, "duration_sec": duration_sec},
            )
        return
    if estimated_source_bytes is not None and estimated_source_bytes > max_bytes:
        raise UrlImportError(
            "payload_too_large",
            meta={"host": host, "bytes": estimated_source_bytes, "reason": "source_filesize"},
        )


def _pick_import_source(tmpdir: Path) -> Path:
    files = [p for p in tmpdir.iterdir() if p.is_file()]
    if not files:
        raise UrlImportError("download_failed")
    audio = [p for p in files if p.suffix.lower() in _IMPORT_AUDIO_SUFFIXES]
    if audio:
        mp3 = [p for p in audio if p.suffix.lower() == ".mp3"]
        pool = mp3 or audio
        return max(pool, key=lambda p: p.stat().st_size)
    return max(files, key=lambda p: p.stat().st_size)


def _ydl_opts(
    proxy: str | None,
    *,
    cookies_path: str | None = None,
    max_audio_bitrate_kbps: int = 0,
    max_bytes: int = 0,
    host: str = "",
    is_canceled: Callable[[], bool] | None = None,
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
    if download:
        if max_bytes > 0:
            opts["max_filesize"] = max_bytes
        if host and (max_bytes > 0 or is_canceled):
            opts["progress_hooks"] = [
                _import_progress_hook(host=host, max_bytes=max_bytes, is_canceled=is_canceled)
            ]
    return opts


def _extract_info_with_cancel(
    ydl: Any,
    url: str,
    *,
    download: bool,
    is_canceled: Callable[[], bool] | None,
) -> Any:
    if not is_canceled:
        return ydl.extract_info(url, download=download)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ydl.extract_info, url, download)
        while True:
            try:
                return future.result(timeout=0.25)
            except concurrent.futures.TimeoutError:
                if is_canceled():
                    with contextlib.suppress(Exception):
                        ydl.close()
                    raise UrlImportError("canceled")


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
    max_bytes: int = 0,
    download: bool,
    outtmpl: str | None = None,
    is_canceled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled, DownloadError, ExtractorError

    attempts = _youtube_client_attempts(host)
    last_exc: BaseException | None = None
    cleared_cache = False
    clients_tried: list[list[str] | None] = []

    for index, clients in enumerate(attempts):
        if is_canceled and is_canceled():
            raise UrlImportError("canceled")
        clients_tried.append(clients)
        if index > 0 and not cleared_cache:
            _clear_ytdl_cache()
            cleared_cache = True
        opts = _ydl_opts(
            proxy,
            cookies_path=cookies_path,
            max_audio_bitrate_kbps=max_audio_bitrate_kbps,
            max_bytes=max_bytes,
            host=host,
            is_canceled=is_canceled,
            youtube_clients=clients,
            outtmpl=outtmpl,
            download=download,
        )
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = _extract_info_with_cancel(
                    ydl,
                    url,
                    download=download,
                    is_canceled=is_canceled,
                )
            if not isinstance(info, dict):
                raise UrlImportError("download_failed", meta={"host": host})
            return info
        except UrlImportError:
            raise
        except DownloadCancelled as exc:
            raise UrlImportError("canceled") from exc
        except (ExtractorError, DownloadError) as exc:
            last_exc = exc
            if _is_filesize_limit_error(exc):
                raise UrlImportError(
                    "payload_too_large",
                    meta={"host": host, "reason": "max_filesize", "error_detail": _error_detail(exc)},
                ) from exc
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
            if isinstance(exc, DownloadCancelled):
                raise UrlImportError("canceled") from exc
            if _is_filesize_limit_error(exc):
                raise UrlImportError(
                    "payload_too_large",
                    meta={"host": host, "reason": "max_filesize", "error_detail": _error_detail(exc)},
                ) from exc
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


def _normalize_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is not None:
            return mapped
    return ip


def _is_blocked_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    ip = _normalize_ip(ip)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _port_from_url(url: str) -> int:
    parsed = urlparse(url.strip())
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme.lower() == "https":
        return 443
    return 80


def _reject_literal_blocked_host(host: str) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if _is_blocked_address(ip):
        raise UrlImportError(
            "unsupported_host",
            meta={"host": host, "reason": "blocked_address"},
        )


def _resolve_addrinfo(host: str, port: int) -> list[tuple]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        try:
            return future.result(timeout=_DNS_RESOLUTION_TIMEOUT_SEC)
        except concurrent.futures.TimeoutError as exc:
            raise UrlImportError(
                "unsupported_host",
                meta={
                    "host": host,
                    "reason": "dns_resolution_failed",
                    "error_detail": f"DNS lookup timed out after {_DNS_RESOLUTION_TIMEOUT_SEC}s",
                },
            ) from exc


def _reject_blocked_resolved_ips(host: str, *, port: int) -> None:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return

    try:
        infos = _resolve_addrinfo(host, port)
    except socket.gaierror as exc:
        raise UrlImportError(
            "unsupported_host",
            meta={
                "host": host,
                "reason": "dns_resolution_failed",
                "error_detail": _error_detail(exc),
            },
        ) from exc

    if not infos:
        raise UrlImportError(
            "unsupported_host",
            meta={"host": host, "reason": "dns_resolution_failed"},
        )

    seen: set[str] = set()
    for _, _, _, _, sockaddr in infos:
        addr = sockaddr[0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_address(ip):
            raise UrlImportError(
                "unsupported_host",
                meta={
                    "host": host,
                    "reason": "blocked_address",
                    "resolved_ip": str(_normalize_ip(ip)),
                },
            )


def reject_literal_blocked_import_url(url: str) -> str:
    """Reject literal private/link-local IPs before capture URL heuristics."""
    cleaned = validate_import_url(url)
    host = host_from_url(cleaned)
    if host:
        _reject_literal_blocked_host(host)
    return cleaned


def reject_blocked_import_url(url: str) -> str:
    """Block SSRF targets for catalog URL import (DNS + literal IPs)."""
    cleaned = validate_import_url(url)
    host = host_from_url(cleaned)
    if host:
        _reject_literal_blocked_host(host)
        _reject_blocked_resolved_ips(host, port=_port_from_url(cleaned))
    return cleaned


def assert_import_fetch_allowed(url: str, *, settings_allowed: list[str]) -> str:
    """Reject internal/metadata URLs and non-catalog hosts before yt-dlp runs."""
    cleaned = validate_import_url(url)
    host = host_from_url(cleaned)

    _reject_literal_blocked_host(host)

    platform = catalog_platform_for_host(host)
    if platform is None:
        raise UrlImportError(
            "unsupported_host",
            meta={"host": host, "reason": "not_in_catalog"},
        )

    extractor_id = platform["id"]
    if extractor_id not in settings_allowed:
        raise UrlImportError(
            "unsupported_host",
            meta={
                "host": host,
                "platform": platform["label"],
                "extractor": extractor_id,
                "reason": "disabled_by_admin",
            },
        )

    _reject_blocked_resolved_ips(host, port=_port_from_url(cleaned))

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
    is_canceled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    cleaned = assert_import_fetch_allowed(url, settings_allowed=settings_allowed)
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
        is_canceled=is_canceled,
    )

    extractor_key, platform_label, host = _check_extractor(
        info.get("extractor_key") or info.get("extractor"),
        settings_allowed=settings_allowed,
        host=host,
    )
    title = info.get("title")
    duration_sec = _duration_sec_from_info(info)
    estimated_source_bytes = _estimated_source_bytes_from_info(info, max_audio_bitrate_kbps)
    return {
        "extractor_key": extractor_key,
        "platform_label": platform_label,
        "host": host,
        "title": title if isinstance(title, str) else None,
        "duration_sec": duration_sec,
        "estimated_source_bytes": estimated_source_bytes,
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
        is_canceled=is_canceled,
    )
    if is_canceled and is_canceled():
        raise UrlImportError("canceled")

    _reject_import_over_size_limit(
        max_bytes=max_bytes,
        duration_sec=meta.get("duration_sec"),
        max_audio_bitrate_kbps=max_audio_bitrate_kbps,
        host=meta["host"],
        estimated_source_bytes=meta.get("estimated_source_bytes"),
    )

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
        max_bytes=max_bytes,
        download=True,
        outtmpl=outtmpl,
        is_canceled=is_canceled,
    )

    if is_canceled and is_canceled():
        raise UrlImportError("canceled")

    try:
        source = _pick_import_source(tmpdir)
    except UrlImportError as exc:
        raise UrlImportError("download_failed", meta={"host": meta["host"]}) from exc

    size = source.stat().st_size
    if size > max_bytes:
        cleanup_import_path(source)
        raise UrlImportError("payload_too_large", meta={"host": meta["host"], "bytes": size})

    _reject_incomplete_import_artifact(
        size=size,
        duration_sec=meta.get("duration_sec"),
        max_audio_bitrate_kbps=max_audio_bitrate_kbps,
        host=meta["host"],
        max_bytes=max_bytes,
    )

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

"""Catalog of URL-import platforms (yt-dlp extractors) and instance whitelist helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import InstanceSettings

DEFAULT_IMPORT_AUDIO_BITRATE_KBPS = 64
IMPORT_AUDIO_BITRATE_MIN_KBPS = 48
IMPORT_AUDIO_BITRATE_MAX_KBPS = 320


def normalize_import_audio_bitrate_kbps(value: int | None) -> int:
    """0 = no cap (best available). Otherwise clamp to supported MP3 range."""
    if value is None or value <= 0:
        return 0
    return max(IMPORT_AUDIO_BITRATE_MIN_KBPS, min(IMPORT_AUDIO_BITRATE_MAX_KBPS, int(value)))


IMPORT_PLATFORM_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "Youtube",
        "label": "YouTube",
        "domains": ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com"),
        "default_enabled": True,
    },
    {
        "id": "Rutube",
        "label": "Rutube",
        "domains": ("rutube.ru",),
        "default_enabled": True,
    },
    {
        "id": "TikTok",
        "label": "TikTok",
        "domains": ("tiktok.com",),
        "default_enabled": True,
    },
)

_CATALOG_BY_ID = {item["id"]: item for item in IMPORT_PLATFORM_CATALOG}


def catalog_entry(extractor_id: str) -> dict[str, Any] | None:
    return _CATALOG_BY_ID.get(extractor_id)


def default_allowed_extractors() -> list[str]:
    return [item["id"] for item in IMPORT_PLATFORM_CATALOG if item.get("default_enabled")]


def normalize_allowed_extractors(raw: list[str] | None) -> list[str]:
    if not raw:
        return default_allowed_extractors()
    out: list[str] = []
    for item in raw:
        key = str(item).strip()
        if key and key in _CATALOG_BY_ID and key not in out:
            out.append(key)
    return out or default_allowed_extractors()


def allowed_extractors(settings: InstanceSettings) -> list[str]:
    raw = settings.import_allowed_extractors_json
    if raw is None:
        return default_allowed_extractors()
    if isinstance(raw, list):
        return normalize_allowed_extractors([str(x) for x in raw])
    return default_allowed_extractors()


def validate_allowed_extractors(ids: list[str]) -> list[str]:
    out: list[str] = []
    for item in ids:
        key = str(item).strip()
        if not key:
            continue
        if key not in _CATALOG_BY_ID:
            raise ValueError(f"unknown import extractor: {key}")
        if key not in out:
            out.append(key)
    if not out:
        raise ValueError("at least one import platform is required")
    return out


def platform_public(entry: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "label": entry["label"],
        "domains": list(entry["domains"]),
        "enabled": enabled,
    }


def admin_platforms(settings: InstanceSettings) -> list[dict[str, Any]]:
    allowed = set(allowed_extractors(settings))
    return [platform_public(entry, enabled=entry["id"] in allowed) for entry in IMPORT_PLATFORM_CATALOG]


def public_platforms(settings: InstanceSettings) -> list[dict[str, Any]]:
    allowed = allowed_extractors(settings)
    out: list[dict[str, Any]] = []
    for extractor_id in allowed:
        entry = catalog_entry(extractor_id)
        if entry is None:
            continue
        out.append({"label": entry["label"], "domains": list(entry["domains"])})
    return out


def host_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def catalog_platform_for_host(host: str) -> dict[str, Any] | None:
    if not host:
        return None
    for entry in IMPORT_PLATFORM_CATALOG:
        domains = entry.get("domains") or ()
        if host in domains or any(host.endswith(f".{domain}") for domain in domains):
            return entry
    return None


def _normalize_hostport(hostport: str) -> str:
    hostport = hostport.strip()
    if not hostport:
        return hostport
    if hostport.startswith("["):
        closing = hostport.find("]")
        if closing != -1 and ":" in hostport[closing:]:
            host, _, port = hostport.rpartition(":")
            port = port.strip()
            if port:
                int(port)
            return f"{host}:{port}" if port else host
        return hostport
    if ":" not in hostport:
        return hostport
    host, _, port = hostport.rpartition(":")
    host = host.strip()
    port = port.strip()
    if port:
        int(port)
    return f"{host}:{port}" if port else host


_PROXY_SCHEMES = frozenset({"socks5", "socks5h", "socks4", "http", "https"})


def normalize_download_proxy_url(url: str) -> str:
    """Normalize yt-dlp proxy URL (socks5/socks4/http/https). Fixes common typos (e.g. space before port)."""
    from urllib.parse import urlparse, urlunparse

    cleaned = url.strip()
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    if parsed.scheme not in _PROXY_SCHEMES:
        cleaned = f"socks5://{cleaned.lstrip('/')}"
        parsed = urlparse(cleaned)
    netloc = parsed.netloc.strip()
    if not netloc:
        raise ValueError("invalid proxy url")
    if "@" in netloc:
        userinfo, hostport = netloc.rsplit("@", 1)
        netloc = f"{userinfo.strip()}@{_normalize_hostport(hostport)}"
    else:
        netloc = _normalize_hostport(netloc)
    return urlunparse(parsed._replace(netloc=netloc))


def effective_download_proxy(settings: InstanceSettings, db: Session) -> str | None:
    if not settings.download_proxy_enabled:
        return None
    url = (settings.download_proxy_url or "").strip()
    if not url:
        return None
    try:
        url = normalize_download_proxy_url(url)
    except ValueError:
        return None
    if settings.download_proxy_password_encrypted and "@" in url:
        from app.crypto import decrypt_str
        from urllib.parse import quote, urlparse, urlunparse

        password = decrypt_str(settings.download_proxy_password_encrypted, db)
        if password:
            parsed = urlparse(url)
            netloc = parsed.netloc
            if "@" in netloc:
                userinfo, hostport = netloc.rsplit("@", 1)
                if ":" not in userinfo:
                    userinfo = f"{quote(userinfo, safe='')}:{quote(password, safe='')}"
                    netloc = f"{userinfo}@{hostport}"
                    url = urlunparse(parsed._replace(netloc=netloc))
    return url

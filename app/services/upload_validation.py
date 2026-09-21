"""Audio upload content sniffing (magic bytes)."""

from __future__ import annotations

from pathlib import Path

_HEADER_LEN = 12
_ALLOWED_SUFFIXES = (".mp3", ".m4a", ".wav")


class InvalidAudioContent(Exception):
    """File header does not match the declared audio suffix."""


def validate_audio_header(suffix: str, header: bytes) -> None:
    normalized = suffix.lower()
    if normalized == ".wav":
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise InvalidAudioContent()
        return
    if normalized == ".mp3":
        if header[:3] == b"ID3":
            return
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return
        raise InvalidAudioContent()
    if normalized == ".m4a":
        if len(header) < 8 or header[4:8] != b"ftyp":
            raise InvalidAudioContent()
        return
    raise InvalidAudioContent()


def validate_audio_file(suffix: str, data: bytes) -> None:
    validate_audio_header(suffix, data[:_HEADER_LEN])


def sniff_audio_suffix(header: bytes) -> str | None:
    for candidate in _ALLOWED_SUFFIXES:
        try:
            validate_audio_header(candidate, header)
        except InvalidAudioContent:
            continue
        return candidate
    return None


def _suffix_from_content_type(content_type: str) -> str | None:
    ct = content_type.split(";", 1)[0].strip().lower()
    mapping = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/wav": ".wav",
        "audio/wave": ".wav",
        "audio/x-wav": ".wav",
    }
    return mapping.get(ct)


def resolve_capture_artifact(
    content: bytes,
    headers: dict[str, str],
    *,
    filename_from_disposition: str,
    default_suffix: str = ".mp3",
) -> tuple[str, str]:
    """Pick storage suffix and filename for a capture worker download."""
    header = content[:_HEADER_LEN]
    sniffed = sniff_audio_suffix(header)

    filename = filename_from_disposition.strip() or f"capture{default_suffix}"
    ext = Path(filename).suffix.lower()
    from_name = ext if ext in _ALLOWED_SUFFIXES else None

    content_type = headers.get("content-type") or ""
    from_type = _suffix_from_content_type(content_type)

    suffix = sniffed or from_name or from_type or default_suffix
    stem = Path(filename).stem or "capture"
    if not filename.lower().endswith(suffix):
        filename = f"{stem}{suffix}"
    return suffix, filename


MIN_CAPTURE_ARTIFACT_BYTES = 512


def validate_capture_artifact_against_poll(content: bytes, poll: dict) -> None:
    """Ensure downloaded bytes match worker-reported artifact metadata."""
    artifact = poll.get("artifact")
    if not isinstance(artifact, dict):
        return
    expected_size = artifact.get("size_bytes")
    if isinstance(expected_size, int) and expected_size > 0 and len(content) != expected_size:
        raise InvalidAudioContent()
    meta = poll.get("meta") if isinstance(poll.get("meta"), dict) else {}
    duration = meta.get("duration_sec")
    if isinstance(duration, (int, float)) and duration >= 1.0 and len(content) < MIN_CAPTURE_ARTIFACT_BYTES:
        raise InvalidAudioContent()


def validate_capture_download(content: bytes, headers: dict[str, str]) -> None:
    """Reject API error bodies and implausibly small capture artifacts."""
    if not content:
        raise InvalidAudioContent()
    if content.lstrip()[:1] == b"{":
        raise InvalidAudioContent()
    content_type = (headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type in {"application/json", "text/plain", "text/html"}:
        raise InvalidAudioContent()
    if len(content) < MIN_CAPTURE_ARTIFACT_BYTES:
        raise InvalidAudioContent()
    sniffed = sniff_audio_suffix(content[:_HEADER_LEN])
    if sniffed is None:
        raise InvalidAudioContent()
    validate_audio_header(sniffed, content[:_HEADER_LEN])

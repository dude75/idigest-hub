"""Helpers for file download / export responses."""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi.responses import Response

_SAFE_CHARS = re.compile(r"[^\w\s.-]", re.UNICODE)
_MARKDOWN_FENCE = re.compile(r"^```(?:markdown|md)?\r?\n([\s\S]*?)\r?\n```$", re.UNICODE)


def unwrap_markdown_fence(text: str) -> str:
    trimmed = text.strip()
    match = _MARKDOWN_FENCE.match(trimmed)
    return match.group(1) if match else text


def safe_filename(name: str, fallback: str = "download") -> str:
    base = _SAFE_CHARS.sub("", name).strip() or fallback
    return base[:200]


def content_disposition_attachment(filename: str, *, disposition: str = "attachment") -> str:
    """Build a Content-Disposition header safe for non-ASCII filenames (RFC 5987)."""
    name = safe_filename(filename)
    quoted = quote(name)
    if quoted != name:
        return f"{disposition}; filename*=utf-8''{quoted}"
    return f'{disposition}; filename="{name}"'


def attachment_response(content: str | bytes, filename: str, media_type: str) -> Response:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )

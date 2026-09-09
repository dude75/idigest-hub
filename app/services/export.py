"""Helpers for file download / export responses."""

from __future__ import annotations

import re

from fastapi.responses import Response

_SAFE_CHARS = re.compile(r"[^\w\s.-]", re.UNICODE)


def safe_filename(name: str, fallback: str = "download") -> str:
    base = _SAFE_CHARS.sub("", name).strip() or fallback
    return base[:200]


def attachment_response(content: str | bytes, filename: str, media_type: str) -> Response:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(filename)}"'},
    )

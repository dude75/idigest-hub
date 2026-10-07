from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import get_settings
from app.paths import HUB_VIDEO_UPLOAD_TMP_PREFIX, hub_tmp_root


@pytest.mark.asyncio
async def test_video_upload_to_mp3_temp_uses_hub_tmp(tmp_path, monkeypatch):
    from app.services import video_extract

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    source = tmp_path / "fake_source.bin"
    source.write_bytes(b"\x00" * 8)
    mp3 = tmp_path / "fake.mp3"
    mp3.write_bytes(b"ID3" + b"\x00" * 16)

    async def fake_stream(file, dest, *, max_bytes):
        dest.write_bytes(source.read_bytes())

    monkeypatch.setattr(video_extract, "stream_upload_to_file", fake_stream)
    monkeypatch.setattr(video_extract, "_extract_sync", lambda _src, dest: dest.write_bytes(mp3.read_bytes()))

    upload = MagicMock()
    upload.read = AsyncMock(return_value=b"")
    result = await video_extract.video_upload_to_mp3_temp(upload, suffix=".mp4", max_bytes=1024)

    assert result.is_relative_to(hub_tmp_root(get_settings()))
    assert result.parent.name.startswith(HUB_VIDEO_UPLOAD_TMP_PREFIX)
    video_extract.cleanup_extract_temp(result)
    assert not result.parent.exists()

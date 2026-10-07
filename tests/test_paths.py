from pathlib import Path

from app.config import Settings
from app.paths import (
    ensure_hub_tmp,
    hub_tmp_root,
    hub_ytdlp_cache_dir,
    import_tmpdir_for_path,
    is_hub_import_tmpdir,
    make_hub_import_tmpdir,
)


def test_hub_tmp_under_data_dir(tmp_path):
    settings = Settings(DATA_DIR=str(tmp_path))
    root = ensure_hub_tmp(settings)
    assert root == tmp_path / "tmp"
    assert root.is_dir()
    assert hub_tmp_root(settings) == root


def test_make_hub_import_tmpdir_lives_under_hub_tmp(tmp_path):
    settings = Settings(DATA_DIR=str(tmp_path))
    import_dir = make_hub_import_tmpdir(settings)
    assert is_hub_import_tmpdir(import_dir)
    assert import_dir.is_relative_to(hub_tmp_root(settings))


def test_import_tmpdir_for_path(tmp_path):
    settings = Settings(DATA_DIR=str(tmp_path))
    import_dir = make_hub_import_tmpdir(settings)
    artifact = import_dir / "clip.mp3"
    artifact.write_bytes(b"ID3")
    assert import_tmpdir_for_path(artifact) == import_dir.resolve()


def test_ytdlp_cache_dir(tmp_path):
    settings = Settings(DATA_DIR=str(tmp_path))
    cache = hub_ytdlp_cache_dir(settings)
    assert cache == tmp_path / "tmp" / "yt-dlp"

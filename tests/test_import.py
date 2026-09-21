"""URL import tasks and instance whitelist."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tests.conftest import (
    add_worker,
    create_tariff,
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    seed_node_health,
    setup_admin,
    signup,
    wait_task,
)


@pytest.fixture(autouse=True)
def _reset_import_runner():
    from app.services.import_runner import reset_import_runner

    reset_import_runner()
    yield
    reset_import_runner()


def test_import_platform_catalog():
    from app.services.import_platforms import IMPORT_PLATFORM_CATALOG, default_allowed_extractors

    ids = {item["id"] for item in IMPORT_PLATFORM_CATALOG}
    assert ids == {"Youtube", "Rutube", "TikTok"}
    assert default_allowed_extractors() == ["Youtube", "Rutube", "TikTok"]


def test_import_platforms(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "platforms@example.com", "platformspass1", tariff_id).status_code == 200
    login_ready(client, "platforms@example.com", "platformspass1")
    response = client.get("/api/v1/import/platforms")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    labels = {item["label"] for item in payload["platforms"]}
    assert labels == {"YouTube", "Rutube", "TikTok"}
    assert payload["download_proxy_required"] is False
    assert payload["download_proxy_available"] is True


def test_proxy_host_port():
    from app.services.download_proxy_health import proxy_host_port

    assert proxy_host_port("socks5://127.0.0.1:1080") == ("127.0.0.1", 1080)
    assert proxy_host_port("http://proxy.example:8080") == ("proxy.example", 8080)
    assert proxy_host_port("socks5://user@host:9999") == ("host", 9999)


def test_download_proxy_status_respects_enabled_flag():
    from unittest.mock import MagicMock

    from app.models import InstanceSettings
    from app.services.download_proxy_health import download_proxy_status, reset_download_proxy_health_cache

    reset_download_proxy_health_cache()
    db = MagicMock()
    settings = InstanceSettings(
        id=1,
        download_proxy_url="socks5://127.0.0.1:1080",
        download_proxy_enabled=False,
    )
    assert download_proxy_status(settings, db) == {
        "download_proxy_required": False,
        "download_proxy_available": True,
    }


def test_create_import_blocked_when_proxy_required_and_unavailable(client, monkeypatch):
    from app.services.download_proxy_health import reset_download_proxy_health_cache

    reset_download_proxy_health_cache()
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "download_proxy_url": "socks5://127.0.0.1:1",
            "download_proxy_enabled": True,
        },
    )
    tariff_id = default_tariff_id(client)
    assert signup(client, "proxydown@example.com", "proxydownpass1", tariff_id).status_code == 200
    login_ready(client, "proxydown@example.com", "proxydownpass1")

    monkeypatch.setattr(
        "app.services.download_proxy_health.check_download_proxy_available",
        lambda *_args, **_kwargs: False,
    )
    reset_download_proxy_health_cache()

    platforms = client.get("/api/v1/import/platforms")
    assert platforms.status_code == 200
    body = platforms.json()
    assert body["download_proxy_required"] is True
    assert body["download_proxy_available"] is False

    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 503
    assert err_code(response) == "proxy_unavailable"


def test_create_import_allowed_when_proxy_not_required(client, monkeypatch):
    from app.services.download_proxy_health import reset_download_proxy_health_cache

    reset_download_proxy_health_cache()
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={
            "download_proxy_url": "socks5://127.0.0.1:1",
            "download_proxy_enabled": False,
        },
    )
    tariff_id = default_tariff_id(client)
    assert signup(client, "noproxy@example.com", "noproxypass1", tariff_id).status_code == 200
    login_ready(client, "noproxy@example.com", "noproxypass1")

    monkeypatch.setattr(
        "app.services.download_proxy_health.check_download_proxy_available",
        lambda *_args, **_kwargs: False,
    )
    reset_download_proxy_health_cache()

    platforms = client.get("/api/v1/import/platforms")
    assert platforms.status_code == 200
    body = platforms.json()
    assert body["download_proxy_required"] is False
    assert body["download_proxy_available"] is True

    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 202
    assert response.json()["task_id"]


def test_import_disabled(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    patch = client.patch(
        "/api/v1/instance/settings",
        json={"import_enabled": False},
    )
    assert patch.status_code == 200
    logout(client)
    assert signup(client, "import@example.com", "importpass1", tariff_id).status_code == 200
    login_ready(client, "import@example.com", "importpass1")
    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 403
    assert err_code(response) == "import_disabled"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "https://evil.example.com/video/1",
    ],
)
def test_assert_import_fetch_allowed_blocks_unsafe(url):
    from app.services.url_import import UrlImportError, assert_import_fetch_allowed

    with pytest.raises(UrlImportError) as exc_info:
        assert_import_fetch_allowed(url, settings_allowed=["Youtube", "Rutube", "TikTok"])
    assert exc_info.value.code == "unsupported_host"


def test_assert_import_fetch_allowed_accepts_catalog_host():
    from app.services.url_import import assert_import_fetch_allowed

    cleaned = assert_import_fetch_allowed(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        settings_allowed=["Youtube"],
    )
    assert cleaned.startswith("https://")


def test_assert_import_fetch_allowed_blocks_dns_rebinding(monkeypatch):
    from app.services.url_import import UrlImportError, assert_import_fetch_allowed

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", port),
            )
        ]

    monkeypatch.setattr("app.services.url_import.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UrlImportError) as exc_info:
        assert_import_fetch_allowed(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            settings_allowed=["Youtube"],
        )
    assert exc_info.value.code == "unsupported_host"
    assert exc_info.value.meta["reason"] == "blocked_address"
    assert exc_info.value.meta["resolved_ip"] == "127.0.0.1"


def test_assert_import_fetch_allowed_blocks_private_resolved_ip(monkeypatch):
    from app.services.url_import import UrlImportError, assert_import_fetch_allowed

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.5", port),
            )
        ]

    monkeypatch.setattr("app.services.url_import.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UrlImportError) as exc_info:
        assert_import_fetch_allowed(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            settings_allowed=["Youtube"],
        )
    assert exc_info.value.meta["reason"] == "blocked_address"
    assert exc_info.value.meta["resolved_ip"] == "10.0.0.5"


def test_assert_import_fetch_allowed_blocks_dns_resolution_failure(monkeypatch):
    from app.services.url_import import UrlImportError, assert_import_fetch_allowed

    def fake_getaddrinfo(host, port, *args, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr("app.services.url_import.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UrlImportError) as exc_info:
        assert_import_fetch_allowed(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            settings_allowed=["Youtube"],
        )
    assert exc_info.value.meta["reason"] == "dns_resolution_failed"


def test_assert_import_fetch_allowed_respects_admin_whitelist():
    from app.services.url_import import UrlImportError, assert_import_fetch_allowed

    with pytest.raises(UrlImportError) as exc_info:
        assert_import_fetch_allowed(
            "https://www.tiktok.com/@user/video/1",
            settings_allowed=["Youtube"],
        )
    assert exc_info.value.code == "unsupported_host"
    assert exc_info.value.meta["reason"] == "disabled_by_admin"


def test_import_rejects_blocked_url_at_api(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "ssrf@example.com", "ssrfpass1234", tariff_id).status_code == 200
    login_ready(client, "ssrf@example.com", "ssrfpass1234")
    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert response.status_code == 400
    assert err_code(response) == "unsupported_host"


def test_import_invalid_url(client):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "badurl@example.com", "badurlpass1", tariff_id).status_code == 200
    login_ready(client, "badurl@example.com", "badurlpass1")
    response = client.post("/api/v1/tasks/import", json={"url": "not-a-url"})
    assert response.status_code == 400
    assert err_code(response) == "invalid_url"


def test_import_audio_bitrate_settings():
    from app.services.import_platforms import normalize_import_audio_bitrate_kbps
    from app.services.url_import import _audio_format_selector

    assert normalize_import_audio_bitrate_kbps(128) == 128
    assert normalize_import_audio_bitrate_kbps(0) == 0
    assert normalize_import_audio_bitrate_kbps(999) == 320
    assert _audio_format_selector(128) == "bestaudio[abr<=128]/bestaudio/best"
    assert _audio_format_selector(0) == "bestaudio/best"


def test_import_max_concurrent_settings():
    from app.services.import_platforms import normalize_import_max_concurrent

    assert normalize_import_max_concurrent(2) == 2
    assert normalize_import_max_concurrent(None) == 2
    assert normalize_import_max_concurrent(0) == 1
    assert normalize_import_max_concurrent(99) == 16


def test_instance_settings_import_max_concurrent(client):
    setup_admin(client)
    response = client.get("/api/v1/instance/settings")
    assert response.status_code == 200
    assert response.json()["import_max_concurrent"] == 2
    patch = client.patch("/api/v1/instance/settings", json={"import_max_concurrent": 4})
    assert patch.status_code == 200, patch.text
    assert patch.json()["import_max_concurrent"] == 4


def test_raise_ydl_error_maps_403():
    from app.services.url_import import UrlImportError, _raise_ydl_error

    try:
        _raise_ydl_error(
            Exception("HTTP Error 403: Forbidden"),
            host="youtube.com",
            proxy=None,
            youtube_client=["android"],
            youtube_clients_tried=[["default", "web_embedded"], ["android"]],
        )
    except UrlImportError as exc:
        assert exc.code == "video_unavailable"
        assert exc.meta["reason"] == "blocked_403"
        assert exc.meta["error_detail"] == "HTTP Error 403: Forbidden"
        assert exc.meta["youtube_client"] == ["android"]
        assert exc.meta["youtube_clients_tried"] == [["default", "web_embedded"], ["android"]]
    else:
        raise AssertionError("expected UrlImportError")


def test_import_task_saves_error_detail(client, monkeypatch):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "failimport@example.com", "failimportpass1", tariff_id).status_code == 200
    login_ready(client, "failimport@example.com", "failimportpass1")

    from app.services.url_import import UrlImportError

    def fake_download(url, **kwargs):
        raise UrlImportError(
            "video_unavailable",
            meta={
                "host": "youtube.com",
                "reason": "blocked_403",
                "error_detail": "HTTP Error 403: Forbidden",
                "youtube_clients_tried": [["default", "web_embedded"], ["android"], ["ios"]],
            },
        )

    monkeypatch.setattr("app.services.import_runner.download_audio", fake_download)

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert created.status_code == 202
    task_id = created.json()["task_id"]

    import time

    body = None
    for _ in range(100):
        polled = client.get(f"/api/v1/tasks/{task_id}")
        assert polled.status_code == 200
        body = polled.json()
        if body["status"] in {"success", "error"}:
            break
        time.sleep(0.05)

    assert body is not None
    assert body["status"] == "error"
    assert body["error"]["code"] == "video_unavailable"
    assert body["meta"]["reason"] == "blocked_403"
    assert body["meta"]["error_detail"] == "HTTP Error 403: Forbidden"
    assert body["meta"]["youtube_clients_tried"] == [["default", "web_embedded"], ["android"], ["ios"]]
    assert body["meta"]["stage"] == "error"


def test_effective_download_proxy_respects_enabled_flag():
    from unittest.mock import MagicMock

    from app.models import InstanceSettings
    from app.services.import_platforms import effective_download_proxy

    db = MagicMock()
    settings = InstanceSettings(
        id=1,
        download_proxy_url="socks5://127.0.0.1:1080",
        download_proxy_enabled=False,
    )
    assert effective_download_proxy(settings, db) is None
    settings.download_proxy_enabled = True
    assert effective_download_proxy(settings, db) == "socks5://127.0.0.1:1080"


def test_normalize_download_proxy_url():
    from app.services.import_platforms import normalize_download_proxy_url

    assert normalize_download_proxy_url("socks5://127.0.0.1: 12334") == "socks5://127.0.0.1:12334"
    assert normalize_download_proxy_url("  socks5://user@host:1080  ") == "socks5://user@host:1080"
    assert normalize_download_proxy_url("host:1080") == "socks5://host:1080"
    assert normalize_download_proxy_url("http://proxy.example:8080") == "http://proxy.example:8080"
    assert normalize_download_proxy_url("https://user@proxy.example:8443") == "https://user@proxy.example:8443"


def test_instance_settings_import_whitelist(client):
    setup_admin(client)
    response = client.get("/api/v1/instance/settings")
    assert response.status_code == 200
    platforms = response.json()["import_platforms"]
    assert any(item["id"] == "Youtube" and item["enabled"] for item in platforms)
    patch = client.patch(
        "/api/v1/instance/settings",
        json={
            "import_allowed_extractors": ["Youtube", "Rutube"],
            "download_proxy_url": "socks5://127.0.0.1:1080",
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    enabled = {item["id"] for item in body["import_platforms"] if item["enabled"]}
    assert enabled == {"Youtube", "Rutube"}
    assert body["download_proxy_configured"] is True
    assert body["download_proxy_url"] == "socks5://127.0.0.1:1080"
    assert body["download_proxy_enabled"] is False
    enabled = client.patch(
        "/api/v1/instance/settings",
        json={"download_proxy_enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["download_proxy_enabled"] is True
    cleared = client.patch(
        "/api/v1/instance/settings",
        json={"download_proxy_url": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["download_proxy_enabled"] is False
    blocked = client.patch(
        "/api/v1/instance/settings",
        json={"download_proxy_enabled": True},
    )
    assert blocked.status_code == 400
    assert err_code(blocked) == "validation_error"
    spaced = client.patch(
        "/api/v1/instance/settings",
        json={"download_proxy_url": "socks5://127.0.0.1: 12345"},
    )
    assert spaced.status_code == 200, spaced.text
    assert spaced.json()["download_proxy_url"] == "socks5://127.0.0.1:12345"
    bad = client.patch(
        "/api/v1/instance/settings",
        json={"import_allowed_extractors": ["NotAPlatform"]},
    )
    assert bad.status_code == 400
    assert err_code(bad) == "validation_error"


def test_import_task_success(client, tmp_path, monkeypatch):
    setup_admin(client)
    tariff_id = default_tariff_id(client)
    assert signup(client, "okimport@example.com", "okimportpass1", tariff_id).status_code == 200
    login_ready(client, "okimport@example.com", "okimportpass1")

    source = tmp_path / "clip.mp3"
    source.write_bytes(b"ID3" + b"\x00" * 128)

    from app.services.url_import import ImportResult

    def fake_download(url, **kwargs):
        return ImportResult(
            source_path=source,
            suffix=".mp3",
            original_filename="Sample Video.mp3",
            title="Sample Video",
            duration_sec=42.0,
            extractor_key="Youtube",
            host="youtube.com",
            platform_label="YouTube",
        )

    monkeypatch.setattr("app.services.import_runner.download_audio", fake_download)

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert created.status_code == 202, created.text
    task_id = created.json()["task_id"]

    import time

    body = None
    for _ in range(100):
        polled = client.get(f"/api/v1/tasks/{task_id}")
        assert polled.status_code == 200, polled.text
        body = polled.json()
        if body["status"] in {"success", "error"}:
            break
        time.sleep(0.05)

    assert body is not None
    assert body["status"] == "success", body
    assert body["audio_id"]
    audio = client.get(f"/api/v1/audios/{body['audio_id']}")
    assert audio.status_code == 200
    assert audio.json()["filename"] == "Sample Video.mp3"
    assert audio.json()["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    listed = client.get("/api/v1/audios")
    assert listed.status_code == 200
    match = next(item for item in listed.json()["items"] if item["id"] == body["audio_id"])
    assert match["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_import_with_transcribe_chains_follow_up(client, tmp_path, monkeypatch, fake_workers):
    setup_admin(client)
    worker = add_worker(client)
    seed_node_health(worker["id"])
    tariff_id = default_tariff_id(client)
    assert signup(client, "pipeimport@example.com", "pipeimportpass1", tariff_id).status_code == 200
    login_ready(client, "pipeimport@example.com", "pipeimportpass1")

    source = tmp_path / "clip.mp3"
    source.write_bytes(b"ID3" + b"\x00" * 128)

    from app.services.url_import import ImportResult

    def fake_download(url, **kwargs):
        return ImportResult(
            source_path=source,
            suffix=".mp3",
            original_filename="Sample Video.mp3",
            title="Sample Video",
            duration_sec=42.0,
            extractor_key="Youtube",
            host="youtube.com",
            platform_label="YouTube",
        )

    monkeypatch.setattr("app.services.import_runner.download_audio", fake_download)
    fake_workers.transcribe_mode = "success"

    created = client.post(
        "/api/v1/tasks/import",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "transcribe": True,
        },
    )
    assert created.status_code == 202, created.text
    import_id = created.json()["task_id"]
    body = wait_task(client, import_id, status="success")
    assert body["audio_id"]
    follow_up_id = body["meta"]["follow_up_task_id"]
    assert follow_up_id
    follow_up = wait_task(client, follow_up_id, status="success")
    assert follow_up["transcript_id"]


def test_import_unsupported_extractor(client):
    setup_admin(client)
    client.patch(
        "/api/v1/instance/settings",
        json={"import_allowed_extractors": ["Youtube"]},
    )
    tariff_id = default_tariff_id(client)
    assert signup(client, "tiktok@example.com", "tiktokpass1", tariff_id).status_code == 200
    login_ready(client, "tiktok@example.com", "tiktokpass1")

    response = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://www.tiktok.com/@user/video/1"},
    )
    assert response.status_code == 400
    assert err_code(response) == "unsupported_host"


def test_pick_import_source_prefers_largest_mp3(tmp_path):
    from app.services.url_import import _pick_import_source

    (tmp_path / "00000000-0000-0123-abcd-000000000000.info.json").write_text("{}")
    (tmp_path / "00000000-0000-0123-abcd-000000000000.jpeg").write_bytes(b"\xff" * 32)
    small = tmp_path / "00000000-0000-0123-abcd-000000000000.mp3"
    large = tmp_path / "00000000-0000-0123-abcd-000000000001.mp3"
    small.write_bytes(b"ID3" + b"\x00" * 64)
    large.write_bytes(b"ID3" + b"\x00" * 4096)

    picked = _pick_import_source(tmp_path)
    assert picked == large


def test_download_audio_payload_too_large_uses_largest_artifact(monkeypatch):
    from pathlib import Path

    from app.services.url_import import UrlImportError, download_audio

    def fake_probe(url, **kwargs):
        return {
            "extractor_key": "Rutube",
            "platform_label": "Rutube",
            "host": "rutube.ru",
            "title": "Clip",
            "duration_sec": 30.0,
        }

    def fake_ytdl(url, *, outtmpl=None, download=False, **kwargs):
        assert download is True
        assert outtmpl is not None
        parent = Path(outtmpl).parent
        (parent / "00000000-0000-0123-abcd-000000000000.info.json").write_text("{}")
        (parent / "00000000-0000-0123-abcd-000000000000.jpeg").write_bytes(b"\xff" * 64)
        (parent / "00000000-0000-0123-abcd-000000000000.mp3").write_bytes(b"ID3" + b"\x00" * 512)
        return {}

    monkeypatch.setattr("app.services.url_import.probe_url", fake_probe)
    monkeypatch.setattr("app.services.url_import._run_ytdl", fake_ytdl)

    with pytest.raises(UrlImportError) as exc:
        download_audio(
            "https://rutube.ru/video/abc/",
            settings_allowed=["Rutube"],
            proxy=None,
            max_audio_bitrate_kbps=64,
            max_bytes=256,
        )
    assert exc.value.code == "payload_too_large"
    assert exc.value.meta["bytes"] > 256


def test_download_audio_rejects_by_duration_before_download(monkeypatch):
    from app.services.url_import import UrlImportError, download_audio

    def fake_probe(url, **kwargs):
        return {
            "extractor_key": "Rutube",
            "platform_label": "Rutube",
            "host": "rutube.ru",
            "title": "Long stream",
            "duration_sec": 3600.0,
        }

    def fail_ytdl(*args, **kwargs):
        raise AssertionError("yt-dlp download should not run when duration exceeds cap")

    monkeypatch.setattr("app.services.url_import.probe_url", fake_probe)
    monkeypatch.setattr("app.services.url_import._run_ytdl", fail_ytdl)

    with pytest.raises(UrlImportError) as exc:
        download_audio(
            "https://rutube.ru/video/abc/",
            settings_allowed=["Rutube"],
            proxy=None,
            max_audio_bitrate_kbps=64,
            max_bytes=1024,
        )
    assert exc.value.code == "payload_too_large"


def test_import_task_payload_too_large_after_download(client, tmp_path, monkeypatch):
    from app.services.url_import import ImportResult

    setup_admin(client)
    tiny = create_tariff(client, name="TinyImport", max_upload_bytes=256)
    logout(client)
    assert signup(client, "tinyimport@example.com", "tinyimportpass1", tiny["id"]).status_code == 200
    login_ready(client, "tinyimport@example.com", "tinyimportpass1")

    source = tmp_path / "big.mp3"
    source.write_bytes(b"ID3" + b"\x00" * 512)

    def fake_download(url, **kwargs):
        assert kwargs["max_bytes"] == 256
        return ImportResult(
            source_path=source,
            suffix=".mp3",
            original_filename="big.mp3",
            title="Big",
            duration_sec=10.0,
            extractor_key="Rutube",
            host="rutube.ru",
            platform_label="Rutube",
        )

    monkeypatch.setattr("app.services.import_runner.download_audio", fake_download)

    created = client.post(
        "/api/v1/tasks/import",
        json={"url": "https://rutube.ru/video/abc123/"},
    )
    assert created.status_code == 202, created.text
    body = wait_task(client, created.json()["task_id"], status="error")
    assert body["error"]["code"] == "payload_too_large"

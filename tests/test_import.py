"""URL import tasks and instance whitelist."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import (
    default_tariff_id,
    err_code,
    login_ready,
    logout,
    setup_admin,
    signup,
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
    from app.models import InstanceSettings
    from app.services.import_platforms import effective_download_proxy

    settings = InstanceSettings(
        id=1,
        download_proxy_url="socks5://127.0.0.1:1080",
        download_proxy_enabled=False,
    )
    assert effective_download_proxy(settings) is None
    settings.download_proxy_enabled = True
    assert effective_download_proxy(settings) == "socks5://127.0.0.1:1080"


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

"""Regression tests for SPA static file path traversal (H7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import resolve_spa_path, spa_response


@pytest.fixture
def web_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    (dist / "icons.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    return dist


@pytest.fixture
def spa_test_client(web_dist: Path) -> TestClient:
    app = FastAPI()

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return spa_response(web_dist, full_path)

    return TestClient(app)


def test_resolve_spa_path_serves_static_file_in_dist(web_dist: Path) -> None:
    assert resolve_spa_path(web_dist, "icons.svg") == web_dist / "icons.svg"


def test_resolve_spa_path_falls_back_to_index_for_spa_routes(web_dist: Path) -> None:
    assert resolve_spa_path(web_dist, "app/tasks") == "index"
    assert resolve_spa_path(web_dist, "login") == "index"


def test_resolve_spa_path_root_returns_index(web_dist: Path) -> None:
    assert resolve_spa_path(web_dist, "") == "index"


def test_resolve_spa_path_blocks_api_prefix(web_dist: Path) -> None:
    assert resolve_spa_path(web_dist, "api/v1/health") == "not_found"


def test_resolve_spa_path_blocks_directory_traversal(web_dist: Path) -> None:
    assert resolve_spa_path(web_dist, "../../secret.txt") == "not_found"
    assert resolve_spa_path(web_dist, "../..//secret.txt") == "not_found"
    assert resolve_spa_path(web_dist, "../../app/config.py") == "not_found"


def test_resolve_spa_path_blocks_absolute_path(web_dist: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    assert resolve_spa_path(web_dist, str(secret)) == "not_found"


def test_spa_response_blocks_traversal(web_dist: Path) -> None:
    response = spa_response(web_dist, "../../secret.txt")
    assert response.status_code == 404


def test_spa_response_serves_index_for_spa_route(web_dist: Path) -> None:
    response = spa_response(web_dist, "app/library/audio")
    assert response.status_code == 200
    assert response.path == web_dist / "index.html"


def test_spa_response_serves_static_file(web_dist: Path) -> None:
    response = spa_response(web_dist, "icons.svg")
    assert response.status_code == 200
    assert response.path == web_dist / "icons.svg"


def test_spa_client_blocks_traversal(spa_test_client: TestClient) -> None:
    # TestClient normalizes literal ../..; encoded slashes match real HTTP clients.
    response = spa_test_client.get("/..%2f..%2fsecret.txt")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert "TOP SECRET" not in response.text


def test_spa_client_serves_spa_route(spa_test_client: TestClient) -> None:
    response = spa_test_client.get("/app/tasks")
    assert response.status_code == 200
    assert "spa" in response.text


def test_spa_client_serves_static_file(spa_test_client: TestClient) -> None:
    response = spa_test_client.get("/icons.svg")
    assert response.status_code == 200
    assert "<svg/>" in response.text

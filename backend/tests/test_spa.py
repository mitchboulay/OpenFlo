from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.export_openapi import OPENAPI_PATH, render_openapi
from app.main import create_app
from app.spa import is_spa_path
from conftest import mark_setup_ready

INDEX_HTML = "<!doctype html><title>OpenFLO</title>"


def _client(tmp_path: Path, dist: Path) -> TestClient:
    settings = Settings(db_path=str(tmp_path / "backend.db"), ui_dist=str(dist))
    return TestClient(mark_setup_ready(create_app(settings)))


@pytest.fixture
def spa_client(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML)
    (dist / "assets" / "x.js").write_text("console.log('x')")
    with _client(tmp_path, dist) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/devices/abc", "/homes/1/add"])
def test_client_routes_return_index(spa_client: TestClient, path: str) -> None:
    response = spa_client.get(path)
    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["cache-control"] == "no-cache"


def test_assets_are_served(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/x.js")
    assert response.status_code == 200
    assert response.text == "console.log('x')"


def test_missing_asset_is_404_not_index(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/missing.js")
    assert response.status_code == 404
    assert response.text != INDEX_HTML


def test_healthz_not_shadowed(spa_client: TestClient) -> None:
    response = spa_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_device_api_not_shadowed(spa_client: TestClient) -> None:
    response = spa_client.post("/device-api/v2/healthcheck", json={})
    assert response.headers["content-type"].startswith("application/json")
    assert response.text != INDEX_HTML
    # GET on a POST-only device route keeps its 405; the fallback never answers it.
    assert spa_client.get("/device-api/v2/healthcheck").status_code == 405


def test_unknown_api_v1_path_is_a_v1_error(spa_client: TestClient) -> None:
    response = spa_client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Not Found"}


def test_unknown_device_api_path_stays_json_404(spa_client: TestClient) -> None:
    response = spa_client.get("/device-api/nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_non_get_unknown_path_is_404(spa_client: TestClient) -> None:
    assert spa_client.post("/devices/abc").status_code == 404


def test_openapi_served_under_api_v1(spa_client: TestClient) -> None:
    response = spa_client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.json()["openapi"].startswith("3.")
    assert spa_client.get("/docs").text == INDEX_HTML  # docs UI stays off


def test_without_dist_nothing_is_mounted(tmp_path: Path) -> None:
    with _client(tmp_path, tmp_path / "absent") as client:
        assert client.get("/").status_code == 404
        assert client.get("/devices/abc").status_code == 404
        assert client.get("/healthz").status_code == 200


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", True),
        ("/devices/abc", True),
        ("/apis", True),
        ("/healthz", False),
        ("/api", False),
        ("/api/v1/x", False),
        ("/admin/devices", True),  # /admin was retired for /api/v1 (B1.4)
        ("/device-api/v2/register", False),
        ("/assets/x.js", False),
    ],
)
def test_is_spa_path(path: str, expected: bool) -> None:
    assert is_spa_path(path) is expected


def test_committed_openapi_matches_app() -> None:
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi(), (
        "backend/openapi.json is stale: run `python -m app.export_openapi` "
        "then `npm run gen:api` in ui/"
    )

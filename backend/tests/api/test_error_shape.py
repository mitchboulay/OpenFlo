from __future__ import annotations

import hashlib
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import tokens
from conftest import DEVICE_ID, mark_setup_ready

from .conftest import Api

CODE = re.compile(r"^[A-Z][A-Z0-9_]*$")
TOKEN = "bootstrap-secret-0123456789"


def assert_error(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code and CODE.fullmatch(body["code"])
    assert isinstance(body["message"], str) and body["message"]
    assert set(body) <= {"code", "message", "detail"}
    return body


def _client(tmp_path: Any, **overrides: Any) -> TestClient:
    return TestClient(mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "auth.db"), **overrides))))


def test_validation_errors_carry_details(api: Api) -> None:
    body = assert_error(api.post("/homes", {"name": "", "colour": "red"}), 422, "INVALID_REQUEST")
    locations = {".".join(e["loc"]) for e in body["detail"]["errors"]}
    assert locations == {"body.name", "body.colour"}


def test_unknown_route_and_method(api: Api) -> None:
    assert_error(api.get("/nope"), 404, "NOT_FOUND")
    assert_error(api.put("/homes"), 405, "METHOD_NOT_ALLOWED")


def test_service_errors(api: Api) -> None:
    assert_error(api.get("/devices/NOPE"), 404, "DEVICE_NOT_FOUND")
    assert_error(api.post(f"/devices/{DEVICE_ID}/dispense"), 409, "DISPENSING_LOCKED")


def test_device_api_errors_keep_their_shape(api: Api) -> None:
    """The device API never gains "detail" (or "fields", outside the bottle lock)."""
    body = api.client.post("/device-api/v2/update-device", json={"batteryLevel": "high"},
                           headers={"x-device-id": DEVICE_ID}).json()
    assert set(body) == {"code", "message"} and body["code"] == "INVALID_REQUEST"


LOGIN_MODES: dict[str, dict[str, Any]] = {
    "basic": {},
    "oidc": {"oidc_issuer": "https://idp.example", "oidc_client_id": "openflo"},
    "proxy": {"trusted_proxy_cidr": "10.9.9.0/24"},
}


@pytest.mark.parametrize("mode", sorted(LOGIN_MODES))
def test_login_modes_require_a_token(tmp_path: Any, mode: str) -> None:
    with _client(tmp_path, auth_mode=mode, **LOGIN_MODES[mode]) as client:
        assert_error(client.get("/api/v1/homes"), 401, "AUTH_REQUIRED")
        assert client.get("/healthz").status_code == 200  # exempt


def test_bootstrap_token(tmp_path: Any) -> None:
    with _client(tmp_path, auth_mode="basic", api_token=TOKEN) as client:
        assert client.get("/api/v1/homes", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
        assert_error(client.get("/api/v1/homes", headers={"Authorization": "Bearer wrong"}), 401, "INVALID_TOKEN")
        assert_error(client.get("/api/v1/homes", headers={"Authorization": "Bearer "}), 401, "INVALID_TOKEN")
        created = client.post("/api/v1/homes", json={"name": "Cabin"},
                              headers={"Authorization": f"Bearer {TOKEN}"})
        with client.app.state.db.connection() as conn:
            row = conn.execute("SELECT actor FROM homes WHERE id = ?", (created.json()["id"],)).fetchone()
            stored = tokens.list_unrevoked(conn)
        assert row[0] == "bootstrap"
        # Only the digest is stored, and it is never the plaintext.
        assert [t.token_sha256 for t in stored] == [hashlib.sha256(TOKEN.encode()).hexdigest()]
        assert stored[0].last_used_at is not None


def test_a_bad_bearer_is_rejected_even_in_none_mode(api: Api) -> None:
    assert_error(api.get("/homes", headers={"Authorization": "Bearer nope"}), 401, "INVALID_TOKEN")


def test_changing_the_env_token_revokes_the_old_one(tmp_path: Any) -> None:
    with _client(tmp_path, auth_mode="basic", api_token=TOKEN):
        pass
    with _client(tmp_path, auth_mode="basic", api_token="rotated-token-9876543210") as client:
        assert_error(client.get("/api/v1/homes", headers={"Authorization": f"Bearer {TOKEN}"}), 401, "INVALID_TOKEN")
        assert client.get("/api/v1/homes", headers={"Authorization": "Bearer rotated-token-9876543210"}).status_code == 200
    with _client(tmp_path, auth_mode="basic") as client:  # unset: no bootstrap token at all
        bearer = {"Authorization": "Bearer rotated-token-9876543210"}
        assert_error(client.get("/api/v1/homes", headers=bearer), 401, "INVALID_TOKEN")


def test_openapi_documents_the_error_shape(api: Api) -> None:
    spec = api.client.get("/api/v1/openapi.json").json()
    responses = spec["paths"]["/api/v1/homes"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorBody")
    assert not any(p.startswith("/admin") for p in spec["paths"])

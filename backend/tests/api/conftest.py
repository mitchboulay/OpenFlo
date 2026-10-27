from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import devices, homes
from conftest import DEVICE_ID, mark_setup_ready

API = "/api/v1"
DEV = {"x-device-id": DEVICE_ID}


class Api:
    """A TestClient in ``none`` auth mode with one active device in home "Home"."""

    def __init__(self, client: TestClient):
        self.client = client
        self.app: Any = client.app
        with self.app.state.db.connection() as conn:
            self.home_id = homes.create(conn, "Home", "UTC", "tester").id
            devices.create(conn, DEVICE_ID, "active", registered=True, home_id=self.home_id, name="Kitchen")

    def get(self, path: str, **kw: Any) -> Any:
        return self.client.get(API + path, **kw)

    def post(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.client.post(API + path, json=json, **kw)

    def patch(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.client.patch(API + path, json=json, **kw)

    def put(self, path: str, json: Any = None, **kw: Any) -> Any:
        return self.client.put(API + path, json=json, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.client.delete(API + path, **kw)

    def device_post(self, endpoint: str, body: Any = None, device_id: str = DEVICE_ID) -> Any:
        return self.client.post(f"/device-api/v2/{endpoint}", json=body or {}, headers={"x-device-id": device_id})

    def unlock(self) -> None:
        assert self.patch(f"/devices/{DEVICE_ID}/controls", {"dispensing_enabled": True}).status_code == 200

    def sql(self, statement: str, params: tuple[Any, ...] = ()) -> None:
        with self.app.state.db.connection() as conn:
            conn.execute(statement, params)

    def add_telemetry(self, received_at: str, **payload: Any) -> None:
        self.sql(
            "INSERT INTO telemetry (device_id, received_at, source, payload_json, payload_sha256)"
            " VALUES (?, ?, 'cloud', ?, '')",
            (DEVICE_ID, received_at, json.dumps(payload)),
        )


def make_api(tmp_path: Any, **overrides: Any) -> Iterator[Api]:
    settings = Settings(db_path=str(tmp_path / "api.db"), auth_mode="none", **overrides)
    with TestClient(mark_setup_ready(create_app(settings))) as client:
        yield Api(client)


@pytest.fixture
def api(tmp_path: Any) -> Iterator[Api]:
    yield from make_api(tmp_path)


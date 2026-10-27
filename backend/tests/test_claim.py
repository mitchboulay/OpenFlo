"""Claiming unclaimed devices into a home (FR-5)."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import homes
from app.services.device_policy import BOTTLE_LOCK_BODY
from conftest import DEVICE_ID, mark_setup_ready, update_payload

DEV = {"x-device-id": DEVICE_ID}


@pytest.fixture
def api(tmp_path: Any) -> Iterator[tuple[TestClient, int]]:
    app = mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "c.db"), auth_mode="none")))
    with TestClient(app) as client:
        with app.state.db.connection() as conn:
            home_id = homes.create(conn, "Home", "UTC", "tester").id
        # First contact from an unknown ID creates the unclaimed row (under the cap).
        assert client.post("/device-api/v2/update-device", json=update_payload(), headers=DEV).status_code == 422
        yield client, home_id


def _claim(client: TestClient, home_id: int, device_id: str = DEVICE_ID) -> Any:
    return client.post(f"/api/v1/devices/{device_id}/claim",
                       json={"home_id": home_id, "name": " Kitchen ", "location": "Sink"})


def test_claim_makes_the_device_active_with_dispensing_off(api: tuple[TestClient, int]) -> None:
    client, home_id = api
    assert [d["device_id"] for d in client.get("/api/v1/devices/unclaimed").json()] == [DEVICE_ID]
    response = _claim(client, home_id)
    assert response.status_code == 200
    detail = response.json()
    assert (detail["status"], detail["home_id"], detail["name"], detail["location"]) == (
        "active", home_id, "Kitchen", "Sink")
    assert detail["installed_at"] is not None
    assert detail["controls"]["dispensing_enabled"] is False
    assert client.get("/api/v1/devices/unclaimed").json() == []
    assert client.post("/device-api/v2/update-device", json=update_payload(), headers=DEV).status_code == 200
    bottle = client.post("/device-api/v2/get-bottle", headers=DEV)
    assert bottle.json() == BOTTLE_LOCK_BODY  # dispensing off: the lock, never an authorization


def test_claim_turns_an_enabled_dispensing_switch_off(api: tuple[TestClient, int]) -> None:
    client, home_id = api
    repo = client.app.state.repo  # type: ignore[attr-defined]
    repo.update_controls(DEVICE_ID, {"dispensing_enabled": True, "actor": "tester"})
    assert _claim(client, home_id).json()["controls"]["dispensing_enabled"] is False


def test_only_unclaimed_devices_can_be_claimed(api: tuple[TestClient, int]) -> None:
    client, home_id = api
    assert _claim(client, home_id).status_code == 200
    again = _claim(client, home_id)
    assert again.status_code == 409 and again.json()["code"] == "NOT_UNCLAIMED"


@pytest.mark.parametrize("device_id, home_offset, code", [
    ("FFFFFFFFFFFFFFFF", 0, "DEVICE_NOT_FOUND"),
    (DEVICE_ID, 999, "HOME_NOT_FOUND"),
])
def test_claim_needs_an_existing_device_and_home(
    api: tuple[TestClient, int], device_id: str, home_offset: int, code: str
) -> None:
    client, home_id = api
    response = _claim(client, home_id + home_offset, device_id)
    assert response.status_code == 404 and response.json()["code"] == code


def test_claim_validates_the_body(api: tuple[TestClient, int]) -> None:
    client, home_id = api
    response = client.post(f"/api/v1/devices/{DEVICE_ID}/claim", json={"home_id": home_id, "name": ""})
    assert response.status_code == 422

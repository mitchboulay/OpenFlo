from __future__ import annotations

import json
from pathlib import Path

from app.models import ScheduleItem, UpdateDeviceRequest
from conftest import pairing_session

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_update_fixture_validates():
    model = UpdateDeviceRequest.model_validate(_load("update_device.json"))
    assert model.firmwareVersion == "3.0.64"


def test_register_fixture_round_trip(client):
    body = _load("register_device.json")
    pairing_session(client.app, "fixture-ott")
    client.post("/device-api/v2/healthcheck", json={"deviceId": body["deviceId"]})
    response = client.post(
        "/device-api/v2/register",
        json=body,
        headers={"x-device-ott": "fixture-ott"},
    )
    assert response.status_code == 200


def test_schedule_fixture_validates():
    body = _load("schedule_response.json")
    items = [ScheduleItem.model_validate(item) for item in body["data"]]
    assert items[0].doseCount == 1
    assert items[0].cmd == 0

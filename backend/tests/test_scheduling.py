from __future__ import annotations

from conftest import add_once_rule, make_client, register, update

DEVICE = "D8256700000A0001"


def _registered(tmp_path, **overrides):
    c, app = make_client(tmp_path, **overrides)
    c.__enter__()
    assert register(c).status_code == 200
    return c, app


def test_schedule_and_bottle_disabled_by_default(tmp_path):
    c, app = _registered(tmp_path)
    try:
        # A rule alone serves nothing: schedules and dispensing are both off until the operator turns them on.
        add_once_rule(app)
        app.state.repo.update_controls(DEVICE, {"dispensing_enabled": False, "schedules_enabled": False})
        schedule = c.post(
            "/device-api/v2/get-schedule",
            headers={"x-device-id": DEVICE},
        )
        bottle = c.post(
            "/device-api/v2/get-bottle",
            headers={"x-device-id": DEVICE},
        )
    finally:
        c.__exit__(None, None, None)
    assert schedule.status_code == 200
    assert schedule.json() == {"data": []}
    # Locked by default: the firmware's own "not authorized" code (with fields, so
    # FUN_40094750 acts on it); 422 also clears the bottle-sync flag.
    assert bottle.status_code == 422
    assert bottle.json() == {
        "fields": {},
        "code": "BOTTLE_INSTALLED_NOT_AUTHORIZED",
        "message": "dispensing is locked by the operator",
    }


def test_schedule_sync_flag_and_empty_schedule(tmp_path):
    c, app = _registered(tmp_path)
    try:
        first = update(c)
        assert first.status_code == 200
        assert first.json()["data"]["isScheduleSynced"] is False

        schedule = c.post(
            "/device-api/v2/get-schedule",
            headers={"x-device-id": DEVICE},
        )
        assert schedule.status_code == 200
        assert schedule.json() == {"data": []}

        second = update(c)
        assert second.json()["data"]["isScheduleSynced"] is True
    finally:
        c.__exit__(None, None, None)


def test_schedule_response_contains_configured_items(tmp_path):
    c, app = _registered(tmp_path)
    try:
        first = add_once_rule(app)
        add_once_rule(app, at=first + 3600, dose_count=2)
        response = c.post(
            "/device-api/v2/get-schedule",
            headers={"x-device-id": DEVICE},
        )
        body = response.json()
        assert response.status_code == 200
        assert [item["doseCount"] for item in body["data"]] == [1, 2]
        # cmd is always 0 (normal window); the exact-time window is never used.
        assert all(item["cmd"] == 0 for item in body["data"])
        assert all("remoteDispense" not in item for item in body["data"])
    finally:
        c.__exit__(None, None, None)


def test_get_fw_suppresses_ota(client):
    register(client)
    response = client.post(
        "/device-api/v2/get-fw",
        json={"firmwareVersion": "3.0.64", "deviceId": DEVICE},
        headers={"x-device-id": DEVICE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["actualFirmwareVersion"] == "3.0.64"
    assert "url" not in body


def test_bottle_authorization_record_shape(tmp_path):
    c, app = _registered(tmp_path)
    app.state.repo.update_controls(DEVICE, {"dispensing_enabled": True})
    try:
        bottle = c.post("/device-api/v2/get-bottle", headers={"x-device-id": DEVICE})
    finally:
        c.__exit__(None, None, None)
    body = bottle.json()
    assert bottle.status_code == 200
    # Volume is tracked server-side: the counter is topped up so the device never self-locks.
    assert body["data"]["dispenseLeft"] == body["data"]["dispenseNumber"] == 100
    # Full 6-slot table, slot order, uniform open time (177 mL standard dose), at the top level.
    assert body["config"] == [{"index": i, "dispenseTime": 65} for i in range(6)]
    assert "config" not in body["data"]
    assert "remoteDispense" not in bottle.text


def test_relocking_returns_firmware_not_authorized_code(tmp_path):
    c, app = _registered(tmp_path)
    app.state.repo.update_controls(DEVICE, {"dispensing_enabled": True})
    app.state.repo.update_controls(DEVICE, {"dispensing_enabled": False})
    try:
        bottle = c.post("/device-api/v2/get-bottle", headers={"x-device-id": DEVICE})
    finally:
        c.__exit__(None, None, None)
    assert bottle.status_code == 422
    assert bottle.json()["code"] == "BOTTLE_INSTALLED_NOT_AUTHORIZED"

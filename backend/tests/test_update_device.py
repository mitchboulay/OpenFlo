from __future__ import annotations

from conftest import register, update, update_payload


def test_update_device_success_and_safe_response(client):
    assert register(client).status_code == 200

    response = update(client)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["isUpToDate"] is True
    assert "remoteDispense" not in data
    assert "url" not in data
    assert "extPowerState" not in data
    assert "isSettingsSynced" not in data
    assert client.app.state.repo.count_telemetry() == 1


def test_update_device_requires_registration(client):
    response = update(client)
    assert response.status_code == 422
    assert response.json()["code"] == "DEVICE_NOT_REGISTERED"


def test_update_device_missing_header(client):
    response = client.post(
        "/device-api/v2/update-device", json=update_payload()
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_DEVICE_ID"


def test_update_device_wrong_type(client):
    assert register(client).status_code == 200
    response = update(client, batteryLevel="high")
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_update_device_partial_payload_and_unknown_field(client):
    assert register(client).status_code == 200
    response = client.post(
        "/device-api/v2/update-device",
        json={"batteryLevel": 50, "futureField": {"x": 1}},
        headers={"x-device-id": "D8256700000A0001"},
    )
    assert response.status_code == 200
    latest = client.app.state.repo.latest_telemetry("D8256700000A0001")
    assert latest is not None
    assert '"futureField"' in latest["payload_json"]


def test_fast_sync_time_is_opt_in_and_sends_only_that_key(tmp_path):
    from conftest import make_client, register, update_payload

    default, _ = make_client(tmp_path)
    with default:
        register(default)
        plain = default.post(
            "/device-api/v2/update-device",
            json=update_payload(),
            headers={"x-device-id": "D8256700000A0001"},
        )
    assert "config" not in plain.json()["data"]

    tuned, app = make_client(tmp_path)
    app.state.repo.update_controls("D8256700000A0001", {"sync_interval_seconds": 3900})
    with tuned:
        resp = tuned.post(
            "/device-api/v2/update-device",
            json=update_payload(),
            headers={"x-device-id": "D8256700000A0001"},
        )
    # A device never served a schedule is told to fetch one (empty here, clearing anything it held).
    assert resp.json() == {"data": {"isUpToDate": True, "isScheduleSynced": False, "config": {"fast-sync-time": 3900}}}


def test_shift_time_is_sent_before_fast_sync_time(tmp_path):
    from conftest import make_client, register, update_payload

    c, app = make_client(tmp_path)
    app.state.repo.update_controls(
        "D8256700000A0001", {"sync_interval_seconds": 900, "shift_time_seconds": 60}
    )
    with c:
        register(c)
        resp = c.post(
            "/device-api/v2/update-device",
            json=update_payload(),
            headers={"x-device-id": "D8256700000A0001"},
        )
    config = resp.json()["data"]["config"]
    assert list(config) == ["shift-time", "fast-sync-time"]
    assert resp.text.index("shift-time") < resp.text.index("fast-sync-time")
    assert config == {"shift-time": 60, "fast-sync-time": 900}

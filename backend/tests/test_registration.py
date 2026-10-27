from __future__ import annotations

from app.repositories import devices
from conftest import DEVICE_ID, open_awaiting_join_session, register


def test_registration_succeeds_once_per_token(client):
    first = register(client)
    replay = register(client)  # the token is one-time: its session is completed
    assert first.status_code == 200
    assert first.json() == {}
    assert replay.status_code == 422
    assert replay.json() == {"code": "NOT_FOUND", "message": replay.json()["message"]}
    assert client.app.state.repo.count_devices() == 1


def test_registration_invalid_device_id(client):
    response = client.post(
        "/device-api/v2/register",
        json={"deviceId": "bad id with spaces"},
        headers={"x-device-ott": "ott"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MALFORMED_DEVICE_ID"


def test_registration_does_not_store_token(client):
    register(client, ott="super-secret-ott")
    logs = client.app.state.repo.recent_logs(50)
    assert all("super-secret-ott" not in str(row) for row in logs)


def test_firmware_pairing_sequence_succeeds_while_a_session_awaits_join(app_client):
    # Pairing_task (0x40093300): healthcheck until 200, then register, then syncs.
    c, app = app_client
    open_awaiting_join_session(app)
    health = c.post(
        "/device-api/v2/healthcheck",
        json={"deviceId": DEVICE_ID},
        headers={"x-device-id": DEVICE_ID},
    )
    assert app.state.repo.count_devices() == 0
    reg = c.post(
        "/device-api/v2/register",
        json={"deviceId": DEVICE_ID},
        headers={"x-device-ott": "session-ott"},
    )
    sync = c.post(
        "/device-api/v2/update-device",
        json={"batteryLevel": 94, "firmwareVersion": "3.0.64"},
        headers={"x-device-id": DEVICE_ID},
    )
    assert health.status_code == 200
    assert reg.status_code == 200
    # First sync: no schedule was ever served, so the device is told to fetch its (empty) one.
    assert sync.json() == {"data": {"isUpToDate": True, "isScheduleSynced": False}}
    with app.state.db.connection() as conn:
        device = devices.get(conn, DEVICE_ID)
    assert device is not None and device.status == "active" and device.registered

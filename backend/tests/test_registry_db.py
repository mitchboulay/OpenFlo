"""Device API policy table (requirements: "Device API policy"), driven only by ``devices.status``."""
from __future__ import annotations

import pytest

from app.repositories import devices, provisioning
from conftest import DEVICE_ID, open_awaiting_join_session, seed_device, update_payload

HEADERS = {"x-device-id": DEVICE_ID}


def _healthcheck(client):
    return client.post("/device-api/v2/healthcheck", json={"deviceId": DEVICE_ID}, headers=HEADERS)


def _register(client, ott: str = "ott"):
    return client.post("/device-api/v2/register", json={"deviceId": DEVICE_ID}, headers={"x-device-ott": ott})


def _update(client):
    return client.post("/device-api/v2/update-device", json=update_payload(), headers=HEADERS)


def _assert_ignorable(response, code: str) -> None:
    assert response.status_code == 422
    assert response.json() == {"code": code, "message": response.json()["message"]}


@pytest.mark.parametrize("status", ["active", "provisioning"])
def test_served_statuses_pass_every_endpoint(app_client, status):
    client, app = app_client
    seed_device(app, status=status)
    assert _healthcheck(client).status_code == 200
    _assert_ignorable(_register(client), "NOT_FOUND")  # registration needs a session token (AD-4)
    assert _update(client).status_code == 200


@pytest.mark.parametrize("status", ["unclaimed", "retired"])
def test_unclaimed_and_retired_are_answered_as_unregistered(app_client, status):
    client, app = app_client
    seed_device(app, status=status)
    _assert_ignorable(_healthcheck(client), "DEVICE_NOT_REGISTERED")
    _assert_ignorable(_update(client), "DEVICE_NOT_REGISTERED")
    _assert_ignorable(_register(client), "NOT_FOUND")
    get_fw = client.post(
        "/device-api/v2/get-fw", json={"firmwareVersion": "3.0.64", "deviceId": DEVICE_ID}, headers=HEADERS
    )
    _assert_ignorable(get_fw, "DEVICE_NOT_REGISTERED")
    with app.state.db.connection() as conn:
        device = devices.get(conn, DEVICE_ID)
    assert device is not None and device.status == status and not device.registered


def test_unknown_id_without_session(app_client):
    client, app = app_client
    _assert_ignorable(_healthcheck(client), "DEVICE_NOT_REGISTERED")
    _assert_ignorable(_register(client), "NOT_FOUND")
    assert app.state.repo.count_devices() == 0  # pairing endpoints never create rows
    _assert_ignorable(_update(client), "DEVICE_NOT_REGISTERED")
    with app.state.db.connection() as conn:
        device = devices.get(conn, DEVICE_ID)
    assert device is not None and device.status == "unclaimed"  # first sync contact, under the cap


def test_unknown_id_while_session_awaits_join_records_sighting(app_client):
    client, app = app_client
    open_awaiting_join_session(app)
    assert _healthcheck(client).status_code == 200
    with app.state.db.connection() as conn:
        sighting = provisioning.latest_sighting_for_ip(conn, "testclient", "2000-01-01T00:00:00+00:00")
    assert sighting is not None and sighting.device_id == DEVICE_ID
    assert _register(client, "session-ott").status_code == 200


def test_expired_session_does_not_open_pairing(app_client):
    client, app = app_client
    open_awaiting_join_session(app, expires_at="2000-01-01T00:00:00+00:00")
    _assert_ignorable(_healthcheck(client), "DEVICE_NOT_REGISTERED")
    _assert_ignorable(_register(client), "NOT_FOUND")


def test_unclaimed_device_is_not_reopened_by_a_session_healthcheck(app_client):
    # AD-4: the awaiting_join exception is for unknown IDs only.
    client, app = app_client
    seed_device(app, status="unclaimed")
    open_awaiting_join_session(app)
    _assert_ignorable(_healthcheck(client), "DEVICE_NOT_REGISTERED")


def test_malformed_id_is_rejected_before_policy(app_client):
    client, _ = app_client
    response = client.post("/device-api/v2/register", json={"deviceId": "bad id"}, headers={"x-device-ott": "o"})
    _assert_ignorable(response, "MALFORMED_DEVICE_ID")

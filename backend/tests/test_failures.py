from __future__ import annotations

import json

import pytest

from app.services.device_policy import BOTTLE_LOCK_BODY, BOTTLE_LOCK_STATUS
from conftest import make_client, register

DEVICE = "D8256700000A0001"


def test_malformed_json(client):
    response = client.post(
        "/device-api/v2/register",
        content="{",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_oversized_body(tmp_path):
    c, _ = make_client(tmp_path, max_body_bytes=128)
    with c:
        response = c.post(
            "/device-api/v2/register",
            content="x" * 1024,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_health_events_and_qc(app_client):
    c, app = app_client
    register(c)
    health = c.post(
        "/device-api/v2/healthcheck",
        json={"deviceId": DEVICE},
        headers={"x-device-id": DEVICE},
    )
    events = c.post(
        "/device-api/v2/send-events",
        json=[{"type": "wake", "payload": {"reason": "timer"}}],
        headers={"x-device-id": DEVICE},
    )
    qc = c.post(
        "/device-api/v2/create-qc-report",
        json={
            "deviceId": DEVICE,
            "sessionId": 7,
            "data": {
                "bottleSwitchPassed": "PASSED",
                "userDispenses": "PASSED",
                "firmwareVersion": "3.0.64",
                "floatTestPassed": "skipped",
                "proVersion": False,
                "deviceType": 0,
            },
        },
        headers={"x-device-id": DEVICE},
    )
    assert health.status_code == 200
    assert events.status_code == 200
    assert qc.status_code == 200
    assert app.state.repo.count_events() == 3  # pairing healthcheck + healthcheck + events


def test_unknown_device_get_fw(client):
    response = client.post(
        "/device-api/v2/get-fw",
        json={"firmwareVersion": "3.0.64", "deviceId": DEVICE},
        headers={"x-device-id": DEVICE},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "DEVICE_NOT_REGISTERED"


def test_protocol_logs_redact_ott(client):
    register(client, ott="very-secret-ott")
    rows = client.app.state.repo.recent_logs(20)
    text = json.dumps(rows)
    assert "very-secret-ott" not in text
    assert rows


def test_firmware_reset_codes_cannot_be_constructed():
    from app.errors import FIRMWARE_RESET_CODES, ApiError

    for code in FIRMWARE_RESET_CODES:
        with pytest.raises(ValueError):
            ApiError(code, "x")


def test_no_endpoint_emits_firmware_reset_codes(client):
    endpoints = [
        "register", "update-device", "get-fw", "get-bottle", "get-schedule",
        "healthcheck", "send-events", "create-qc-report",
    ]
    bodies = [b"{}", b"not json", b'{"deviceId": "bad id"}', b"x" * 70000]
    headers = [{}, {"x-device-id": "UNREGISTERED00001"}, {"x-device-id": "bad id"}]
    for endpoint in endpoints:
        for body in bodies:
            for extra in headers:
                response = client.post(
                    f"/device-api/v2/{endpoint}",
                    content=body,
                    headers={"Content-Type": "application/json", **extra},
                )
                assert "INVALID_DEVICE_ID" not in response.text, (endpoint, body[:20], extra)
                assert "NOT_UNIQUE" not in response.text, (endpoint, body[:20], extra)
                if response.status_code != 200 and "fields" in response.json():
                    # Firmware ignores error bodies without "fields" (FUN_40094c80). The only exception is
                    # the bottle lock, served to known devices that may not dispense (here: the unclaimed
                    # row update-device created for UNREGISTERED00001).
                    assert endpoint == "get-bottle", (endpoint, body[:20], extra)
                    assert (response.status_code, response.json()) == (
                        BOTTLE_LOCK_STATUS, BOTTLE_LOCK_BODY
                    ), (endpoint, body[:20], extra)

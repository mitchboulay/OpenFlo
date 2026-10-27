"""Phase 5 — Deterministic protocol test fixtures.

Replay full device wake cycles as the firmware would execute them:
  register → update-device → (conditional sub-requests) → verify state.

Each fixture represents a scenario documented in device-sync-state-machine.md.
"""
from __future__ import annotations

from conftest import DEVICE_ID, add_once_rule, make_client, register, update

HEADERS = {"x-device-id": DEVICE_ID}


def _setup(tmp_path, **overrides):
    c, app = make_client(tmp_path, **overrides)
    c.__enter__()
    register(c)
    return c, app


# -- Fixture 1: Clean wake, all synced, device sleeps ----------------------

def test_fixture_clean_wake_all_synced(tmp_path):
    """Device wakes, posts telemetry, gets all-synced response, sleeps."""
    c, app = _setup(tmp_path)
    try:
        resp = update(c)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["isUpToDate"] is True
        assert "remoteDispense" not in data
        assert "url" not in data
        assert app.state.repo.count_telemetry() == 1
        assert app.state.repo.count_logs() >= 2  # register + update
    finally:
        c.__exit__(None, None, None)


# -- Fixture 2: Wake with schedule sync trigger ----------------------------

def test_fixture_schedule_sync_cycle(tmp_path):
    """Device wakes, gets isScheduleSynced=false, fetches schedule, next wake is synced."""
    c, app = _setup(tmp_path)
    try:
        # First wake: schedule not synced
        r1 = update(c)
        assert r1.json()["data"]["isScheduleSynced"] is False

        # Device fetches schedule (empty — no schedules configured)
        sched = c.post("/device-api/v2/get-schedule", headers=HEADERS)
        assert sched.status_code == 200
        assert sched.json()["data"] == []

        # Second wake: schedule now synced
        r2 = update(c)
        assert r2.json()["data"]["isScheduleSynced"] is True
    finally:
        c.__exit__(None, None, None)


# -- Fixture 3: Wake with pre-configured schedule items --------------------

def test_fixture_schedule_with_items(tmp_path):
    """Operator provisions schedule items; device receives them on sync."""
    c, app = _setup(tmp_path)
    try:
        first = add_once_rule(app)
        add_once_rule(app, at=first + 3600, dose_count=2)

        # First wake triggers schedule fetch
        r1 = update(c)
        assert r1.json()["data"]["isScheduleSynced"] is False

        sched = c.post("/device-api/v2/get-schedule", headers=HEADERS)
        body = sched.json()["data"]
        assert body == [
            {"timestamp": first, "doseCount": 1, "cmd": 0},
            {"timestamp": first + 3600, "doseCount": 2, "cmd": 0},
        ]

        # Second wake: synced
        r2 = update(c)
        assert r2.json()["data"]["isScheduleSynced"] is True
    finally:
        c.__exit__(None, None, None)


# -- Fixture 4: Firmware version check (OTA suppressed) --------------------

def test_fixture_get_fw_no_ota(tmp_path):
    """Device asks for firmware; emulator never returns an OTA URL."""
    c, _ = _setup(tmp_path)
    try:
        update(c)
        resp = c.post(
            "/device-api/v2/get-fw",
            json={"firmwareVersion": "3.0.64", "deviceId": DEVICE_ID},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["actualFirmwareVersion"] == "3.0.64"
        assert "url" not in body
        assert "redirectLocation" not in body
    finally:
        c.__exit__(None, None, None)


# -- Fixture 5: Full wake cycle with healthcheck + events ------------------

def test_fixture_full_wake_with_events(tmp_path):
    """Simulates a complete wake: register → update → healthcheck → events → qc."""
    c, app = _setup(tmp_path)
    try:
        update(c)

        c.post(
            "/device-api/v2/healthcheck",
            json={"deviceId": DEVICE_ID},
            headers=HEADERS,
        )
        c.post(
            "/device-api/v2/send-events",
            json=[{"type": "dispense", "ts": 1698300000}],
            headers=HEADERS,
        )
        c.post(
            "/device-api/v2/create-qc-report",
            json={
                "deviceId": DEVICE_ID,
                "sessionId": 1,
                "data": {
                    "bottleSwitchPassed": "PASSED",
                    "userDispenses": "PASSED",
                    "firmwareVersion": "3.0.64",
                    "floatTestPassed": "skipped",
                    "proVersion": False,
                    "deviceType": 0,
                },
            },
            headers=HEADERS,
        )

        assert app.state.repo.count_telemetry() == 1
        assert app.state.repo.count_events() == 3  # pairing healthcheck + healthcheck + events
    finally:
        c.__exit__(None, None, None)


# -- Fixture 6: Multiple wakes track firmware version ----------------------

def test_fixture_firmware_version_tracking(tmp_path):
    """Telemetry updates persist firmware version on the device record."""
    c, app = _setup(tmp_path)
    try:
        update(c, firmwareVersion="3.0.63")
        dev = app.state.repo.get_device(DEVICE_ID)
        assert dev["firmware_version"] == "3.0.63"

        update(c, firmwareVersion="3.0.64")
        dev = app.state.repo.get_device(DEVICE_ID)
        assert dev["firmware_version"] == "3.0.64"
    finally:
        c.__exit__(None, None, None)


# -- Fixture 8: Protocol log captures full request/response ----------------

def test_fixture_protocol_log_completeness(tmp_path):
    """Every endpoint call is logged with method, path, status, and headers."""
    c, app = _setup(tmp_path, log_payloads=True)
    try:
        update(c)
        logs = app.state.repo.recent_logs(50)
        paths = [row["path"] for row in logs]
        assert "/device-api/v2/register" in paths
        assert "/device-api/v2/update-device" in paths
        for row in logs:
            assert row["method"] in ("GET", "POST")
            assert row["status"] is not None
            assert row["headers_json"]
    finally:
        c.__exit__(None, None, None)


# -- Fixture 9: Safety invariant — response never contains dispense --------

def test_fixture_safety_no_dispense_ever(tmp_path):
    """No response from any endpoint ever contains remoteDispense.isActive=true."""
    c, app = _setup(tmp_path)
    app.state.repo.update_controls(DEVICE_ID, {"dispensing_enabled": True, "sync_interval_seconds": 3900})
    try:
        for _ in range(3):
            resp = update(c)
            data = resp.json().get("data", {})
            rd = data.get("remoteDispense", {})
            assert rd.get("isActive") is not True

        sched = c.post("/device-api/v2/get-schedule", headers=HEADERS)
        assert "remoteDispense" not in sched.text

        bottle = c.post("/device-api/v2/get-bottle", headers=HEADERS)
        assert "remoteDispense" not in bottle.text

        fw = c.post(
            "/device-api/v2/get-fw",
            json={"firmwareVersion": "3.0.64", "deviceId": DEVICE_ID},
            headers=HEADERS,
        )
        assert "remoteDispense" not in fw.text
    finally:
        c.__exit__(None, None, None)


# -- Fixture 10: Safety invariant — response never triggers OTA ------------

def test_fixture_safety_no_ota_ever(tmp_path):
    """No response ever returns isUpToDate=false or a redirectLocation URL."""
    c, _ = _setup(tmp_path)
    try:
        resp = update(c)
        data = resp.json()["data"]
        assert data.get("isUpToDate") is not False
        assert "redirectLocation" not in str(resp.json())
    finally:
        c.__exit__(None, None, None)

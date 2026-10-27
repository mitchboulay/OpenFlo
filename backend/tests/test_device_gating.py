"""Device-path abuse controls (AD-3, FR-13) and command withholding (FR-5, FR-6)."""
from __future__ import annotations

import json

from app.device_gate import INSTANCE_HEADER
from app.repositories import devices, flags
from app.repositories import settings as settings_repo
from app.services.device_policy import BOTTLE_LOCK_BODY
from conftest import DEVICE_ID, add_once_rule, seed_device, update_payload

IP_A = "198.51.100.7"
IP_B = "203.0.113.9"


def _post(client, path: str, device_id: str = DEVICE_ID, ip: str = IP_A, body: object = None):
    return client.post(
        f"/device-api/v2/{path}",
        json=update_payload() if body is None else body,
        headers={"x-device-id": device_id, "x-test-source-ip": ip},
    )


def _healthcheck(client, device_id: str = DEVICE_ID, ip: str = IP_A):
    return _post(client, "healthcheck", device_id, ip, {"deviceId": device_id})


def _open_flags(app, kind=None) -> list[flags.IdentityFlag]:
    with app.state.db.connection() as conn:
        found = flags.list_open(conn, DEVICE_ID)
    return [flag for flag in found if kind is None or flag.kind == kind]


def _device(app, device_id: str = DEVICE_ID) -> devices.Device | None:
    with app.state.db.connection() as conn:
        return devices.get(conn, device_id)


def _assert_rate_limited(response) -> None:
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert "fields" not in response.json()


def test_per_ip_bucket_trips_at_301_in_five_minutes(gated):
    client, app, clock = gated
    seed_device(app)
    for _ in range(300):
        assert _healthcheck(client).status_code == 200
    _assert_rate_limited(_healthcheck(client))
    assert _healthcheck(client, ip=IP_B).status_code == 200  # per IP
    clock.advance(1.0)  # token bucket: one request refills per second
    assert _healthcheck(client).status_code == 200
    _assert_rate_limited(_healthcheck(client))


def test_unknown_id_limiter_is_ten_per_minute_per_ip(gated):
    client, app, clock = gated
    seed_device(app)
    for n in range(10):
        assert _healthcheck(client, f"UNKNOWN{n:04d}").json()["code"] == "DEVICE_NOT_REGISTERED"
    _assert_rate_limited(_healthcheck(client, "UNKNOWN9999"))
    assert _healthcheck(client).status_code == 200  # known IDs are not limited by it
    assert _healthcheck(client, "UNKNOWN9999", ip=IP_B).json()["code"] == "DEVICE_NOT_REGISTERED"
    clock.advance(60)
    assert _healthcheck(client, "UNKNOWN9999").json()["code"] == "DEVICE_NOT_REGISTERED"


def test_unclaimed_cap_rejects_the_eleventh_without_a_row(gated):
    client, app, _ = gated
    for n in range(10):
        response = _post(client, "update-device", f"STRANGER{n:04d}", ip=f"192.0.2.{n + 1}")
        assert response.json()["code"] == "DEVICE_NOT_REGISTERED"
    eleventh = _post(client, "update-device", "STRANGER0010", ip="192.0.2.99")
    assert eleventh.status_code == 422
    assert eleventh.json() == {"code": "DEVICE_NOT_REGISTERED", "message": eleventh.json()["message"]}
    with app.state.db.connection() as conn:
        assert devices.count_by_status(conn, "unclaimed") == 10
        assert devices.get(conn, "STRANGER0010") is None
    assert app.state.device_gate.rejected_unknown == 1
    logged = [row for row in app.state.repo.recent_logs(50) if row["device_id"] == "STRANGER0010"]
    assert logged == []
    unclaimed = _device(app, "STRANGER0000")
    assert unclaimed is not None and unclaimed.last_ip == "192.0.2.1"


def test_ip_conflict_raised_once_and_not_duplicated(gated):
    client, app, clock = gated
    seed_device(app)
    assert _post(client, "update-device", ip=IP_A).status_code == 200
    clock.advance(30)
    _post(client, "update-device", ip=IP_B)
    clock.advance(30)
    _post(client, "update-device", ip=IP_A)
    clock.advance(30)
    _post(client, "update-device", ip=IP_B)
    raised = _open_flags(app, "ip_conflict")
    assert len(raised) == 1
    assert raised[0].detail == {"source_ip": IP_B, "other_ips": [IP_A]}
    assert _device(app).last_ip == IP_B


def test_new_ip_after_ten_quiet_minutes_is_not_a_conflict(gated):
    # Dynamic IPs and NAT changes are normal (no IP pinning).
    client, app, clock = gated
    seed_device(app)
    _post(client, "update-device", ip=IP_A)
    clock.advance(10 * 60 + 1)
    _post(client, "update-device", ip=IP_B)
    assert _open_flags(app) == []


def test_telemetry_implausible_on_firmware_change(gated):
    client, app, clock = gated
    seed_device(app)
    _post(client, "update-device", body=update_payload(firmwareVersion="3.0.64", deviceType=0, pcbVersion="6.3.0"))
    first = _device(app)
    assert (first.firmware_version, first.pcb_version) == ("3.0.64", "6.3.0")
    assert json.loads(first.metadata_json)["deviceType"] == 0
    assert _open_flags(app) == []

    _post(client, "update-device", body=update_payload(firmwareVersion="3.0.70"))
    _post(client, "update-device", body=update_payload(firmwareVersion="3.0.70", deviceType=3))
    raised = _open_flags(app, "telemetry_implausible")
    assert len(raised) == 1
    assert raised[0].detail == {"changed": {"firmwareVersion": {"stored": "3.0.64", "reported": "3.0.70"}}}
    assert _device(app).firmware_version == "3.0.70"


def test_remote_dispense_withheld_while_flagged_and_delivered_after_ack(gated):
    client, app, _ = gated
    seed_device(app)
    app.state.repo.update_controls(DEVICE_ID, {"dispensing_enabled": True})
    app.state.repo.queue_dispense(DEVICE_ID, nonce=4242)
    with app.state.db.connection() as conn:
        flag = flags.raise_flag(conn, DEVICE_ID, "ip_conflict", {"source_ip": IP_B, "other_ips": [IP_A]})

    withheld = _post(client, "update-device").json()["data"]
    assert "remoteDispense" not in withheld
    assert app.state.repo.pending_dispense(DEVICE_ID) is not None  # stays queued

    with app.state.db.connection() as conn:
        flags.ack(conn, flag.id, "tester")
    delivered = _post(client, "update-device").json()["data"]
    assert delivered["remoteDispense"] == {"isActive": True, "nonce": 4242}
    assert "remoteDispense" not in _post(client, "update-device").json()["data"]  # exactly once


def test_schedules_withheld_while_flagged(gated):
    client, app, _ = gated
    seed_device(app)
    add_once_rule(app)
    with app.state.db.connection() as conn:
        flag = flags.raise_flag(conn, DEVICE_ID, "telemetry_implausible", {"changed": {}})
    # Flagged: the device should hold nothing, so it is told to refetch and gets [].
    assert _post(client, "update-device").json()["data"]["isScheduleSynced"] is False
    assert _post(client, "get-schedule", body={}).json() == {"data": []}
    assert _post(client, "update-device").json()["data"]["isScheduleSynced"] is True
    with app.state.db.connection() as conn:
        flags.ack(conn, flag.id, "tester")
    # The ack changes what the device should hold: refetch, and the entry is served.
    assert _post(client, "update-device").json()["data"]["isScheduleSynced"] is False
    assert len(_post(client, "get-schedule", body={}).json()["data"]) == 1


def test_get_bottle_lock_for_flagged_and_unclaimed_devices(gated):
    client, app, _ = gated
    seed_device(app)
    app.state.repo.update_controls(DEVICE_ID, {"dispensing_enabled": True})
    assert _post(client, "get-bottle", body={}).status_code == 200
    with app.state.db.connection() as conn:
        flags.raise_flag(conn, DEVICE_ID, "ip_conflict", {"source_ip": IP_B, "other_ips": [IP_A]})
    flagged = _post(client, "get-bottle", body={})
    assert (flagged.status_code, flagged.json()) == (422, BOTTLE_LOCK_BODY)

    seed_device(app, "UNCLAIMED0001", status="unclaimed")
    app.state.repo.update_controls("UNCLAIMED0001", {"dispensing_enabled": True})
    unclaimed = _post(client, "get-bottle", "UNCLAIMED0001", body={})
    assert (unclaimed.status_code, unclaimed.json()) == (422, BOTTLE_LOCK_BODY)


def test_instance_header_on_every_device_response(gated):
    client, app, _ = gated
    with app.state.db.connection() as conn:
        instance_id = settings_repo.instance_id(conn)
    seed_device(app)
    responses = [_post(client, "update-device"), _healthcheck(client, "UNKNOWN0001")]
    for _ in range(300):
        _healthcheck(client, ip=IP_B)
    responses.append(_healthcheck(client, ip=IP_B))
    assert [r.status_code for r in responses] == [200, 422, 429]
    assert all(r.headers[INSTANCE_HEADER] == instance_id for r in responses)
    assert INSTANCE_HEADER not in client.get("/healthz").headers


def test_no_payloads_logged_for_unknown_ids(gated):
    client, app, _ = gated
    seed_device(app)
    _post(client, "update-device", "STRANGER0001")
    _post(client, "update-device")
    rows = {row["device_id"]: row for row in app.state.repo.recent_logs(50)}
    stranger, known = rows["STRANGER0001"], rows[DEVICE_ID]
    assert (stranger["request_json"], stranger["response_json"]) == (None, None)
    assert stranger["path"] == "/device-api/v2/update-device" and stranger["status"] == 422
    assert stranger["headers_json"]
    assert known["request_json"] is not None and known["response_json"] is not None

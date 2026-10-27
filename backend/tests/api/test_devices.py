from __future__ import annotations

from datetime import datetime, timedelta

from app.repositories import devices, flags
from conftest import DEVICE_ID, update_payload

from .conftest import Api

DETAIL_KEYS = {
    "device_id", "home_id", "name", "location", "status", "retire_requested_at", "installed_at", "mac", "last_ip",
    "hardware_type", "pcb_version", "firmware_version", "network_name", "signal", "battery_level", "ext_power",
    "first_seen", "last_seen", "last_sync", "next_expected_sync", "next_dose_at", "pending", "flags", "controls", "dosing",
    "bottle", "remote_dispense",
}


def test_detail_never_omits_nullable_fields(api: Api) -> None:
    body = api.get(f"/devices/{DEVICE_ID}").json()
    assert set(body) == DETAIL_KEYS
    assert body["mac"] is None and body["battery_level"] is None and body["bottle"] is None
    assert body["last_sync"] is None and body["next_expected_sync"] is None and body["pending"] == []
    assert body["next_dose_at"] is None
    assert body["dosing"]["profile"]["slug"] == "standard" and body["dosing"]["dose_ml"] == 177
    assert body["controls"] == {
        "dispensing_enabled": False, "wake_preset": None, "schedules_enabled": False,
        "sync_interval_seconds": None, "shift_time_seconds": None, "updated_at": None,
    }


def test_detail_reports_telemetry_and_sync(api: Api) -> None:
    sync = api.device_post("update-device", update_payload(batteryLevel=81, connectionLevel=64, networkName="Barn"))
    assert sync.status_code == 200
    body = api.get(f"/devices/{DEVICE_ID}").json()
    assert (body["battery_level"], body["signal"], body["network_name"], body["ext_power"]) == (81, 64, "Barn", False)
    assert body["firmware_version"] == "3.0.64" and body["last_ip"] == "testclient"
    started = datetime.fromisoformat(body["last_sync"])
    # No interval was ever sent: the firmware's own 48 h applies.
    assert datetime.fromisoformat(body["next_expected_sync"]) - started == timedelta(hours=48)
    api.patch(f"/devices/{DEVICE_ID}/controls", {"wake_preset": "responsive"})
    body = api.get(f"/devices/{DEVICE_ID}").json()
    assert datetime.fromisoformat(body["next_expected_sync"]) - started == timedelta(hours=1)


def test_pending_clears_per_item_at_the_next_sync(api: Api) -> None:
    api.unlock()
    api.put(f"/devices/{DEVICE_ID}/dosing", {"profile_id": 1, "dose_ml": 150})
    api.post(f"/devices/{DEVICE_ID}/dispense")
    pending = api.get(f"/devices/{DEVICE_ID}").json()["pending"]
    assert {p["kind"] for p in pending} == {"controls", "dose", "dispense"}

    api.device_post("update-device", update_payload())  # controls and the dispense go out
    assert {p["kind"] for p in api.get(f"/devices/{DEVICE_ID}").json()["pending"]} == {"dose"}
    assert api.device_post("get-bottle").status_code == 200  # the dose is served
    assert api.get(f"/devices/{DEVICE_ID}").json()["pending"] == []


def test_unclaimed_route_is_not_a_device_id(api: Api) -> None:
    with api.app.state.db.connection() as conn:
        devices.create(conn, "UNCLAIMED0001", "unclaimed", last_ip="203.0.113.9")
    listed = api.get("/devices/unclaimed").json()
    assert [(d["device_id"], d["last_ip"]) for d in listed] == [("UNCLAIMED0001", "203.0.113.9")]
    assert set(listed[0]) == {"device_id", "last_ip", "first_seen", "last_seen"}


def test_unknown_device_is_404(api: Api) -> None:
    response = api.get("/devices/NOPE")
    assert response.status_code == 404 and response.json()["code"] == "DEVICE_NOT_FOUND"


def test_patch_device_fields(api: Api) -> None:
    response = api.patch(f"/devices/{DEVICE_ID}", {
        "name": " Sink ", "location": "Under the sink", "installed_at": "2026-10-01T12:00:00-04:00",
    })
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["location"]) == ("Sink", "Under the sink")
    assert body["installed_at"] == "2026-10-01T16:00:00+00:00"
    assert api.patch(f"/devices/{DEVICE_ID}", {"location": None}).json()["location"] is None
    assert api.patch(f"/devices/{DEVICE_ID}", {"name": "x" * 41}).status_code == 422
    assert api.patch(f"/devices/{DEVICE_ID}", {"serial": "x"}).status_code == 422


def test_move_home_drops_the_old_home_liquid(api: Api) -> None:
    custom = api.post(f"/homes/{api.home_id}/liquid-profiles", {
        "name": "Bleach", "capacity_ml": 500, "flow_full_ml_s": 20, "default_dose_ml": 50,
    }).json()
    assert api.put(f"/devices/{DEVICE_ID}/dosing", {"profile_id": custom["id"], "dose_ml": 60}).status_code == 200
    other = api.post("/homes", {"name": "Other"}).json()
    moved = api.patch(f"/devices/{DEVICE_ID}", {"home_id": other["id"]}).json()
    assert moved["home_id"] == other["id"]
    assert moved["dosing"]["profile"]["slug"] == "standard" and moved["dosing"]["dose_ml"] == 177
    assert api.patch(f"/devices/{DEVICE_ID}", {"home_id": 999}).json()["code"] == "HOME_NOT_FOUND"


def test_dispense_now_lifecycle(api: Api) -> None:
    url = f"/devices/{DEVICE_ID}/dispense"
    locked = api.post(url)
    assert locked.status_code == 409 and locked.json()["code"] == "DISPENSING_LOCKED"
    api.unlock()
    first = api.post(url).json()
    assert api.post(url).json()["id"] == first["id"]  # one pending at a time
    cancelled = api.delete(url).json()
    assert cancelled["id"] == first["id"] and cancelled["cancelled_at"] is not None
    assert api.delete(url).json()["code"] == "NO_PENDING_DISPENSE"

    queued = api.post(url).json()
    sync = api.device_post("update-device", update_payload()).json()["data"]
    assert sync["remoteDispense"]["isActive"] is True
    assert "remoteDispense" not in api.device_post("update-device", update_payload()).json()["data"]
    api.device_post("send-events", {"data": [{"status": 0, "code": 1, "timestamp": 1_800_000_000}]})
    delivered = api.get(f"/devices/{DEVICE_ID}").json()["remote_dispense"]
    assert delivered["pending"] is None and delivered["last_delivered"]["id"] == queued["id"]
    assert delivered["last_delivered"]["confirmed_at"] is not None


def test_flags_withhold_dispense_until_acknowledged(api: Api) -> None:
    api.unlock()
    with api.app.state.db.connection() as conn:
        flag = flags.raise_flag(conn, DEVICE_ID, "ip_conflict", {"source_ip": "198.51.100.2", "other_ips": ["10.0.0.5"]})
        flags.raise_flag(conn, DEVICE_ID, "telemetry_implausible",
                         {"changed": {"pcbVersion": {"stored": "6.3.0", "reported": "7.0.0"}}})
    blocked = api.post(f"/devices/{DEVICE_ID}/dispense")
    assert blocked.status_code == 409 and blocked.json()["code"] == "IDENTITY_FLAGGED"

    listed = {f["kind"]: f for f in api.get(f"/devices/{DEVICE_ID}/flags").json()}
    assert listed["ip_conflict"]["detail"]["source_ips"] == ["10.0.0.5", "198.51.100.2"]
    telemetry_detail = listed["telemetry_implausible"]["detail"]
    assert (telemetry_detail["field"], telemetry_detail["old"], telemetry_detail["new"]) == ("pcbVersion", "6.3.0", "7.0.0")
    assert api.get(f"/devices/{DEVICE_ID}").json()["flags"] and api.get(f"/homes/{api.home_id}/devices").json()[0]["flagged"]

    acks = {row["id"]: api.post(f"/flags/{row['id']}/ack").json() for row in listed.values()}
    assert all(a["acked_by"] == "operator:local" and a["acked_at"] for a in acks.values())
    assert api.post(f"/flags/{flag.id}/ack").json()["acked_at"] == acks[flag.id]["acked_at"]  # idempotent
    assert api.post("/flags/999/ack").status_code == 404
    assert api.post(f"/devices/{DEVICE_ID}/dispense").status_code == 200

from __future__ import annotations

from conftest import DEVICE_ID, add_once_rule, update_payload

from .conftest import Api

RETIRE = f"/devices/{DEVICE_ID}/retire"


def _serve_a_schedule(api: Api) -> None:
    add_once_rule(api.app)
    assert api.device_post("get-schedule").json()["data"] != []


def test_retires_immediately_when_nothing_was_served(api: Api) -> None:
    response = api.post(RETIRE, {})
    assert response.status_code == 200 and response.json()["status"] == "retired"
    # A retired ID is answered as unregistered on the device path.
    assert api.device_post("update-device", update_payload()).json()["code"] == "DEVICE_NOT_REGISTERED"
    assert api.post(RETIRE).status_code == 200  # idempotent, body optional


def test_two_phase_retire_waits_for_the_empty_schedule(api: Api) -> None:

    _serve_a_schedule(api)
    api.post(f"/devices/{DEVICE_ID}/dispense")

    pending = api.post(RETIRE, {})
    assert pending.status_code == 202
    body = pending.json()
    assert body["status"] == "active" and body["retire_requested_at"] is not None
    assert "retire" in {p["kind"] for p in body["pending"]}
    assert api.post(RETIRE, {}).status_code == 202  # still waiting; the request time is kept
    assert api.get(f"/devices/{DEVICE_ID}").json()["retire_requested_at"] == body["retire_requested_at"]

    # Phase 2: the next sync asks for the schedule, which is served empty and completes the retire.
    assert api.device_post("update-device", update_payload()).json()["data"]["isScheduleSynced"] is False
    assert api.device_post("get-schedule").json() == {"data": []}
    detail = api.get(f"/devices/{DEVICE_ID}").json()
    assert detail["status"] == "retired" and detail["pending"] == []
    assert detail["remote_dispense"]["pending"] is None  # a retired device never gets a queued dispense


def test_force_retires_without_waiting(api: Api) -> None:
    _serve_a_schedule(api)
    assert api.post(RETIRE, {}).status_code == 202
    forced = api.post(RETIRE, {"force": True})
    assert forced.status_code == 200 and forced.json()["status"] == "retired"


def test_retire_validation(api: Api) -> None:
    assert api.post(RETIRE, {"force": "soon"}).status_code == 422
    assert api.post(RETIRE, {"now": True}).status_code == 422
    assert api.post("/devices/NOPE/retire", {}).status_code == 404

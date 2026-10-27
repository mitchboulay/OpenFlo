from __future__ import annotations

from conftest import DEVICE_ID, update_payload

from .conftest import Api

HISTORY = f"/devices/{DEVICE_ID}/history"


def test_dispenses_page_with_a_cursor(api: Api) -> None:
    batch = [{"status": 0, "code": 1 if n % 2 else 3, "timestamp": 1_900_000_000 + n} for n in range(5)]
    api.device_post("send-events", {"data": batch})
    first = api.get(HISTORY, params={"kind": "dispenses", "limit": 3}).json()
    assert first["kind"] == "dispenses" and len(first["items"]) == 3
    assert first["next_before_id"] == first["items"][-1]["id"]
    rest = api.get(HISTORY, params={"kind": "dispenses", "limit": 3, "before_id": first["next_before_id"]}).json()
    assert len(rest["items"]) == 2 and rest["next_before_id"] is None
    timestamps = [i["device_timestamp"] for i in first["items"] + rest["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    assert {i["dose_count"] for i in first["items"] + rest["items"]} == {1, 2}  # SE 3 is a double dose


def test_events_and_syncs(api: Api) -> None:
    api.device_post("update-device", update_payload())
    api.device_post("send-events", {"data": [{"status": 1, "code": 5, "timestamp": 1_900_000_000}]})
    events = api.get(HISTORY, params={"kind": "events"}).json()["items"]
    assert events[0]["kind"] == "send-events" and events[0]["payload"]["data"][0]["code"] == 5
    syncs = api.get(HISTORY, params={"kind": "syncs"}).json()["items"]
    assert len(syncs) == 1 and syncs[0]["request_count"] == 2 and syncs[0]["source_ip"] == "testclient"


def test_history_validation(api: Api) -> None:
    assert api.get(HISTORY, params={"kind": "logs"}).status_code == 422
    assert api.get(HISTORY).status_code == 422
    assert api.get(HISTORY, params={"kind": "syncs", "limit": 0}).status_code == 422
    assert api.get(HISTORY, params={"kind": "syncs", "limit": 501}).status_code == 422
    assert api.get("/devices/NOPE/history", params={"kind": "syncs"}).status_code == 404
    empty = api.get(HISTORY, params={"kind": "syncs"}).json()
    assert empty == {"kind": "syncs", "items": [], "next_before_id": None}

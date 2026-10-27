from __future__ import annotations

from conftest import DEVICE_ID

from .conftest import Api


def test_create_defaults_timezone_and_rejects_duplicates_case_insensitively(api: Api) -> None:
    created = api.post("/homes", {"name": " Cabin "})
    assert created.status_code == 201
    assert created.json()["name"] == "Cabin" and created.json()["timezone"] == "UTC"
    clash = api.post("/homes", {"name": "CABIN", "timezone": "Europe/Paris"})
    assert clash.status_code == 409 and clash.json()["code"] == "HOME_EXISTS"


def test_timezone_must_be_iana(api: Api) -> None:
    response = api.post("/homes", {"name": "Lake", "timezone": "Mars/Olympus"})
    assert response.status_code == 422 and response.json()["code"] == "TIMEZONE_INVALID"
    assert api.post("/homes", {"name": "Lake", "timezone": "America/New_York"}).status_code == 201


def test_name_bounds(api: Api) -> None:
    assert api.post("/homes", {"name": ""}).status_code == 422
    assert api.post("/homes", {"name": "x" * 61}).status_code == 422


def test_list_summaries(api: Api) -> None:
    api.post("/homes", {"name": "Empty"})
    by_name = {h["name"]: h for h in api.get("/homes").json()}
    assert by_name["Empty"]["summary"] == "empty" and by_name["Empty"]["device_count"] == 0
    assert by_name["Home"]["device_count"] == 1 and by_name["Home"]["summary"] == "ok"

    api.post(f"/devices/{DEVICE_ID}/bottles", {"fill": "set", "fill_ml": 100})  # less than one 177 mL dose
    home = next(h for h in api.get("/homes").json() if h["name"] == "Home")
    assert home["summary"] == "attention" and home["attention_count"] == 1


def test_list_is_paginated(api: Api) -> None:
    for n in range(3):
        api.post("/homes", {"name": f"H{n}"})
    first = api.get("/homes", params={"limit": 2}).json()
    rest = api.get("/homes", params={"limit": 2, "before_id": first[-1]["id"]}).json()
    assert len(first) == 2 and len(rest) == 2
    assert {h["id"] for h in first}.isdisjoint(h["id"] for h in rest)
    assert api.get("/homes", params={"limit": 501}).status_code == 422


def test_rename_and_retime(api: Api) -> None:
    other = api.post("/homes", {"name": "Other"}).json()
    renamed = api.patch(f"/homes/{api.home_id}", {"name": "Main", "timezone": "America/Chicago"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Main" and renamed.json()["timezone"] == "America/Chicago"
    clash = api.patch(f"/homes/{api.home_id}", {"name": "other"})
    assert clash.status_code == 409 and clash.json()["code"] == "HOME_EXISTS"
    assert api.patch(f"/homes/{other['id']}", {"name": "OTHER"}).status_code == 200  # own name, new case
    assert api.patch(f"/homes/{api.home_id}", {"name": None}).status_code == 422
    assert api.patch("/homes/999", {"name": "x"}).json()["code"] == "HOME_NOT_FOUND"


def test_delete_is_blocked_until_devices_are_retired(api: Api) -> None:
    blocked = api.delete(f"/homes/{api.home_id}")
    assert blocked.status_code == 409 and blocked.json()["code"] == "HOME_HAS_DEVICES"
    assert api.post(f"/devices/{DEVICE_ID}/retire", {}).status_code == 200
    assert api.delete(f"/homes/{api.home_id}").status_code == 204
    assert api.get(f"/devices/{DEVICE_ID}").json()["home_id"] is None
    assert api.delete(f"/homes/{api.home_id}").status_code == 404


def test_home_devices(api: Api) -> None:
    devices = api.get(f"/homes/{api.home_id}/devices").json()
    assert [d["device_id"] for d in devices] == [DEVICE_ID]
    summary = devices[0]
    assert summary["name"] == "Kitchen" and summary["status"] == "active"
    assert summary["bottle_guidance"] == "unknown" and summary["flagged"] is False
    assert summary["next_dose_at"] is None and summary["pending_count"] == 0
    assert api.get("/homes/999/devices").status_code == 404

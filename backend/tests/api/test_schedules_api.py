"""Schedule rule endpoints (FR-9, API Specification): CRUD, validation and the upcoming list."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import DEVICE_ID

from .conftest import Api

RULES = f"/devices/{DEVICE_ID}/schedule/rules"
SCHEDULE = f"/devices/{DEVICE_ID}/schedule"


def _at(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def test_create_list_update_delete(api: Api) -> None:
    created = api.post(RULES, {"kind": "weekly", "local_time": "09:00", "days_mask": 0b1000001, "dose_count": 2})
    assert created.status_code == 201
    rule = created.json()
    assert rule["summary"] == "Every Mon, Sun at 09:00 · double dose" and rule["at"] is None

    at = _at(3)
    once = api.post(RULES, {"kind": "once", "at": at}).json()
    assert once["at"] == at and once["summary"].startswith("Once on ")

    view = api.get(SCHEDULE).json()
    assert [r["id"] for r in view["rules"]] == [rule["id"], once["id"]]
    [once_entry] = [e for e in view["upcoming"] if e["rule_ids"] == [once["id"]]]
    assert (once_entry["at"], once_entry["status"], once_entry["reason"]) == (at, "pending", None)
    assert any(e["rule_ids"] == [rule["id"]] and e["dose_count"] == 2 for e in view["upcoming"])

    disabled = api.patch(f"/schedule/rules/{rule['id']}", {"enabled": False}).json()
    assert disabled["enabled"] is False
    assert [e["rule_ids"] for e in api.get(SCHEDULE).json()["upcoming"]] == [[once["id"]]]

    switched = api.patch(f"/schedule/rules/{once['id']}", {"kind": "daily", "local_time": "07:15"}).json()
    assert (switched["kind"], switched["at"], switched["summary"]) == ("daily", None, "Every day at 07:15")

    assert api.delete(f"/schedule/rules/{rule['id']}").status_code == 204
    assert [r["id"] for r in api.get(SCHEDULE).json()["rules"]] == [once["id"]]
    assert api.delete(f"/schedule/rules/{rule['id']}").status_code == 404


def test_interval_rule_anchors_at_now_by_default(api: Api) -> None:
    rule = api.post(RULES, {"kind": "interval", "interval_hours": 6}).json()
    assert rule["summary"] == "Every 6 hours" and rule["at"] is not None
    upcoming = api.get(SCHEDULE).json()["upcoming"]
    gaps = {datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"]) for a, b in zip(upcoming, upcoming[1:])}
    assert gaps == {timedelta(hours=6)}


def test_validation(api: Api) -> None:
    invalid = [
        {"kind": "daily"},
        {"kind": "daily", "local_time": "09:00", "days_mask": 3},
        {"kind": "weekly", "local_time": "09:00"},
        {"kind": "once", "at": _at(-1)},
        {"kind": "once"},
    ]
    for body in invalid:
        response = api.post(RULES, body)
        assert (response.status_code, response.json()["code"]) == (422, "SCHEDULE_INVALID"), body
    for body in ({"kind": "daily", "local_time": "24:00"}, {"kind": "interval", "interval_hours": 5},
                 {"kind": "weekly", "local_time": "09:00", "days_mask": 128}, {"kind": "once", "dose_count": 3}):
        assert api.post(RULES, body).json()["code"] == "INVALID_REQUEST", body
    assert api.post("/devices/NOPE/schedule/rules", {"kind": "daily", "local_time": "09:00"}).status_code == 404
    assert api.patch("/schedule/rules/999", {"enabled": False}).status_code == 404

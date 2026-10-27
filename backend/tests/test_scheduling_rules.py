"""B3.1 schedules (FR-9, AD-6): expansion, the 33 cap, serving, sync hash, fired/missed, pause and re-serve."""
from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import devices, homes, schedules
from app.repositories.schedules import ScheduleRule
from app.services import device_lifecycle, homes as home_service, schedule_rules, scheduling
from app.services.schedule_expansion import MAX_ENTRIES, MIN_HORIZON_S, horizon_seconds, plan
from conftest import DEVICE_ID, mark_setup_ready, update_payload

NY = ZoneInfo("America/New_York")
HEADERS = {"x-device-id": DEVICE_ID}
DAY = 86_400


def _epoch(*args: int, tz: ZoneInfo | timezone = timezone.utc) -> int:
    return int(datetime(*args, tzinfo=tz).timestamp())


def _rule(kind: str, rule_id: int = 1, dose_count: int = 1, **shape: Any) -> ScheduleRule:
    fields = {"local_time": None, "days_mask": None, "interval_hours": None, "at_epoch": None, **shape}
    return ScheduleRule(rule_id, DEVICE_ID, kind, fields["local_time"], fields["days_mask"], fields["interval_hours"],
                        fields["at_epoch"], dose_count, True, "t0", "test")


class Env:
    """An active, registered device in home "Home" (UTC), with dispensing and schedules on (shift 600 s)."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.app: Any = client.app
        with self.app.state.db.connection() as conn:
            self.home_id = homes.create(conn, "Home", "UTC", "test").id
            devices.create(conn, DEVICE_ID, "active", registered=True, home_id=self.home_id, name="Kitchen")
        self.controls(dispensing_enabled=True, schedules_enabled=True, shift_time_seconds=600,
                      sync_interval_seconds=3600)

    def controls(self, **changes: Any) -> None:
        self.app.state.repo.update_controls(DEVICE_ID, changes)

    def add(self, **fields: Any) -> int:
        with self.app.state.db.connection() as conn:
            return schedule_rules.create_rule(conn, DEVICE_ID, fields, "test").rule.id

    def entries(self, after: int = 0) -> list[schedules.ScheduleEntry]:
        with self.app.state.db.connection() as conn:
            return schedules.entries_after(conn, DEVICE_ID, after)

    def synced(self) -> bool:
        return self.client.post("/device-api/v2/update-device", json=update_payload(), headers=HEADERS).json()[
            "data"]["isScheduleSynced"]

    def fetch(self) -> list[dict[str, int]]:
        response = self.client.post("/device-api/v2/get-schedule", headers=HEADERS)
        assert response.status_code == 200
        return response.json()["data"]

    def events(self, *items: tuple[int, int, int]) -> None:
        body = {"data": [{"status": s, "code": c, "timestamp": ts} for s, c, ts in items]}
        assert self.client.post("/device-api/v2/send-events", json=body, headers=HEADERS).status_code == 200


@pytest.fixture
def env(tmp_path: Any) -> Iterator[Env]:
    app = mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "s.db"), auth_mode="none")))
    with TestClient(app) as client:
        yield Env(client)


# -- expansion (pure) ------------------------------------------------------------------------------------------

def _local(entries: list[int]) -> list[str]:
    return [datetime.fromtimestamp(ts, NY).strftime("%m-%d %H:%M %Z") for ts in entries]


def test_daily_0230_across_dst_spring_forward_in_new_york() -> None:
    now = _epoch(2026, 3, 6, 12, 0)
    got = [p.timestamp for p in plan([_rule("daily", local_time="02:30")], NY, now, 3600)][:4]
    # 02:30 does not exist on 03-08: it lands at 03:30 EDT (the pre-transition offset), still once that day.
    assert _local(got) == ["03-07 02:30 EST", "03-08 03:30 EDT", "03-09 02:30 EDT", "03-10 02:30 EDT"]
    assert got[1] == _epoch(2026, 3, 8, 7, 30) and got[2] == _epoch(2026, 3, 9, 6, 30)


def test_daily_0230_across_dst_fall_back_in_new_york() -> None:
    now = _epoch(2026, 10, 30, 12, 0)
    got = [p.timestamp for p in plan([_rule("daily", local_time="02:30")], NY, now, 3600)][:3]
    assert _local(got) == ["10-31 02:30 EDT", "11-01 02:30 EST", "11-02 02:30 EST"]
    assert [b - a for a, b in zip(got, got[1:])] == [25 * 3600, DAY]  # the fall-back day is 25 h long


def test_ambiguous_fall_back_time_is_served_once() -> None:
    now = _epoch(2026, 10, 31, 12, 0)
    got = [p.timestamp for p in plan([_rule("daily", local_time="01:30")], NY, now, 3600)][:2]
    assert _local(got) == ["11-01 01:30 EDT", "11-02 01:30 EST"]


def test_cap_is_33_entries() -> None:
    every_six_hours = _rule("interval", interval_hours=6, at_epoch=0)
    assert len(plan([every_six_hours], NY, 1_800_000_000, 3600)) == MAX_ENTRIES == 33
    many = [_rule("daily", rule_id=i, local_time=f"{i:02d}:00") for i in range(10)]
    planned = plan(many, NY, 1_800_000_000, 3600)
    assert len(planned) == 33 and [p.timestamp for p in planned] == sorted(p.timestamp for p in planned)


def test_horizon_vs_the_48_hour_interval() -> None:
    # The firmware default (48 h) gives 3 x 48 h = 6 d, so the 14-day floor wins; a longer interval extends it.
    assert horizon_seconds(None) == horizon_seconds(172_800) == MIN_HORIZON_S == 14 * DAY
    assert horizon_seconds(6 * DAY) == 18 * DAY
    now = _epoch(2026, 6, 1, 0, 0)
    daily = plan([_rule("daily", local_time="09:00")], ZoneInfo("UTC"), now, 172_800)
    assert len(daily) == 14 and daily[-1].timestamp <= now + 14 * DAY


def test_same_timestamp_rules_merge_with_max_dose_and_both_links() -> None:
    now = _epoch(2026, 6, 1, 0, 0)
    single = _rule("daily", rule_id=1, local_time="09:00")
    double_monday = _rule("weekly", rule_id=2, dose_count=2, local_time="09:00", days_mask=0b1)
    planned = {p.timestamp: p for p in plan([single, double_monday], ZoneInfo("UTC"), now, 3600)}
    monday = planned[_epoch(2026, 6, 1, 9, 0)]  # 2026-06-01 is a Monday
    assert (monday.dose_count, monday.rule_ids) == (2, (1, 2))
    assert (planned[_epoch(2026, 6, 2, 9, 0)].dose_count, planned[_epoch(2026, 6, 2, 9, 0)].rule_ids) == (1, (1,))


def test_merge_is_stored_with_both_rule_links(env: Env) -> None:
    at = int(time.time()) + DAY
    first, second = env.add(kind="once", at_epoch=at), env.add(kind="once", at_epoch=at, dose_count=2)
    [entry] = env.entries()
    with env.app.state.db.connection() as conn:
        links = schedules.rule_ids_by_entry(conn, [entry.id])
    assert (entry.timestamp, entry.dose_count, links[entry.id]) == (at, 2, [first, second])


# -- device path -----------------------------------------------------------------------------------------------

def test_hash_flips_on_change_and_serve_marks_entries_served(env: Env) -> None:
    at = int(time.time()) + DAY
    assert env.synced() is False  # never served
    assert env.fetch() == []
    assert env.synced() is True

    env.add(kind="once", at_epoch=at, dose_count=2)
    assert env.synced() is False
    assert env.fetch() == [{"timestamp": at, "doseCount": 2, "cmd": 0}]
    assert [e.status for e in env.entries()] == ["served"]
    assert env.synced() is True
    assert env.synced() is True  # stable while nothing changes


def test_too_soon_entries_are_cleared_at_serve_time(env: Env) -> None:
    now = int(time.time())
    soon, later = now + 900, now + 3 * 3600  # shift 600 s: anything before now + 1200 s is too soon
    env.add(kind="once", at_epoch=soon)
    env.add(kind="once", at_epoch=later)
    assert env.fetch() == [{"timestamp": later, "doseCount": 1, "cmd": 0}]
    by_ts = {e.timestamp: e for e in env.entries()}
    assert (by_ts[soon].status, by_ts[soon].reason) == ("cleared", "too_soon")
    assert by_ts[later].status == "served"
    assert env.synced() is True


def test_fired_and_missed_are_decided_only_after_a_send_events_ingest(env: Env) -> None:
    now = int(time.time())
    a, b = now + 2 * 3600, now + 4 * 3600
    env.add(kind="once", at_epoch=a)
    env.add(kind="once", at_epoch=b)
    env.fetch()
    with env.app.state.db.connection() as conn:
        # Both doses are past; an update-device alone decides nothing.
        scheduling.sync_on_update(conn, DEVICE_ID, now=b + DAY)
        assert [e.status for e in schedules.entries_after(conn, DEVICE_ID, 0)] == ["served", "served"]
        # The ingest reports SE 1 for the first dose (100 s late, inside the fire window); the second is missed.
        scheduling.record_fired(conn, DEVICE_ID, a + 100, "t")
        scheduling.after_ingest(conn, DEVICE_ID, now=b + DAY)
        assert [(e.status, e.fired_at) for e in schedules.entries_after(conn, DEVICE_ID, 0)] == [
            ("fired", "t"), ("missed", None)]


def test_send_events_se3_fires_the_served_entry(env: Env) -> None:
    at = int(time.time()) + DAY
    env.add(kind="once", at_epoch=at, dose_count=2)
    env.fetch()
    env.events((0, 3, at + 30))
    [entry] = env.entries()
    assert entry.status == "fired" and entry.fired_at is not None


def test_home_timezone_change_re_expands(env: Env) -> None:
    env.add(kind="daily", local_time="09:00")
    env.fetch()
    before = env.entries()
    assert all(datetime.fromtimestamp(e.timestamp, timezone.utc).hour == 9 for e in before)
    with env.app.state.db.connection() as conn:
        home_service.update_home(conn, env.home_id, {"timezone": "America/New_York"}, "test")
    after = env.entries()
    assert after and all(datetime.fromtimestamp(e.timestamp, NY).strftime("%H:%M") == "09:00" for e in after)
    assert {e.status for e in after} == {"pending"}
    assert env.synced() is False


def test_device_home_change_re_expands(env: Env) -> None:
    env.add(kind="daily", local_time="09:00")
    with env.app.state.db.connection() as conn:
        tokyo = homes.create(conn, "Tokyo", "Asia/Tokyo", "test").id
        device_lifecycle.update_device(conn, DEVICE_ID, {"home_id": tokyo}, "test")
    tz = ZoneInfo("Asia/Tokyo")
    assert all(datetime.fromtimestamp(e.timestamp, tz).strftime("%H:%M") == "09:00" for e in env.entries())


@pytest.mark.parametrize("pause", [{"schedules_enabled": False}, {"dispensing_enabled": False}])
def test_pause_serves_empty_and_resumes(env: Env, pause: dict[str, bool]) -> None:
    at = int(time.time()) + DAY
    env.add(kind="once", at_epoch=at)
    assert len(env.fetch()) == 1 and env.synced() is True

    env.controls(**pause)
    assert env.synced() is False
    assert env.fetch() == []
    assert [e.status for e in env.entries()] == ["pending"]  # no longer on the device
    assert env.synced() is True

    env.controls(schedules_enabled=True, dispensing_enabled=True)
    assert env.synced() is False
    assert env.fetch() == [{"timestamp": at, "doseCount": 1, "cmd": 0}]


@pytest.mark.parametrize("code", [5, 6, 7])
def test_bottle_events_re_serve_the_schedule(env: Env, code: int) -> None:
    at = int(time.time()) + DAY
    env.add(kind="once", at_epoch=at)
    env.fetch()
    assert env.synced() is True
    env.events((1, code, int(time.time())))
    assert env.synced() is False
    assert env.fetch() == [{"timestamp": at, "doseCount": 1, "cmd": 0}]
    assert env.synced() is True


def test_next_dose_and_pre_wake_feed_sync_honesty(env: Env) -> None:
    env.controls(sync_interval_seconds=21_600)  # timer wake 6 h after the last sync
    at = int(time.time()) + 2 * 3600
    env.add(kind="once", at_epoch=at)
    env.synced()  # records a sync, so a next expected sync exists
    detail = env.client.get(f"/api/v1/devices/{DEVICE_ID}").json()
    assert "schedule" in {p["kind"] for p in detail["pending"]}
    env.fetch()
    detail = env.client.get(f"/api/v1/devices/{DEVICE_ID}").json()
    assert "schedule" not in {p["kind"] for p in detail["pending"]}
    # The dose pre-wakes the device 2 x shift-time (1200 s) early, well before the 6 h timer wake (FR-14).
    assert detail["next_expected_sync"] == datetime.fromtimestamp(at - 1200, timezone.utc).isoformat()
    summary = env.client.get(f"/api/v1/homes/{env.home_id}/devices").json()[0]
    assert summary["next_dose_at"] == datetime.fromtimestamp(at, timezone.utc).isoformat()
    assert detail["next_dose_at"] == summary["next_dose_at"]  # the device header's "Next dose …"

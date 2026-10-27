"""Schedules on the device path (FR-9, FR-14, AD-6): expansion into entries, serving, and fired/missed.

Entry lifecycle: ``pending`` (not on the device) -> ``served`` (in the last get-schedule) -> ``fired`` (matched
SE 1/3) or ``missed`` (decided after a send-events ingest). A pending entry the device can no longer receive in
time is ``cleared`` (``too_soon``, or ``paused`` when it passed while schedules were withheld).

What the device should hold is a pure function of the entries and the controls; its hash against the hash of
what was last served drives ``isScheduleSynced``, so no change has to remember to flip a flag.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Final
from zoneinfo import ZoneInfo

from ..persistence.repository import utcnow
from ..repositories import devices, homes
from ..repositories._rows import MAX_LIMIT
from ..repositories import schedules as repo
from ..repositories.schedules import ScheduleEntry
from . import device_policy
from .schedule_expansion import EMPTY_HASH, MAX_ENTRIES, PlannedEntry, plan, schedule_hash

logger = logging.getLogger(__name__)

SERVABLE: Final = ("pending", "served")
# ponytail: the factory shift-time is unknown (>= 1950 s on the lab unit, AD-7); assumed when none was sent.
UNKNOWN_SHIFT_S: Final = 1950
# The firmware widens its fire window to 200 s on external power (FUN_40098a94); match SE events at least that far.
EXT_POWER_WINDOW_S: Final = 200


def now_epoch() -> int:
    return int(time.time())


@dataclass(frozen=True, slots=True)
class ScheduleContext:
    device_id: str
    tz: ZoneInfo
    shift_s: int
    sync_interval_s: int | None
    blocked: bool  # paused (lock or switch), retiring, inactive or flagged: serve []


def context(conn: sqlite3.Connection, device_id: str) -> ScheduleContext:
    device = devices.get(conn, device_id)
    assert device is not None
    home = homes.get(conn, device.home_id) if device.home_id is not None else None
    ctl = repo.controls(conn, device_id)
    blocked = (not (ctl.dispensing_enabled and ctl.schedules_enabled) or device.retire_requested_at is not None
               or not device_policy.may_receive_commands(conn, device_id))
    return ScheduleContext(device_id, ZoneInfo(home.timezone if home else "UTC"),
                           ctl.shift_time_seconds or UNKNOWN_SHIFT_S, ctl.sync_interval_seconds, blocked)


def _upsert(conn: sqlite3.Connection, device_id: str, entry: ScheduleEntry | None, planned: PlannedEntry) -> None:
    if entry is None:
        entry_id = repo.insert_entry(conn, device_id, planned.timestamp, planned.dose_count)
    else:
        entry_id = entry.id
        if entry.status in SERVABLE and entry.dose_count != planned.dose_count:
            # The device holds the old count: back to pending so the hash differs and it is re-served.
            repo.update_entry(conn, entry_id, {"dose_count": planned.dose_count, "status": "pending"})
    repo.link_rules(conn, entry_id, planned.rule_ids)


def _clear_undelivered(conn: sqlite3.Connection, ctx: ScheduleContext, before_ts: int) -> None:
    """Pending entries due before ``before_ts`` can no longer be delivered in time."""
    ids = repo.entries_before(conn, ctx.device_id, "pending", before_ts)
    if ids:
        repo.set_status(conn, ids, "cleared", "paused" if ctx.blocked else "too_soon")


def expand(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> None:
    """Recompute the device's future entries from its rules (AD-6); fired/missed history is never touched."""
    now = now_epoch() if now is None else now
    ctx = context(conn, device_id)
    planned = plan(repo.list_rules(conn, device_id), ctx.tz, now, ctx.sync_interval_s)
    existing = {entry.timestamp: entry for entry in repo.entries_after(conn, device_id, now)}
    for item in planned:
        _upsert(conn, device_id, existing.pop(item.timestamp, None), item)
    stale = [entry.id for entry in existing.values() if entry.status not in ("fired", "missed")]
    repo.delete_entries(conn, stale)
    _clear_undelivered(conn, ctx, now + 1)


def expand_home(conn: sqlite3.Connection, home_id: int, now: int | None = None) -> None:
    """Re-expand every non-retired device of a home (its timezone changed)."""
    before: str | None = None
    while True:
        page = devices.list_by_home(conn, home_id, limit=MAX_LIMIT, before_id=before)
        for device in page:
            expand(conn, device.device_id, now)
        if len(page) < MAX_LIMIT:
            return
        before = page[-1].device_id


def desired(conn: sqlite3.Connection, ctx: ScheduleContext, now: int) -> list[ScheduleEntry]:
    """What the device should hold: served entries still in their fire window, plus pending ones far enough out."""
    if ctx.blocked:
        return []
    rows = repo.entries_after(conn, ctx.device_id, now - ctx.shift_s, SERVABLE)
    keep = [e for e in rows if e.status == "served" or e.timestamp >= now + 2 * ctx.shift_s]
    return keep[:MAX_ENTRIES]


def _hash(entries: list[ScheduleEntry]) -> str:
    return schedule_hash((e.timestamp, e.dose_count) for e in entries)


def is_synced(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> bool:
    now = now_epoch() if now is None else now
    ctx = context(conn, device_id)
    return repo.served_state(conn, device_id).schedule_hash == _hash(desired(conn, ctx, now))


def sync_on_update(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> bool:
    """update-device: re-expand (the horizon slides), then ``isScheduleSynced``."""
    now = now_epoch() if now is None else now
    expand(conn, device_id, now)
    return is_synced(conn, device_id, now)


def serve(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> list[dict[str, int]]:
    """get-schedule: the items to send (``cmd`` always 0), marking them served and recording their hash."""
    now = now_epoch() if now is None else now
    ctx = context(conn, device_id)
    if ctx.blocked:
        # The device's schedule is replaced by an empty one: nothing it held is on the device any more.
        held = [e.id for e in repo.entries_after(conn, device_id, now - ctx.shift_s, ("served",))]
        repo.set_status(conn, held, "pending")
        repo.set_served_hash(conn, device_id, EMPTY_HASH)
        return []
    # FR-9 too soon: inside now + 2 x shift-time the device could not pre-wake for it.
    _clear_undelivered(conn, ctx, now + 2 * ctx.shift_s)
    items = desired(conn, ctx, now)
    repo.set_status(conn, [e.id for e in items if e.status == "pending"], "served", served_at=utcnow())
    repo.set_served_hash(conn, device_id, _hash(items))
    logger.info("schedule served device=%s entries=%d", device_id, len(items))
    return [{"timestamp": e.timestamp, "doseCount": e.dose_count, "cmd": 0} for e in items]


def reset_served(conn: sqlite3.Connection, device_id: str) -> None:
    """Bottle EE 5/6/7: forget what was served, so the next update-device re-serves the schedule (AD-6)."""
    repo.set_served_hash(conn, device_id, None)


def record_fired(conn: sqlite3.Connection, device_id: str, device_ts: int, at: str) -> None:
    """SE 1/3: the served (or already missed) entry nearest the event's device time becomes ``fired``."""
    ctx = context(conn, device_id)
    entry = repo.nearest_in_window(conn, device_id, device_ts, max(ctx.shift_s, EXT_POWER_WINDOW_S),
                                   ("served", "missed"))
    if entry is not None:
        repo.update_entry(conn, entry.id, {"status": "fired", "reason": None, "fired_at": at})


def after_ingest(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> None:
    """After a send-events ingest: served entries past ``now - shift-time`` without an SE are ``missed``."""
    now = now_epoch() if now is None else now
    ctx = context(conn, device_id)
    missed = repo.entries_before(conn, device_id, "served", now - ctx.shift_s)
    if missed:
        repo.set_status(conn, missed, "missed")
        logger.info("schedule missed device=%s entries=%d", device_id, len(missed))
    expand(conn, device_id, now)


def has_served_schedule(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> bool:
    """Whether the device may hold a non-empty schedule from us (two-phase retire, FR-2)."""
    now = now_epoch() if now is None else now
    return bool(repo.entries_after(conn, device_id, now, ("served",), limit=1))


def pending_since(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> str | None:
    """When the device's schedule differs from the one it holds: since it was last served (FR-14); else None.

    A device that was never served and should hold nothing is not waiting for anything.
    """
    now = now_epoch() if now is None else now
    state = repo.served_state(conn, device_id)
    wanted = _hash(desired(conn, context(conn, device_id), now))
    if state.schedule_hash == wanted or (state.schedule_hash is None and wanted == EMPTY_HASH):
        return None
    device = devices.get(conn, device_id)
    assert device is not None
    return state.updated_at or device.first_seen


def next_served(conn: sqlite3.Connection, device_id: str, now: int | None = None) -> ScheduleEntry | None:
    """The earliest future dose on the device."""
    now = now_epoch() if now is None else now
    found = repo.entries_after(conn, device_id, now, ("served",), limit=1)
    return found[0] if found else None

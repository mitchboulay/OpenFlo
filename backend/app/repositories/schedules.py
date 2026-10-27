"""Schedule rules, their expanded entries and the served-schedule hash (AD-6). Times are UTC epoch seconds."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypedDict

from ..persistence.repository import utcnow
from ._rows import MAX_LIMIT, columns, fetch_one, to_row, update_columns

RuleKind = Literal["daily", "weekly", "interval", "once"]
EntryStatus = Literal["pending", "served", "fired", "missed", "cleared"]
ClearReason = Literal["too_soon", "paused"]


@dataclass(frozen=True, slots=True)
class ScheduleRule:
    id: int
    device_id: str
    kind: str
    local_time: str | None
    days_mask: int | None
    interval_hours: int | None
    at_epoch: int | None
    dose_count: int
    enabled: bool
    created_at: str
    actor: str


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    id: int
    device_id: str
    timestamp: int
    dose_count: int
    status: str
    reason: str | None
    served_at: str | None
    fired_at: str | None


class RuleFields(TypedDict, total=False):
    kind: RuleKind
    local_time: str | None
    days_mask: int | None
    interval_hours: int | None
    at_epoch: int | None
    dose_count: int
    enabled: bool


_RULE_COLUMNS = frozenset(RuleFields.__annotations__)
_ENTRY_COLUMNS = frozenset({"dose_count", "status", "reason", "served_at", "fired_at"})
_RULES = f"SELECT {columns(ScheduleRule)} FROM schedule_rules"
_ENTRIES = f"SELECT {columns(ScheduleEntry)} FROM schedule_entries"


# -- rules -----------------------------------------------------------------------------------------------------

def create_rule(conn: sqlite3.Connection, device_id: str, rule: RuleFields, actor: str) -> ScheduleRule:
    cur = conn.execute(
        "INSERT INTO schedule_rules (device_id, kind, local_time, days_mask, interval_hours, at_epoch, dose_count,"
        " enabled, created_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (device_id, rule["kind"], rule.get("local_time"), rule.get("days_mask"), rule.get("interval_hours"),
         rule.get("at_epoch"), rule.get("dose_count", 1), int(rule.get("enabled", True)), utcnow(), actor),
    )
    created = get_rule(conn, int(cur.lastrowid))
    assert created is not None
    return created


def get_rule(conn: sqlite3.Connection, rule_id: int) -> ScheduleRule | None:
    return fetch_one(conn, ScheduleRule, f"{_RULES} WHERE id = ?", (rule_id,))


def list_rules(conn: sqlite3.Connection, device_id: str) -> list[ScheduleRule]:
    """A device's rules, oldest first; the service caps a device at far fewer than ``MAX_LIMIT``."""
    rows = conn.execute(f"{_RULES} WHERE device_id = ? ORDER BY id LIMIT ?", (device_id, MAX_LIMIT))
    return [to_row(ScheduleRule, row) for row in rows]


def update_rule(conn: sqlite3.Connection, rule_id: int, changes: RuleFields) -> ScheduleRule | None:
    values = {k: int(v) if k == "enabled" else v for k, v in changes.items()}
    update_columns(conn, "schedule_rules", "id", rule_id, values, _RULE_COLUMNS)
    return get_rule(conn, rule_id)


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    """Delete a rule; entries it produced keep their other links (fired/missed history survives)."""
    conn.execute("DELETE FROM schedule_entry_rules WHERE rule_id = ?", (rule_id,))
    conn.execute("DELETE FROM schedule_rules WHERE id = ?", (rule_id,))


# -- entries ---------------------------------------------------------------------------------------------------

def entries_after(conn: sqlite3.Connection, device_id: str, after_ts: int,
                  statuses: Iterable[EntryStatus] | None = None, limit: int = MAX_LIMIT) -> list[ScheduleEntry]:
    """Entries with ``timestamp > after_ts`` (optionally in ``statuses``), earliest first."""
    sql, params = f"{_ENTRIES} WHERE device_id = ? AND timestamp > ?", [device_id, after_ts]
    if statuses is not None:
        wanted = list(statuses)
        sql += f" AND status IN ({', '.join('?' for _ in wanted)})"
        params += wanted
    rows = conn.execute(f"{sql} ORDER BY timestamp LIMIT ?", (*params, limit))
    return [to_row(ScheduleEntry, row) for row in rows]


def insert_entry(conn: sqlite3.Connection, device_id: str, timestamp: int, dose_count: int) -> int:
    cur = conn.execute(
        "INSERT INTO schedule_entries (device_id, timestamp, dose_count, status) VALUES (?, ?, ?, 'pending')",
        (device_id, timestamp, dose_count),
    )
    return int(cur.lastrowid)


def update_entry(conn: sqlite3.Connection, entry_id: int, changes: dict[str, object]) -> None:
    update_columns(conn, "schedule_entries", "id", entry_id, changes, _ENTRY_COLUMNS)


def set_status(conn: sqlite3.Connection, entry_ids: list[int], status: EntryStatus,
               reason: ClearReason | None = None, served_at: str | None = None) -> None:
    conn.executemany(
        "UPDATE schedule_entries SET status = ?, reason = ?, served_at = coalesce(?, served_at) WHERE id = ?",
        [(status, reason, served_at, entry_id) for entry_id in entry_ids],
    )


def delete_entries(conn: sqlite3.Connection, entry_ids: list[int]) -> None:
    conn.executemany("DELETE FROM schedule_entry_rules WHERE entry_id = ?", [(i,) for i in entry_ids])
    conn.executemany("DELETE FROM schedule_entries WHERE id = ?", [(i,) for i in entry_ids])


def link_rules(conn: sqlite3.Connection, entry_id: int, rule_ids: Iterable[int]) -> None:
    """Replace the entry's rule links (a merged entry links every rule that produced it)."""
    conn.execute("DELETE FROM schedule_entry_rules WHERE entry_id = ?", (entry_id,))
    conn.executemany("INSERT INTO schedule_entry_rules (entry_id, rule_id) VALUES (?, ?)",
                     [(entry_id, rule_id) for rule_id in rule_ids])


def rule_ids_by_entry(conn: sqlite3.Connection, entry_ids: list[int]) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {entry_id: [] for entry_id in entry_ids}
    if not entry_ids:
        return found
    rows = conn.execute(
        f"SELECT entry_id, rule_id FROM schedule_entry_rules WHERE entry_id IN ({', '.join('?' for _ in entry_ids)})"
        " ORDER BY rule_id", entry_ids,
    )
    for entry_id, rule_id in rows:
        found[entry_id].append(rule_id)
    return found


def entries_before(conn: sqlite3.Connection, device_id: str, status: EntryStatus, before_ts: int) -> list[int]:
    """IDs of ``status`` entries with ``timestamp < before_ts`` (``schedule_entries_due``)."""
    rows = conn.execute(
        "SELECT id FROM schedule_entries WHERE device_id = ? AND status = ? AND timestamp < ? LIMIT ?",
        (device_id, status, before_ts, MAX_LIMIT),
    )
    return [row[0] for row in rows]


def nearest_in_window(conn: sqlite3.Connection, device_id: str, at: int, window: int,
                      statuses: tuple[EntryStatus, ...]) -> ScheduleEntry | None:
    """The entry in ``statuses`` closest to device time ``at`` within ``± window`` seconds."""
    marks = ", ".join("?" for _ in statuses)
    return fetch_one(
        conn, ScheduleEntry,
        f"{_ENTRIES} WHERE device_id = ? AND status IN ({marks}) AND timestamp BETWEEN ? AND ?"
        " ORDER BY abs(timestamp - ?) LIMIT 1",
        (device_id, *statuses, at - window, at + window, at),
    )


@dataclass(frozen=True, slots=True)
class ScheduleControls:
    """The ``device_controls`` columns scheduling reads, on the caller's connection (defaults when no row)."""
    dispensing_enabled: bool
    schedules_enabled: bool
    sync_interval_seconds: int | None
    shift_time_seconds: int | None


def controls(conn: sqlite3.Connection, device_id: str) -> ScheduleControls:
    row = conn.execute(
        "SELECT dispensing_enabled, schedules_enabled, sync_interval_seconds, shift_time_seconds"
        " FROM device_controls WHERE device_id = ?", (device_id,),
    ).fetchone()
    if row is None:
        return ScheduleControls(False, False, None, None)
    return ScheduleControls(bool(row[0]), bool(row[1]), row[2], row[3])


# -- served hash (sync_state.schedule_hash) --------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ServedState:
    schedule_hash: str | None
    updated_at: str | None


def served_state(conn: sqlite3.Connection, device_id: str) -> ServedState:
    row = conn.execute("SELECT schedule_hash, updated_at FROM sync_state WHERE device_id = ?", (device_id,)).fetchone()
    return ServedState(row[0], row[1]) if row else ServedState(None, None)


def set_served_hash(conn: sqlite3.Connection, device_id: str, schedule_hash: str | None) -> None:
    conn.execute(
        "INSERT INTO sync_state (device_id, schedule_hash, updated_at) VALUES (?, ?, ?)"
        " ON CONFLICT(device_id) DO UPDATE SET schedule_hash = excluded.schedule_hash, updated_at = excluded.updated_at",
        (device_id, schedule_hash, utcnow()),
    )

"""Device syncs: one row per wake session, derived from device-API requests (AD-3)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page


@dataclass(frozen=True, slots=True)
class DeviceSync:
    id: int
    device_id: str
    started_at: str
    ended_at: str
    request_count: int
    source_ip: str


# ponytail: bounds the index range of other_ips_since; a wake session lasts seconds to minutes (120 s gap
# rule), so an hour is a generous ceiling. Raise it if real syncs ever run longer.
MAX_SYNC_SPAN = timedelta(hours=1)

_SELECT = f"SELECT {columns(DeviceSync)} FROM device_syncs"


def latest(conn: sqlite3.Connection, device_id: str) -> DeviceSync | None:
    """The most recent sync (``device_syncs_recent`` index; device path)."""
    return fetch_one(
        conn, DeviceSync, f"{_SELECT} WHERE device_id = ? ORDER BY started_at DESC LIMIT 1", (device_id,)
    )


def start(conn: sqlite3.Connection, device_id: str, at: str, source_ip: str) -> DeviceSync:
    """Open a new sync with its first request at ``at``."""
    cur = conn.execute(
        "INSERT INTO device_syncs (device_id, started_at, ended_at, request_count, source_ip)"
        " VALUES (?, ?, ?, 1, ?)",
        (device_id, at, at, source_ip),
    )
    return DeviceSync(int(cur.lastrowid), device_id, at, at, 1, source_ip)


def extend(conn: sqlite3.Connection, sync_id: int, at: str) -> None:
    """Count one more request in an open sync and move its end to ``at``."""
    conn.execute(
        "UPDATE device_syncs SET ended_at = ?, request_count = request_count + 1 WHERE id = ?", (at, sync_id)
    )


def other_ips_since(conn: sqlite3.Connection, device_id: str, source_ip: str, since: str) -> list[str]:
    """Distinct source IPs other than ``source_ip`` whose sync ended at or after ``since`` (ip_conflict, FR-13)."""
    started_floor = (datetime.fromisoformat(since) - MAX_SYNC_SPAN).isoformat()
    rows = conn.execute(
        "SELECT DISTINCT source_ip FROM device_syncs WHERE device_id = ? AND started_at >= ? AND ended_at >= ?"
        " AND source_ip <> ? ORDER BY source_ip",
        (device_id, started_floor, since, source_ip),
    )
    return [row[0] for row in rows]


def list_recent(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[DeviceSync]:
    return fetch_page(conn, DeviceSync, "device_syncs", "device_id = ?", (device_id,), limit=limit, before=before_id)


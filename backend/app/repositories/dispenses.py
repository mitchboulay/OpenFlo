"""SE-confirmed dispenses with their bottle and estimated volume (AD-5)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page


@dataclass(frozen=True, slots=True)
class Dispense:
    id: int
    device_id: str
    code: int
    device_timestamp: int | None
    received_at: str
    bottle_id: int | None
    est_volume_ml: float | None
    dose_count: int


def insert(
    conn: sqlite3.Connection,
    device_id: str,
    code: int,
    device_timestamp: int | None,
    *,
    bottle_id: int | None,
    est_volume_ml: float | None,
    dose_count: int,
    at: str | None = None,
) -> bool:
    """Record a dispense; False when already recorded (the firmware resends a batch after a failed sync)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO dispenses (device_id, code, device_timestamp, received_at, bottle_id, est_volume_ml,"
        " dose_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (device_id, code, device_timestamp, at or utcnow(), bottle_id, est_volume_ml, dose_count),
    )
    return cur.rowcount == 1


def latest_estimated_since(conn: sqlite3.Connection, device_id: str, since: str) -> Dispense | None:
    """The newest dispense with a volume estimate received at or after ``since`` (``idx_dispenses_device``)."""
    return fetch_one(
        conn,
        Dispense,
        f"SELECT {columns(Dispense)} FROM dispenses WHERE device_id = ? AND est_volume_ml IS NOT NULL"
        " AND received_at >= ? ORDER BY id DESC LIMIT 1",
        (device_id, since),
    )


def total_ml_for_bottle(conn: sqlite3.Connection, device_id: str, bottle_id: int) -> float:
    """Sum of estimated volumes dispensed from a bottle (``idx_dispenses_device`` narrows to the device)."""
    row = conn.execute(
        "SELECT coalesce(sum(est_volume_ml), 0) FROM dispenses WHERE device_id = ? AND bottle_id = ?",
        (device_id, bottle_id),
    ).fetchone()
    return float(row[0])


def list_for_device(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[Dispense]:
    """Confirmed dispenses, newest first (``idx_dispenses_device``)."""
    return fetch_page(conn, Dispense, "dispenses", "device_id = ?", (device_id,), limit=limit, before=before_id)


def first_received_since(conn: sqlite3.Connection, device_id: str, since: str) -> Dispense | None:
    """The earliest dispense received at or after ``since`` (confirms a delivered remote dispense)."""
    return fetch_one(
        conn,
        Dispense,
        f"SELECT {columns(Dispense)} FROM dispenses WHERE device_id = ? AND received_at >= ? ORDER BY id LIMIT 1",
        (device_id, since),
    )

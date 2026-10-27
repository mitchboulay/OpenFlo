"""Bottles (at most one open per device) and manual fill adjustments."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page


@dataclass(frozen=True, slots=True)
class Bottle:
    id: int
    device_id: str
    profile_id: int
    capacity_ml: float
    initial_fill_ml: float | None
    started_at: str
    ended_at: str | None
    end_reason: str | None


@dataclass(frozen=True, slots=True)
class FillAdjustment:
    id: int
    bottle_id: int
    delta_ml: float
    reason: str
    at: str
    actor: str


_SELECT = f"SELECT {columns(Bottle)} FROM bottles"


def get(conn: sqlite3.Connection, bottle_id: int) -> Bottle | None:
    return fetch_one(conn, Bottle, f"{_SELECT} WHERE id = ?", (bottle_id,))


def open_for_device(conn: sqlite3.Connection, device_id: str) -> Bottle | None:
    """The device's open bottle (partial unique index ``bottles_one_open``; device path)."""
    return fetch_one(conn, Bottle, f"{_SELECT} WHERE device_id = ? AND ended_at IS NULL", (device_id,))


def open_bottle(
    conn: sqlite3.Connection,
    device_id: str,
    profile_id: int,
    capacity_ml: float,
    initial_fill_ml: float | None,
    at: str | None = None,
) -> Bottle:
    """Start a bottle; raises ``sqlite3.IntegrityError`` while another is open (close it first)."""
    started_at = at or utcnow()
    cur = conn.execute(
        "INSERT INTO bottles (device_id, profile_id, capacity_ml, initial_fill_ml, started_at) VALUES (?, ?, ?, ?, ?)",
        (device_id, profile_id, capacity_ml, initial_fill_ml, started_at),
    )
    return Bottle(int(cur.lastrowid), device_id, profile_id, capacity_ml, initial_fill_ml, started_at, None, None)


def close_open(conn: sqlite3.Connection, device_id: str, reason: str, at: str | None = None) -> Bottle | None:
    """Close the device's open bottle, returning it closed; None when no bottle was open."""
    current = open_for_device(conn, device_id)
    if current is None:
        return None
    conn.execute(
        "UPDATE bottles SET ended_at = ?, end_reason = ? WHERE id = ? AND ended_at IS NULL",
        (at or utcnow(), reason, current.id),
    )
    return get(conn, current.id)


def set_initial_fill(conn: sqlite3.Connection, bottle_id: int, initial_fill_ml: float) -> Bottle | None:
    """Make an unknown fill level known (the first manual adjustment of a "Set the level" bottle)."""
    conn.execute("UPDATE bottles SET initial_fill_ml = ? WHERE id = ?", (initial_fill_ml, bottle_id))
    return get(conn, bottle_id)


def list_for_device(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[Bottle]:
    return fetch_page(conn, Bottle, "bottles", "device_id = ?", (device_id,), limit=limit, before=before_id)


def add_adjustment(
    conn: sqlite3.Connection, bottle_id: int, delta_ml: float, reason: str, actor: str, at: str | None = None
) -> FillAdjustment:
    adjusted_at = at or utcnow()
    cur = conn.execute(
        "INSERT INTO fill_adjustments (bottle_id, delta_ml, reason, at, actor) VALUES (?, ?, ?, ?, ?)",
        (bottle_id, delta_ml, reason, adjusted_at, actor),
    )
    return FillAdjustment(int(cur.lastrowid), bottle_id, delta_ml, reason, adjusted_at, actor)


def adjustment_total_ml(conn: sqlite3.Connection, bottle_id: int) -> float:
    """Sum of fill adjustments for a bottle (``fill_adjustments_bottle`` index)."""
    row = conn.execute("SELECT coalesce(sum(delta_ml), 0) FROM fill_adjustments WHERE bottle_id = ?", (bottle_id,))
    return float(row.fetchone()[0])


def list_adjustments(
    conn: sqlite3.Connection, bottle_id: int, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[FillAdjustment]:
    return fetch_page(
        conn, FillAdjustment, "fill_adjustments", "bottle_id = ?", (bottle_id,), limit=limit, before=before_id
    )

"""Per-device dosing configuration and the served-open-time history (AD-5)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page


@dataclass(frozen=True, slots=True)
class DeviceDosing:
    device_id: str
    profile_id: int
    dose_ml: float | None
    fixed_tenths: int | None
    compensation_enabled: bool
    flow_scale: float
    updated_at: str
    actor: str


@dataclass(frozen=True, slots=True)
class DoseServing:
    id: int
    device_id: str
    served_at: str
    tenths: int
    flow_ml_s: float


def get(conn: sqlite3.Connection, device_id: str) -> DeviceDosing | None:
    return fetch_one(conn, DeviceDosing, f"SELECT {columns(DeviceDosing)} FROM device_dosing WHERE device_id = ?",
                     (device_id,))


def put(
    conn: sqlite3.Connection,
    device_id: str,
    profile_id: int,
    *,
    dose_ml: float | None,
    fixed_tenths: int | None,
    compensation_enabled: bool = True,
    flow_scale: float = 1.0,
    actor: str,
    at: str | None = None,
) -> DeviceDosing:
    """Insert or replace the device's dosing (exactly one of ``dose_ml``/``fixed_tenths``; CHECK-enforced)."""
    row = DeviceDosing(device_id, profile_id, dose_ml, fixed_tenths, compensation_enabled, flow_scale,
                       at or utcnow(), actor)
    conn.execute(
        "INSERT INTO device_dosing (device_id, profile_id, dose_ml, fixed_tenths, compensation_enabled, flow_scale,"
        " updated_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(device_id) DO UPDATE SET"
        " profile_id = excluded.profile_id, dose_ml = excluded.dose_ml, fixed_tenths = excluded.fixed_tenths,"
        " compensation_enabled = excluded.compensation_enabled, flow_scale = excluded.flow_scale,"
        " updated_at = excluded.updated_at, actor = excluded.actor",
        (device_id, profile_id, dose_ml, fixed_tenths, int(compensation_enabled), flow_scale, row.updated_at, actor),
    )
    return row


def set_flow_scale(
    conn: sqlite3.Connection, device_id: str, flow_scale: float, actor: str, at: str | None = None
) -> DeviceDosing | None:
    """Store a calibrated flow scale (FR-7)."""
    conn.execute(
        "UPDATE device_dosing SET flow_scale = ?, updated_at = ?, actor = ? WHERE device_id = ?",
        (flow_scale, at or utcnow(), actor, device_id),
    )
    return get(conn, device_id)


def record_serving(
    conn: sqlite3.Connection, device_id: str, tenths: int, flow_ml_s: float, at: str | None = None
) -> DoseServing:
    """Record the open time served by a ``get-bottle`` 200."""
    served_at = at or utcnow()
    cur = conn.execute(
        "INSERT INTO dose_servings (device_id, served_at, tenths, flow_ml_s) VALUES (?, ?, ?, ?)",
        (device_id, served_at, tenths, flow_ml_s),
    )
    return DoseServing(int(cur.lastrowid), device_id, served_at, tenths, flow_ml_s)


def latest_serving(
    conn: sqlite3.Connection, device_id: str, at_or_before: str | None = None
) -> DoseServing | None:
    """The newest serving, optionally at or before a time (``dose_servings_recent`` index; device path)."""
    select = f"SELECT {columns(DoseServing)} FROM dose_servings WHERE device_id = ?"
    if at_or_before is None:
        return fetch_one(conn, DoseServing, f"{select} ORDER BY served_at DESC LIMIT 1", (device_id,))
    return fetch_one(
        conn, DoseServing, f"{select} AND served_at <= ? ORDER BY served_at DESC LIMIT 1", (device_id, at_or_before)
    )


def list_servings(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[DoseServing]:
    return fetch_page(conn, DoseServing, "dose_servings", "device_id = ?", (device_id,), limit=limit, before=before_id)

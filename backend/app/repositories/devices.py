"""Device registry rows (identity, home membership, status)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal, TypedDict

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page, update_columns

DeviceStatus = Literal["provisioning", "active", "unclaimed", "retired"]


@dataclass(frozen=True, slots=True)
class Device:
    device_id: str
    first_seen: str
    last_seen: str
    registered: bool
    firmware_version: str | None
    metadata_json: str
    home_id: int | None
    name: str | None
    location: str | None
    installed_at: str | None
    mac: str | None
    last_ip: str | None
    hardware_type: str | None
    pcb_version: str | None
    status: str
    retire_requested_at: str | None


class DeviceUpdate(TypedDict, total=False):
    last_seen: str
    registered: bool
    firmware_version: str | None
    metadata_json: str
    home_id: int | None
    name: str | None
    location: str | None
    installed_at: str | None
    last_ip: str | None
    hardware_type: str | None
    pcb_version: str | None
    status: DeviceStatus
    retire_requested_at: str | None


_SELECT = f"SELECT {columns(Device)} FROM devices"
_UPDATABLE = frozenset(DeviceUpdate.__annotations__)


def get(conn: sqlite3.Connection, device_id: str) -> Device | None:
    """Primary-key lookup (device path)."""
    return fetch_one(conn, Device, f"{_SELECT} WHERE device_id = ?", (device_id,))


def create(
    conn: sqlite3.Connection,
    device_id: str,
    status: DeviceStatus,
    *,
    registered: bool = False,
    home_id: int | None = None,
    name: str | None = None,
    location: str | None = None,
    last_ip: str | None = None,
    at: str | None = None,
) -> Device:
    """Insert a device row; raises ``sqlite3.IntegrityError`` when the ID exists."""
    now = at or utcnow()
    conn.execute(
        "INSERT INTO devices (device_id, first_seen, last_seen, registered, metadata_json, home_id, name,"
        " location, installed_at, last_ip, status) VALUES (?, ?, ?, ?, '{}', ?, ?, ?, ?, ?, ?)",
        (device_id, now, now, int(registered), home_id, name, location,
         now if home_id is not None else None, last_ip, status),
    )
    device = get(conn, device_id)
    assert device is not None
    return device


def update(conn: sqlite3.Connection, device_id: str, changes: DeviceUpdate) -> Device | None:
    update_columns(conn, "devices", "device_id", device_id, changes, _UPDATABLE)
    return get(conn, device_id)


def add_registration(
    conn: sqlite3.Connection, device_id: str, ott_sha256: str, remote_addr: str | None, at: str | None = None
) -> None:
    """Record an accepted registration; the newest row is the device's current token (its fingerprint, FR-3)."""
    conn.execute(
        "INSERT INTO registrations (device_id, ott_sha256, status, remote_addr, created_at)"
        " VALUES (?, ?, 'accepted', ?, ?)",
        (device_id, ott_sha256, remote_addr, at or utcnow()),
    )


def list_by_home(
    conn: sqlite3.Connection,
    home_id: int,
    *,
    include_retired: bool = False,
    limit: int = DEFAULT_LIMIT,
    before_id: str | None = None,
) -> list[Device]:
    """Devices in a home, by descending device ID (``devices_home`` index)."""
    where = "home_id = ?" if include_retired else "home_id = ? AND status <> 'retired'"
    return fetch_page(conn, Device, "devices", where, (home_id,), limit=limit, before=before_id, key="device_id")


def list_by_status(
    conn: sqlite3.Connection,
    status: DeviceStatus,
    *,
    limit: int = DEFAULT_LIMIT,
    before_id: str | None = None,
) -> list[Device]:
    """Devices in one status, by descending device ID (``devices_status`` index)."""
    return fetch_page(conn, Device, "devices", "status = ?", (status,), limit=limit, before=before_id, key="device_id")


def count_by_status(conn: sqlite3.Connection, status: DeviceStatus) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM devices WHERE status = ?", (status,)).fetchone()[0])


def detach_retired(conn: sqlite3.Connection, home_id: int) -> int:
    """Clear the home of its retired devices (they keep their history), so the home can be deleted."""
    cur = conn.execute("UPDATE devices SET home_id = NULL WHERE home_id = ? AND status = 'retired'", (home_id,))
    return cur.rowcount

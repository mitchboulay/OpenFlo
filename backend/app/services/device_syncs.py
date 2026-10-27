"""Sync derivation (AD-3, FR-14): every device-API request belongs to one wake session in ``device_syncs``."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..repositories import devices, syncs
from .device_identity import raise_once

# A request more than SYNC_GAP after the device's previous one starts a new sync.
SYNC_GAP = timedelta(seconds=120)
# A different source IP while another sync is open or ended within this window raises ip_conflict (FR-13).
IP_CONFLICT_WINDOW = timedelta(minutes=10)


def stamp(at: datetime) -> str:
    return at.isoformat(timespec="microseconds")


def record_request(conn: sqlite3.Connection, device_id: str, source_ip: str, at: datetime) -> None:
    """Start or extend the device's sync, update last_seen/last_ip, and flag a second source IP.

    A request from a different IP than the latest sync starts its own sync, so each row has one source.
    """
    now = stamp(at)
    devices.update(conn, device_id, {"last_seen": now, "last_ip": source_ip})
    latest = syncs.latest(conn, device_id)
    if (
        latest is not None
        and latest.source_ip == source_ip
        and at - datetime.fromisoformat(latest.ended_at) <= SYNC_GAP
    ):
        syncs.extend(conn, latest.id, now)
        return
    other_ips = syncs.other_ips_since(conn, device_id, source_ip, stamp(at - IP_CONFLICT_WINDOW))
    if other_ips:
        raise_once(conn, device_id, "ip_conflict", {"source_ip": source_ip, "other_ips": other_ips}, now)
    if latest is not None and latest.started_at == now:
        # UNIQUE(device_id, started_at): a second IP in the same microsecond joins that sync; the flag names it.
        syncs.extend(conn, latest.id, now)
    else:
        syncs.start(conn, device_id, now, source_ip)


def admit_unclaimed(conn: sqlite3.Connection, device_id: str, source_ip: str, at: datetime, cap: int) -> bool:
    """Create an ``unclaimed`` row for an unknown ID while fewer than ``cap`` exist (FR-5); True when created."""
    if devices.count_by_status(conn, "unclaimed") >= cap:
        return False
    devices.create(conn, device_id, "unclaimed", last_ip=source_ip, at=stamp(at))
    return True

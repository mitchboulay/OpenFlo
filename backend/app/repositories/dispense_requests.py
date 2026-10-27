"""Operator-queued remote dispenses: at most one pending per device, delivered exactly once (FR-6)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..persistence.repository import utcnow
from ._rows import columns, fetch_one


@dataclass(frozen=True, slots=True)
class DispenseRequest:
    id: int
    device_id: str
    nonce: int
    requested_at: str
    delivered_at: str | None
    cancelled_at: str | None


_SELECT = f"SELECT {columns(DispenseRequest)} FROM dispense_requests"


def get(conn: sqlite3.Connection, request_id: int) -> DispenseRequest | None:
    return fetch_one(conn, DispenseRequest, f"{_SELECT} WHERE id = ?", (request_id,))


def pending(conn: sqlite3.Connection, device_id: str) -> DispenseRequest | None:
    """The undelivered, uncancelled request (``idx_dispense_requests_pending``)."""
    return fetch_one(
        conn, DispenseRequest,
        f"{_SELECT} WHERE device_id = ? AND delivered_at IS NULL AND cancelled_at IS NULL ORDER BY id LIMIT 1",
        (device_id,),
    )


def last_delivered(conn: sqlite3.Connection, device_id: str) -> DispenseRequest | None:
    return fetch_one(
        conn, DispenseRequest,
        f"{_SELECT} WHERE device_id = ? AND delivered_at IS NOT NULL ORDER BY id DESC LIMIT 1",
        (device_id,),
    )


def queue(conn: sqlite3.Connection, device_id: str, nonce: int) -> DispenseRequest:
    """The pending request, created with ``nonce`` when there is none."""
    existing = pending(conn, device_id)
    if existing is not None:
        return existing
    cur = conn.execute(
        "INSERT INTO dispense_requests (device_id, nonce, requested_at) VALUES (?, ?, ?)",
        (device_id, nonce, utcnow()),
    )
    created = get(conn, int(cur.lastrowid))
    assert created is not None
    return created


def cancel_pending(conn: sqlite3.Connection, device_id: str) -> int:
    """Cancel the pending request; returns how many were cancelled (0 or 1)."""
    return conn.execute(
        "UPDATE dispense_requests SET cancelled_at = ? WHERE device_id = ?"
        " AND delivered_at IS NULL AND cancelled_at IS NULL",
        (utcnow(), device_id),
    ).rowcount

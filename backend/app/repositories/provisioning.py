"""Provisioning sessions, their event log, and pairing sightings (AD-4)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, MAX_LIMIT, columns, fetch_one, fetch_page, to_row, update_columns

SessionKind = Literal["new", "reset"]
SessionStatus = Literal[
    "awaiting_reset", "awaiting_softap", "awaiting_join", "completed", "expired", "failed", "cancelled"
]
_OPEN_SQL = "status IN ('awaiting_reset', 'awaiting_softap', 'awaiting_join')"


@dataclass(frozen=True, slots=True)
class ProvisioningSession:
    id: int
    home_id: int
    kind: str
    target_device_id: str | None
    device_name: str
    location: str | None
    ott_sha256: str
    status: str
    bound_device_id: str | None
    bound_ip: str | None
    reset_requested_at: str | None
    reset_result: str | None
    created_at: str
    expires_at: str
    completed_at: str | None
    actor: str


@dataclass(frozen=True, slots=True)
class ProvisioningEvent:
    id: int
    session_id: int
    at: str
    step: str
    detail_json: str

    @property
    def detail(self) -> dict[str, Any]:
        return json.loads(self.detail_json)


@dataclass(frozen=True, slots=True)
class PairingSighting:
    device_id: str
    source_ip: str
    first_seen: str
    last_seen: str


class SessionUpdate(TypedDict, total=False):
    status: SessionStatus
    bound_device_id: str | None
    bound_ip: str | None
    reset_requested_at: str | None
    reset_result: str | None
    completed_at: str | None


_SELECT = f"SELECT {columns(ProvisioningSession)} FROM provisioning_sessions"
_UPDATABLE = frozenset(SessionUpdate.__annotations__)


def create(
    conn: sqlite3.Connection,
    home_id: int,
    kind: SessionKind,
    device_name: str,
    ott_sha256: str,
    *,
    expires_at: str,
    actor: str,
    target_device_id: str | None = None,
    location: str | None = None,
    status: SessionStatus = "awaiting_softap",
    at: str | None = None,
) -> ProvisioningSession:
    cur = conn.execute(
        "INSERT INTO provisioning_sessions (home_id, kind, target_device_id, device_name, location, ott_sha256,"
        " status, created_at, expires_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (home_id, kind, target_device_id, device_name, location, ott_sha256, status, at or utcnow(),
         expires_at, actor),
    )
    session = get(conn, int(cur.lastrowid))
    assert session is not None
    return session


def get(conn: sqlite3.Connection, session_id: int) -> ProvisioningSession | None:
    return fetch_one(conn, ProvisioningSession, f"{_SELECT} WHERE id = ?", (session_id,))


def get_by_ott(conn: sqlite3.Connection, ott_sha256: str) -> ProvisioningSession | None:
    """Session lookup by token digest (UNIQUE index; device path ``register``)."""
    return fetch_one(conn, ProvisioningSession, f"{_SELECT} WHERE ott_sha256 = ?", (ott_sha256,))


def update(conn: sqlite3.Connection, session_id: int, changes: SessionUpdate) -> ProvisioningSession | None:
    update_columns(conn, "provisioning_sessions", "id", session_id, changes, _UPDATABLE)
    return get(conn, session_id)


def open_for_home(conn: sqlite3.Connection, home_id: int, now: str | None = None) -> ProvisioningSession | None:
    """The home's unexpired open session, if any (``provisioning_open`` index)."""
    return fetch_one(
        conn,
        ProvisioningSession,
        f"{_SELECT} WHERE {_OPEN_SQL} AND expires_at > ? AND home_id = ? ORDER BY id DESC LIMIT 1",
        (now or utcnow(), home_id),
    )


def any_awaiting_join(conn: sqlite3.Connection, now: str | None = None) -> bool:
    """Whether an unexpired session is waiting for a device to join (``provisioning_open`` index)."""
    row = conn.execute(
        "SELECT 1 FROM provisioning_sessions WHERE status = 'awaiting_join' AND expires_at > ? LIMIT 1",
        (now or utcnow(),),
    ).fetchone()
    return row is not None


def awaiting_softap(
    conn: sqlite3.Connection, target_device_id: str | None, now: str | None = None
) -> list[ProvisioningSession]:
    """Unexpired sessions a healthcheck from this device could advance: ``new`` ones for an unknown ID (None),
    else the ``reset`` ones targeting it (``provisioning_open`` index; at most one open session per home)."""
    target_sql = "kind = 'new'" if target_device_id is None else "kind = 'reset' AND target_device_id = ?"
    params = () if target_device_id is None else (target_device_id,)
    rows = conn.execute(
        f"{_SELECT} WHERE status = 'awaiting_softap' AND expires_at > ? AND {target_sql} ORDER BY id LIMIT ?",
        (now or utcnow(), *params, MAX_LIMIT),
    )
    return [to_row(ProvisioningSession, row) for row in rows]


def expire_due(conn: sqlite3.Connection, now: str | None = None) -> list[int]:
    """Mark open sessions past ``expires_at`` expired; returns their IDs."""
    rows = conn.execute(
        f"UPDATE provisioning_sessions SET status = 'expired' WHERE {_OPEN_SQL} AND expires_at <= ? RETURNING id",
        (now or utcnow(),),
    ).fetchall()
    return sorted(int(row[0]) for row in rows)


def list_sessions(
    conn: sqlite3.Connection, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[ProvisioningSession]:
    return fetch_page(conn, ProvisioningSession, "provisioning_sessions", "", (), limit=limit, before=before_id)


def add_event(
    conn: sqlite3.Connection, session_id: int, step: str, detail: dict[str, Any] | None = None, at: str | None = None
) -> ProvisioningEvent:
    detail_json = json.dumps(detail or {}, sort_keys=True, separators=(",", ":"))
    event_at = at or utcnow()
    cur = conn.execute(
        "INSERT INTO provisioning_events (session_id, at, step, detail_json) VALUES (?, ?, ?, ?)",
        (session_id, event_at, step, detail_json),
    )
    return ProvisioningEvent(int(cur.lastrowid), session_id, event_at, step, detail_json)


def list_events(
    conn: sqlite3.Connection, session_id: int, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[ProvisioningEvent]:
    """A session's steps, newest first (``provisioning_events_session`` index)."""
    return fetch_page(
        conn, ProvisioningEvent, "provisioning_events", "session_id = ?", (session_id,), limit=limit, before=before_id
    )


def record_sighting(conn: sqlite3.Connection, device_id: str, source_ip: str, at: str | None = None) -> None:
    """Upsert an unknown-ID ``healthcheck`` sighting while a session awaits a join."""
    seen = at or utcnow()
    conn.execute(
        "INSERT INTO pairing_sightings (device_id, source_ip, first_seen, last_seen) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(device_id, source_ip) DO UPDATE SET last_seen = excluded.last_seen",
        (device_id, source_ip, seen, seen),
    )


def latest_sighting_for_ip(conn: sqlite3.Connection, source_ip: str, since: str) -> PairingSighting | None:
    """The most recently seen device at ``source_ip`` since a time (``pairing_sightings_ip`` index)."""
    return fetch_one(
        conn,
        PairingSighting,
        f"SELECT {columns(PairingSighting)} FROM pairing_sightings WHERE source_ip = ? AND last_seen >= ?"
        " ORDER BY last_seen DESC LIMIT 1",
        (source_ip, since),
    )


def prune_sightings(conn: sqlite3.Connection, before: str) -> int:
    """Delete sightings last seen before ``before`` (pruned at 20 min by the provisioning service)."""
    return conn.execute("DELETE FROM pairing_sightings WHERE last_seen < ?", (before,)).rowcount

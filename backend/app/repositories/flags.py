"""Device identity flags (FR-13): raised on the device path, acknowledged by a user."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Literal

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page

FlagKind = Literal["ip_conflict", "telemetry_implausible"]


@dataclass(frozen=True, slots=True)
class IdentityFlag:
    id: int
    device_id: str
    kind: str
    detail_json: str
    raised_at: str
    acked_at: str | None
    acked_by: str | None

    @property
    def detail(self) -> dict[str, Any]:
        return json.loads(self.detail_json)


_SELECT = f"SELECT {columns(IdentityFlag)} FROM device_identity_flags"


def raise_flag(
    conn: sqlite3.Connection, device_id: str, kind: FlagKind, detail: dict[str, Any], at: str | None = None
) -> IdentityFlag:
    detail_json = json.dumps(detail, sort_keys=True, separators=(",", ":"))
    raised_at = at or utcnow()
    cur = conn.execute(
        "INSERT INTO device_identity_flags (device_id, kind, detail_json, raised_at) VALUES (?, ?, ?, ?)",
        (device_id, kind, detail_json, raised_at),
    )
    return IdentityFlag(int(cur.lastrowid), device_id, kind, detail_json, raised_at, None, None)


def get(conn: sqlite3.Connection, flag_id: int) -> IdentityFlag | None:
    return fetch_one(conn, IdentityFlag, f"{_SELECT} WHERE id = ?", (flag_id,))


def has_open(conn: sqlite3.Connection, device_id: str, kind: FlagKind | None = None) -> bool:
    """Whether an unacknowledged flag (of ``kind``, when given) exists (``identity_flags_open`` index; device path)."""
    sql = "SELECT 1 FROM device_identity_flags WHERE device_id = ? AND acked_at IS NULL"
    params: tuple[str, ...] = (device_id,)
    if kind is not None:
        sql += " AND kind = ?"
        params += (kind,)
    row = conn.execute(sql + " LIMIT 1", params).fetchone()
    return row is not None


def list_open(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[IdentityFlag]:
    """Unacknowledged flags for a device (``identity_flags_open`` index; device path)."""
    return fetch_page(
        conn, IdentityFlag, "device_identity_flags", "device_id = ? AND acked_at IS NULL", (device_id,),
        limit=limit, before=before_id,
    )


def list_for_device(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[IdentityFlag]:
    return fetch_page(
        conn, IdentityFlag, "device_identity_flags", "device_id = ?", (device_id,), limit=limit, before=before_id
    )


def ack(conn: sqlite3.Connection, flag_id: int, actor: str, at: str | None = None) -> IdentityFlag | None:
    """Acknowledge a flag (idempotent: an already-acked flag keeps its first ack)."""
    conn.execute(
        "UPDATE device_identity_flags SET acked_at = ?, acked_by = ? WHERE id = ? AND acked_at IS NULL",
        (at or utcnow(), actor, flag_id),
    )
    return get(conn, flag_id)

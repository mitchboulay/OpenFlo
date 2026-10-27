"""Homes: a named group of devices with one IANA timezone."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, MAX_LIMIT, columns, fetch_one, fetch_page, update_columns


@dataclass(frozen=True, slots=True)
class Home:
    id: int
    name: str
    timezone: str
    created_at: str
    actor: str


class HomeUpdate(TypedDict, total=False):
    name: str
    timezone: str


_SELECT = f"SELECT {columns(Home)} FROM homes"
_UPDATABLE = frozenset(HomeUpdate.__annotations__)


def create(conn: sqlite3.Connection, name: str, timezone: str, actor: str, at: str | None = None) -> Home:
    """Insert a home; raises ``sqlite3.IntegrityError`` when the name exists (case-insensitive)."""
    cur = conn.execute(
        "INSERT INTO homes (name, timezone, created_at, actor) VALUES (?, ?, ?, ?)",
        (name, timezone, at or utcnow(), actor),
    )
    home = get(conn, int(cur.lastrowid))
    assert home is not None
    return home


def get(conn: sqlite3.Connection, home_id: int) -> Home | None:
    return fetch_one(conn, Home, f"{_SELECT} WHERE id = ?", (home_id,))


def get_by_name(conn: sqlite3.Connection, name: str) -> Home | None:
    """Case-insensitive lookup via the ``homes_name`` expression index."""
    return fetch_one(conn, Home, f"{_SELECT} WHERE lower(name) = lower(?)", (name,))


def list_homes(
    conn: sqlite3.Connection, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[Home]:
    return fetch_page(conn, Home, "homes", "", (), limit=limit, before=before_id)


def update(conn: sqlite3.Connection, home_id: int, changes: HomeUpdate) -> Home | None:
    update_columns(conn, "homes", "id", home_id, changes, _UPDATABLE)
    return get(conn, home_id)


def delete(conn: sqlite3.Connection, home_id: int) -> bool:
    return conn.execute("DELETE FROM homes WHERE id = ?", (home_id,)).rowcount == 1


def non_retired_device_counts(conn: sqlite3.Connection, home_ids: Sequence[int]) -> dict[int, int]:
    """Non-retired device count per home in one ``devices_home`` index query (homes with none map to 0)."""
    if len(home_ids) > MAX_LIMIT:
        raise ValueError(f"at most {MAX_LIMIT} homes per call")
    counts = dict.fromkeys(home_ids, 0)
    if home_ids:
        marks = ", ".join("?" for _ in home_ids)
        rows = conn.execute(
            f"SELECT home_id, COUNT(*) FROM devices WHERE home_id IN ({marks}) AND status <> 'retired'"
            " GROUP BY home_id",
            tuple(home_ids),
        )
        counts.update({int(home_id): int(count) for home_id, count in rows})
    return counts

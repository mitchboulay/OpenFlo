"""Instance settings: one JSON value per key (instance_id, server_address, admin_user, ...)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from ..persistence.repository import utcnow
from ._rows import columns, fetch_one

INSTANCE_ID = "instance_id"


@dataclass(frozen=True, slots=True)
class Setting:
    key: str
    value_json: str
    updated_at: str
    actor: str

    @property
    def value(self) -> Any:
        return json.loads(self.value_json)


def get(conn: sqlite3.Connection, key: str) -> Setting | None:
    return fetch_one(conn, Setting, f"SELECT {columns(Setting)} FROM settings WHERE key = ?", (key,))


def get_value(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    setting = get(conn, key)
    return setting.value if setting is not None else default


def put(conn: sqlite3.Connection, key: str, value: Any, actor: str, at: str | None = None) -> Setting:
    """Insert or replace ``key`` with the JSON encoding of ``value``."""
    row = Setting(key, json.dumps(value, sort_keys=True, separators=(",", ":")), at or utcnow(), actor)
    conn.execute(
        "INSERT INTO settings (key, value_json, updated_at, actor) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,"
        " updated_at = excluded.updated_at, actor = excluded.actor",
        (row.key, row.value_json, row.updated_at, row.actor),
    )
    return row


def delete(conn: sqlite3.Connection, key: str) -> bool:
    return conn.execute("DELETE FROM settings WHERE key = ?", (key,)).rowcount == 1


def instance_id(conn: sqlite3.Connection) -> str:
    """The instance UUID seeded by migration 002."""
    value = get_value(conn, INSTANCE_ID)
    if not isinstance(value, str):
        raise LookupError("settings.instance_id is missing; migration 002 has not run")
    return value

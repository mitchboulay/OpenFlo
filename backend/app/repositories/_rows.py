"""Shared row mapping and cursor paging for the repository modules.

Repository functions take an open ``sqlite3.Connection`` so a service can compose several of them in one
transaction (``with db.connection() as conn``). Table, column and ORDER BY names passed to these helpers are
code constants, never request input; every value is bound as a parameter.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import fields
from typing import Any, TypeVar

DEFAULT_LIMIT = 50
MAX_LIMIT = 500

T = TypeVar("T")


def columns(cls: type) -> str:
    """The dataclass's fields as a SELECT list, in declaration order."""
    return ", ".join(f.name for f in fields(cls))


def to_row(cls: type[T], row: Sequence[Any]) -> T:
    """Build ``cls`` from a row selected with :func:`columns` (SQLite 0/1 become bools for bool fields)."""
    values = [
        bool(value) if value is not None and f.type in ("bool", bool) else value
        for f, value in zip(fields(cls), row)
    ]
    return cls(*values)


def fetch_one(conn: sqlite3.Connection, cls: type[T], sql: str, params: Sequence[Any] = ()) -> T | None:
    row = conn.execute(sql, tuple(params)).fetchone()
    return to_row(cls, row) if row is not None else None


def check_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    return limit


def fetch_page(
    conn: sqlite3.Connection,
    cls: type[T],
    table: str,
    where: str,
    params: Sequence[Any],
    *,
    limit: int,
    before: Any | None,
    key: str = "id",
) -> list[T]:
    """Rows of ``table`` matching ``where``, newest ``key`` first, strictly before the ``before`` cursor."""
    clauses = [where] if where else []
    args = list(params)
    if before is not None:
        clauses.append(f"{key} < ?")
        args.append(before)
    sql = f"SELECT {columns(cls)} FROM {table}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {key} DESC LIMIT ?"
    args.append(check_limit(limit))
    return [to_row(cls, row) for row in conn.execute(sql, args)]


def update_columns(
    conn: sqlite3.Connection,
    table: str,
    key_column: str,
    key: Any,
    changes: Mapping[str, Any],
    allowed: frozenset[str],
) -> int:
    """UPDATE the ``allowed`` columns named in ``changes``; returns the affected row count."""
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"cannot update {table} columns: {sorted(unknown)}")
    if not changes:
        return 0
    assignments = ", ".join(f"{name} = ?" for name in changes)
    cur = conn.execute(f"UPDATE {table} SET {assignments} WHERE {key_column} = ?", (*changes.values(), key))
    return cur.rowcount

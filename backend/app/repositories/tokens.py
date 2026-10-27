"""API tokens (personal, OIDC exchange, bootstrap). Only SHA-256 digests are stored."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page

TokenKind = Literal["personal", "oidc", "bootstrap"]


@dataclass(frozen=True, slots=True)
class ApiToken:
    id: int
    token_sha256: str
    name: str
    actor: str
    kind: str
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    revoked_at: str | None

    @property
    def fingerprint(self) -> str:
        return self.token_sha256[:8]


_SELECT = f"SELECT {columns(ApiToken)} FROM api_tokens"


def create(
    conn: sqlite3.Connection,
    token_sha256: str,
    name: str,
    actor: str,
    kind: TokenKind,
    expires_at: str | None = None,
    at: str | None = None,
) -> ApiToken:
    cur = conn.execute(
        "INSERT INTO api_tokens (token_sha256, name, actor, kind, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (token_sha256, name, actor, kind, at or utcnow(), expires_at),
    )
    token = get(conn, int(cur.lastrowid))
    assert token is not None
    return token


def get(conn: sqlite3.Connection, token_id: int) -> ApiToken | None:
    return fetch_one(conn, ApiToken, f"{_SELECT} WHERE id = ?", (token_id,))


def get_active_by_hash(conn: sqlite3.Connection, token_sha256: str, now: str | None = None) -> ApiToken | None:
    """The unrevoked, unexpired token with this digest (UNIQUE index lookup)."""
    return fetch_one(
        conn,
        ApiToken,
        f"{_SELECT} WHERE token_sha256 = ? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)",
        (token_sha256, now or utcnow()),
    )


def touch(conn: sqlite3.Connection, token_id: int, at: str | None = None) -> None:
    conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (at or utcnow(), token_id))


def revoke(conn: sqlite3.Connection, token_id: int, at: str | None = None) -> bool:
    """Revoke an active token; False when it does not exist or is already revoked."""
    cur = conn.execute(
        "UPDATE api_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (at or utcnow(), token_id)
    )
    return cur.rowcount == 1


def list_unrevoked(
    conn: sqlite3.Connection, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[ApiToken]:
    return fetch_page(conn, ApiToken, "api_tokens", "revoked_at IS NULL", (), limit=limit, before=before_id)


def revoke_kind_except(
    conn: sqlite3.Connection, kind: TokenKind, keep_sha256: str | None, at: str | None = None
) -> int:
    """Revoke every active token of ``kind`` except the one with ``keep_sha256``; returns the count revoked.

    ponytail: unindexed on ``kind``; api_tokens holds a handful of rows per instance and this runs at startup.
    """
    cur = conn.execute(
        "UPDATE api_tokens SET revoked_at = ? WHERE kind = ? AND revoked_at IS NULL AND token_sha256 IS NOT ?",
        (at or utcnow(), kind, keep_sha256),
    )
    return cur.rowcount

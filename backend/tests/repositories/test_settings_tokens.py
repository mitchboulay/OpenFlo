from __future__ import annotations

import sqlite3

import pytest

from app.repositories import settings, tokens
from tests.repositories.conftest import assert_limit_bounds


def test_settings_put_get_overwrite_delete(conn: sqlite3.Connection) -> None:
    assert settings.get(conn, "server_address") is None
    assert settings.get_value(conn, "server_address", "unset") == "unset"
    settings.put(conn, "server_address", "https://flo.example:8443", "alice", at="t1")
    settings.put(conn, "server_address", {"url": "https://b"}, "bob", at="t2")
    row = settings.get(conn, "server_address")
    assert row is not None and (row.value, row.actor, row.updated_at) == ({"url": "https://b"}, "bob", "t2")
    assert settings.delete(conn, "server_address") is True
    assert settings.delete(conn, "server_address") is False


def test_instance_id_is_seeded(conn: sqlite3.Connection) -> None:
    assert len(settings.instance_id(conn)) == 36
    settings.delete(conn, settings.INSTANCE_ID)
    with pytest.raises(LookupError):
        settings.instance_id(conn)


def test_token_lifecycle(conn: sqlite3.Connection) -> None:
    token = tokens.create(conn, "a" * 64, "laptop", "alice", "personal", expires_at="2999-01-01T00:00:00+00:00")
    assert token.fingerprint == "aaaaaaaa" and token.revoked_at is None
    assert tokens.get_active_by_hash(conn, "a" * 64) == token
    tokens.touch(conn, token.id, at="t-used")
    assert tokens.get(conn, token.id).last_used_at == "t-used"  # type: ignore[union-attr]
    assert tokens.revoke(conn, token.id) is True
    assert tokens.revoke(conn, token.id) is False
    assert tokens.get_active_by_hash(conn, "a" * 64) is None


def test_expired_token_is_inactive(conn: sqlite3.Connection) -> None:
    tokens.create(conn, "b" * 64, "old", "alice", "oidc", expires_at="2000-01-01T00:00:00+00:00")
    assert tokens.get_active_by_hash(conn, "b" * 64) is None


def test_duplicate_token_hash_rejected(conn: sqlite3.Connection) -> None:
    tokens.create(conn, "c" * 64, "one", "alice", "personal")
    with pytest.raises(sqlite3.IntegrityError):
        tokens.create(conn, "c" * 64, "two", "alice", "personal")


def test_token_list_pages_and_skips_revoked(conn: sqlite3.Connection) -> None:
    ids = [tokens.create(conn, f"{n:064d}", f"t{n}", "alice", "personal").id for n in range(5)]
    tokens.revoke(conn, ids[4])
    first = tokens.list_unrevoked(conn, limit=2)
    assert [t.id for t in first] == [ids[3], ids[2]]
    assert [t.id for t in tokens.list_unrevoked(conn, limit=2, before_id=first[-1].id)] == [ids[1], ids[0]]
    assert_limit_bounds(lambda limit: tokens.list_unrevoked(conn, limit=limit))

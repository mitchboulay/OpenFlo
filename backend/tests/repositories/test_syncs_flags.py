from __future__ import annotations

import sqlite3

from app.repositories import flags, syncs
from tests.repositories.conftest import assert_limit_bounds


def test_sync_start_extend_latest(conn: sqlite3.Connection, device_id: str) -> None:
    assert syncs.latest(conn, device_id) is None
    first = syncs.start(conn, device_id, "2026-10-26T10:00:00+00:00", "10.0.0.5")
    second = syncs.start(conn, device_id, "2026-10-26T12:00:00+00:00", "10.0.0.5")
    syncs.extend(conn, second.id, "2026-10-26T12:00:30+00:00")
    latest = syncs.latest(conn, device_id)
    assert latest is not None and (latest.id, latest.request_count, latest.ended_at) == (
        second.id, 2, "2026-10-26T12:00:30+00:00",
    )
    assert first.request_count == 1


def test_other_ips_since(conn: sqlite3.Connection, device_id: str) -> None:
    syncs.start(conn, device_id, "2026-10-26T11:58:00+00:00", "10.0.0.7")
    syncs.start(conn, device_id, "2026-10-26T12:00:00+00:00", "10.0.0.5")
    syncs.start(conn, device_id, "2026-10-26T08:00:00+00:00", "10.0.0.8")  # ended long ago
    assert syncs.other_ips_since(conn, device_id, "10.0.0.5", "2026-10-26T11:50:00+00:00") == ["10.0.0.7"]
    assert syncs.other_ips_since(conn, device_id, "10.0.0.7", "2026-10-26T11:59:00+00:00") == ["10.0.0.5"]


def test_sync_list_pages(conn: sqlite3.Connection, device_id: str) -> None:
    ids = [syncs.start(conn, device_id, f"2026-10-26T1{n}:00:00+00:00", "ip").id for n in range(3)]
    assert [s.id for s in syncs.list_recent(conn, device_id, limit=2)] == [ids[2], ids[1]]
    assert [s.id for s in syncs.list_recent(conn, device_id, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: syncs.list_recent(conn, device_id, limit=limit))


def test_flag_raise_and_ack(conn: sqlite3.Connection, device_id: str) -> None:
    assert flags.has_open(conn, device_id) is False
    flag = flags.raise_flag(conn, device_id, "ip_conflict", {"source_ips": ["a", "b"]}, at="t0")
    assert flags.get(conn, flag.id) == flag and flag.detail == {"source_ips": ["a", "b"]}
    assert flags.has_open(conn, device_id) is True
    assert flags.list_open(conn, device_id) == [flag]
    acked = flags.ack(conn, flag.id, "alice", at="t1")
    assert acked is not None and (acked.acked_at, acked.acked_by) == ("t1", "alice")
    again = flags.ack(conn, flag.id, "bob", at="t2")
    assert again is not None and (again.acked_at, again.acked_by) == ("t1", "alice")
    assert flags.has_open(conn, device_id) is False and flags.list_open(conn, device_id) == []
    assert flags.ack(conn, 999, "alice") is None


def test_flag_lists_page(conn: sqlite3.Connection, device_id: str) -> None:
    ids = [flags.raise_flag(conn, device_id, "telemetry_implausible", {"field": str(n)}).id for n in range(3)]
    assert [f.id for f in flags.list_for_device(conn, device_id, limit=2)] == [ids[2], ids[1]]
    assert [f.id for f in flags.list_open(conn, device_id, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: flags.list_open(conn, device_id, limit=limit))
    assert_limit_bounds(lambda limit: flags.list_for_device(conn, device_id, limit=limit))

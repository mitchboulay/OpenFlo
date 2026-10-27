from __future__ import annotations

import sqlite3

import pytest

from app.repositories import bottles, profiles
from tests.repositories.conftest import assert_limit_bounds


@pytest.fixture
def profile_id(conn: sqlite3.Connection) -> int:
    standard = profiles.get_system(conn, profiles.STANDARD)
    assert standard is not None
    return standard.id


def test_one_open_bottle_lifecycle(conn: sqlite3.Connection, device_id: str, profile_id: int) -> None:
    assert bottles.open_for_device(conn, device_id) is None
    assert bottles.close_open(conn, device_id, "eject") is None
    first = bottles.open_bottle(conn, device_id, profile_id, 1065, None, at="t0")
    assert bottles.open_for_device(conn, device_id) == first
    with pytest.raises(sqlite3.IntegrityError):
        bottles.open_bottle(conn, device_id, profile_id, 1065, 500)
    closed = bottles.close_open(conn, device_id, "eject", at="t1")
    assert closed is not None and (closed.id, closed.ended_at, closed.end_reason) == (first.id, "t1", "eject")
    second = bottles.open_bottle(conn, device_id, profile_id, 1065, 800, at="t2")
    assert bottles.open_for_device(conn, device_id) == second
    assert bottles.get(conn, first.id) == closed


def test_bottle_list_pages(conn: sqlite3.Connection, device_id: str, profile_id: int) -> None:
    ids = []
    for n in range(3):
        ids.append(bottles.open_bottle(conn, device_id, profile_id, 1065, None).id)
        bottles.close_open(conn, device_id, "eject")
    assert [b.id for b in bottles.list_for_device(conn, device_id, limit=2)] == [ids[2], ids[1]]
    assert [b.id for b in bottles.list_for_device(conn, device_id, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: bottles.list_for_device(conn, device_id, limit=limit))


def test_fill_adjustments(conn: sqlite3.Connection, device_id: str, profile_id: int) -> None:
    bottle = bottles.open_bottle(conn, device_id, profile_id, 1065, 1000)
    assert bottles.adjustment_total_ml(conn, bottle.id) == 0
    ids = [bottles.add_adjustment(conn, bottle.id, delta, "manual", "alice").id for delta in (-100, 25.5, -10)]
    assert bottles.adjustment_total_ml(conn, bottle.id) == -84.5
    assert [a.id for a in bottles.list_adjustments(conn, bottle.id, limit=2)] == [ids[2], ids[1]]
    assert [a.id for a in bottles.list_adjustments(conn, bottle.id, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: bottles.list_adjustments(conn, bottle.id, limit=limit))

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from app.db import Database
from app.repositories import devices, homes
from app.repositories._rows import MAX_LIMIT

DEVICE_ID = "AABBCCDDEEFF0011"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A foreign-key-enforcing connection to a freshly migrated database."""
    path = tmp_path / "repo.db"
    Database(str(path)).init()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


@pytest.fixture
def home_id(conn: sqlite3.Connection) -> int:
    return homes.create(conn, "Home", "UTC", "tester").id


@pytest.fixture
def device_id(conn: sqlite3.Connection, home_id: int) -> str:
    return devices.create(conn, DEVICE_ID, "active", home_id=home_id, name="Kitchen").device_id


def assert_limit_bounds(list_fn: Callable[..., object]) -> None:
    """``list_fn(limit=...)`` rejects limits outside 1..MAX_LIMIT and accepts both bounds."""
    for bad in (0, -1, MAX_LIMIT + 1):
        with pytest.raises(ValueError):
            list_fn(limit=bad)
    list_fn(limit=1)
    list_fn(limit=MAX_LIMIT)

"""Owner-only state on disk (Security NFR): data dir 0700, database + -wal/-shm and secret.key 0600."""
from __future__ import annotations

import logging
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def open_umask() -> Iterator[None]:
    """umask 000, so only OpenFLO's own modes can make a file private."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


def test_new_state_is_owner_only(tmp_path: Path, open_umask: None) -> None:
    data = tmp_path / "data"
    app = create_app(Settings(db_path=str(data / "openflo.db"), auth_mode="basic"))
    with app.state.db.connection() as conn:  # while a connection is open, the WAL sidecars exist
        conn.execute("CREATE TABLE IF NOT EXISTS t (x)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        sidecars = [data / "openflo.db-wal", data / "openflo.db-shm"]
        assert all(p.exists() for p in sidecars)
        assert {p.name: _mode(p) for p in sidecars} == {p.name: 0o600 for p in sidecars}
    assert _mode(data) == 0o700
    assert _mode(data / "openflo.db") == 0o600
    assert _mode(data / "secret.key") == 0o600


def test_startup_tightens_broader_files_once(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(db_path=str(tmp_path / "openflo.db"), auth_mode="basic")
    create_app(settings)
    for name in ("openflo.db", "secret.key"):
        (tmp_path / name).chmod(0o644)
    caplog.set_level(logging.WARNING, logger="app.private_files")

    create_app(settings)

    assert _mode(tmp_path / "openflo.db") == 0o600 and _mode(tmp_path / "secret.key") == 0o600
    tightened = [r.getMessage() for r in caplog.records if r.name == "app.private_files"]
    assert len(tightened) == 2 and all("0644 to 0600" in message for message in tightened)
    caplog.clear()
    create_app(settings)
    assert not [r for r in caplog.records if r.name == "app.private_files"]

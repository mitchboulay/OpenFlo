from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from app.db import Database
from app.migrations.runner import MIGRATIONS_DIR, MigrationError, discover

BASELINE_TABLES = {
    "devices", "registrations", "telemetry", "events", "qc_reports", "sync_state",
    "protocol_logs", "device_controls", "dispenses", "dispense_requests",
}
ALL_VERSIONS = [m.version for m in discover(MIGRATIONS_DIR)]
LATE_COLUMNS = "    dose_tenths INTEGER,\n    shift_time_seconds INTEGER,\n"


def _old_schema() -> str:
    """The pre-runner SCHEMA: 001 is that text verbatim, so drop the two columns the old init ALTERed in."""
    baseline = (MIGRATIONS_DIR / "001_baseline.sql").read_text()
    assert LATE_COLUMNS in baseline
    return baseline.replace(LATE_COLUMNS, "")


def _build_pre_runner_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(_old_schema())
        conn.execute("ALTER TABLE device_controls ADD COLUMN dose_tenths INTEGER")
        conn.execute("ALTER TABLE device_controls ADD COLUMN shift_time_seconds INTEGER")
        conn.execute(
            "INSERT INTO device_controls (device_id, dispensing_enabled, dose_tenths, shift_time_seconds, updated_at)"
            " VALUES ('D1', 1, 65, 120, 't0')"
        )


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _versions(path: Path) -> list[int]:
    with sqlite3.connect(path) as conn:
        return [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]


def test_fresh_db_gets_baseline(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    assert Database(str(db_path)).init() == ALL_VERSIONS
    assert BASELINE_TABLES | {"schema_migrations"} <= _tables(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(device_controls)")}
    assert {"dose_tenths", "shift_time_seconds"} <= columns


def test_pre_runner_db_is_baselined_without_reexecuting(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    _build_pre_runner_db(db_path)
    # A 001 that would fail if executed proves it is recorded, not run.
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_baseline.sql").write_text("THIS IS NOT SQL;")

    assert Database(str(db_path)).init(migrations) == [1]
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT dispensing_enabled, dose_tenths, shift_time_seconds FROM device_controls").fetchone()
        name = conn.execute("SELECT name FROM schema_migrations").fetchone()[0]
    assert row == (1, 65, 120)
    assert name == "001_baseline"


def test_db_older_than_baseline_aborts(tmp_path: Path) -> None:
    db_path = tmp_path / "ancient.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_old_schema())
    with pytest.raises(MigrationError, match="predates"):
        Database(str(db_path)).init()
    assert "schema_migrations" not in _tables(db_path)


def test_init_twice_is_noop(tmp_path: Path) -> None:
    db_path = tmp_path / "twice.db"
    db = Database(str(db_path))
    db.init()
    with sqlite3.connect(db_path) as conn:
        before = conn.execute("SELECT * FROM schema_migrations").fetchall()
        schema_before = conn.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    assert db.init() == ALL_VERSIONS
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT * FROM schema_migrations").fetchall() == before
        assert conn.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == schema_before


def test_failing_migration_rolls_back_and_raises(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    shutil.copy(MIGRATIONS_DIR / "001_baseline.sql", migrations)
    (migrations / "002_broken.sql").write_text(
        "CREATE TABLE half_done (id INTEGER PRIMARY KEY);\n"
        "INSERT INTO half_done (id) VALUES (1);\n"
        "INSERT INTO no_such_table VALUES (1);\n"
    )
    db_path = tmp_path / "broken.db"

    with pytest.raises(MigrationError, match="002_broken.sql"):
        Database(str(db_path)).init(migrations)
    assert "half_done" not in _tables(db_path)
    assert _versions(db_path) == [1]

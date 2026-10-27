"""Numbered SQL migrations: ``NNN_name.sql`` files applied in order, each atomically."""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent
BASELINE_VERSION = 1
_FILENAME = re.compile(r"^(\d{3})_(\w+)\.sql$")

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


class MigrationError(RuntimeError):
    """A migration could not be applied; startup must abort."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


def discover(migrations_dir: Path) -> list[Migration]:
    """Return the ``NNN_*.sql`` migrations in ``migrations_dir``, ordered by version."""
    found: dict[int, Migration] = {}
    for path in migrations_dir.iterdir():
        match = _FILENAME.match(path.name)
        if not match:
            continue
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"duplicate migration version {version}: {found[version].path.name}, {path.name}")
        found[version] = Migration(version, path.stem, path)
    return [found[v] for v in sorted(found)]


def split_statements(script: str) -> list[str]:
    """Split a SQL script into complete statements (semicolon-safe inside strings/triggers)."""
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        statements.append(buffer.strip())  # sqlite rejects it if it is a truncated statement
    return statements


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _record(conn: sqlite3.Connection, migration: Migration) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
        (migration.version, migration.name, datetime.now(timezone.utc).isoformat()),
    )


def _baseline_pre_runner_db(conn: sqlite3.Connection, migrations: list[Migration]) -> None:
    """Mark 001 applied on a database created before the runner existed."""
    if _table_exists(conn, "schema_migrations") or not _table_exists(conn, "device_controls"):
        return
    if "shift_time_seconds" not in _columns(conn, "device_controls"):
        raise MigrationError("database predates the 001 baseline (device_controls.shift_time_seconds missing)")
    baseline = next((m for m in migrations if m.version == BASELINE_VERSION), None)
    if baseline is None:
        raise MigrationError(f'baseline migration {BASELINE_VERSION:03d}_*.sql not found')
    conn.execute(_CREATE_TRACKING_TABLE)
    _record(conn, baseline)
    logger.info("baselined pre-runner database at migration %s", baseline.name)


def _rollback(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:  # some sqlite errors already rolled back
        conn.execute("ROLLBACK")


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    try:
        conn.execute("BEGIN IMMEDIATE")
        for statement in split_statements(migration.path.read_text(encoding="utf-8")):
            conn.execute(statement)
        _record(conn, migration)
        conn.execute("COMMIT")
    except Exception as exc:
        _rollback(conn)
        raise MigrationError(f"migration {migration.path.name} failed: {exc}") from exc
    logger.info("applied migration %s", migration.name)


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations; return the applied version list. Idempotent.

    ``conn`` must be in autocommit mode (``isolation_level=None``) so transactions are explicit.
    """
    migrations = discover(migrations_dir)
    conn.execute("BEGIN IMMEDIATE")
    try:
        _baseline_pre_runner_db(conn, migrations)
        conn.execute(_CREATE_TRACKING_TABLE)
        conn.execute("COMMIT")
    except BaseException:
        _rollback(conn)
        raise
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for migration in migrations:
        if migration.version not in applied:
            _apply(conn, migration)
    return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]

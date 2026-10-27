from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app import private_files
from app.migrations.runner import MIGRATIONS_DIR, migrate


class Database:
    def __init__(self, path: str):
        self.path = path

    def _connect(self, isolation_level: str | None = "") -> sqlite3.Connection:
        path = Path(self.path)
        private_files.make_dir(path.parent)
        private_files.create_file(path)  # 0600 before SQLite opens it; -wal/-shm inherit the mode
        conn = sqlite3.connect(self.path, timeout=5.0, check_same_thread=False, isolation_level=isolation_level)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self, migrations_dir: Path = MIGRATIONS_DIR) -> list[int]:
        """Apply pending schema migrations; raises MigrationError (aborting startup) on failure.

        Also makes the database and its sidecars owner-only if an older install left them broader."""
        private_files.tighten_database(Path(self.path))  # first, so sidecars SQLite creates now copy 0600
        conn = self._connect(isolation_level=None)
        try:
            return migrate(conn, migrations_dir)
        finally:
            conn.close()

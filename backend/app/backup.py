"""Database backup and restore (Reliability NFR, I3.1).

Backups use SQLite's online backup API, so they are consistent while the app is running (WAL included); the live
file is never copied byte for byte. Each backup is integrity-checked, written 0600 under ``<data>/backups`` with a
UTC timestamp in its name, and only the newest ``KEEP`` are kept.

A restore replaces the live database, so it needs the app stopped. The app holds a shared ``flock`` on
``<data>/openflo.lock`` for its lifetime (``hold_app_lock``); a restore takes it exclusively without waiting and
refuses when it can't. flock works across containers that share the ``/data`` volume.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .private_files import DIR_MODE, FILE_MODE

KEEP = 14
BACKUP_DIR = "backups"
LOCK_FILE = "openflo.lock"
PREFIX = "openflo-"
SUFFIX = ".db"


class BackupError(RuntimeError):
    """The backup or restore did not happen; the message says why (no secrets, no row data)."""


@dataclass(frozen=True, slots=True)
class RestoreResult:
    restored_from: Path
    previous_saved_as: Path | None


def backup_dir(db_path: Path) -> Path:
    return db_path.parent / BACKUP_DIR


def list_backups(directory: Path) -> list[Path]:
    """Backups, oldest first. The UTC timestamp in the name sorts lexically."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.name.startswith(PREFIX) and p.name.endswith(SUFFIX))


def integrity(path: Path) -> str:
    """``PRAGMA integrity_check`` of a file that is not live; ``"ok"`` when sound. Never creates the file."""
    if not path.is_file():
        raise BackupError(f"{path} does not exist")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return f"not a readable SQLite database: {exc}"
    return "; ".join(str(row[0]) for row in rows)


def _create_private(path: Path) -> None:
    """Create ``path`` empty with mode 0600 regardless of umask; fail if it exists."""
    os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE))


def _sqlite_copy(source: Path, dest: Path) -> None:
    """Online backup of ``source`` into the existing empty file ``dest`` (busy-waits up to 5 s per lock).

    The copy inherits the live database's WAL mode; switching it to a rollback journal makes it one
    self-contained file, with no ``-wal``/``-shm`` sidecars. The app turns WAL back on when it opens a restore."""
    src = sqlite3.connect(source, timeout=5.0)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
        finally:
            dst.close()
    finally:
        src.close()


def _timestamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def backup(db_path: Path, keep: int = KEEP, now: datetime | None = None) -> Path:
    """Back up the live database; returns the new file. Prunes to the newest ``keep`` only after it succeeds."""
    if not db_path.is_file():
        raise BackupError(f"database {db_path} does not exist")
    directory = backup_dir(db_path)
    directory.mkdir(mode=DIR_MODE, exist_ok=True)
    final = directory / f"{PREFIX}{_timestamp(now or datetime.now(timezone.utc))}{SUFFIX}"
    partial = final.with_name(final.name + ".partial")
    _create_private(partial)
    try:
        _sqlite_copy(db_path, partial)
        result = integrity(partial)
        if result != "ok":
            raise BackupError(f"backup failed its integrity check: {result}")
        os.replace(partial, final)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    prune(directory, keep)
    return final


def prune(directory: Path, keep: int = KEEP) -> list[Path]:
    """Delete all but the newest ``keep`` backups; returns what was deleted."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    stale = list_backups(directory)[:-keep]
    for path in stale:
        path.unlink()
    return stale


@contextlib.contextmanager
def hold_app_lock(db_path: Path) -> Iterator[None]:
    """Held by the running app (shared, so tests may run several apps). Waits while a restore holds it."""
    fd = os.open(db_path.parent / LOCK_FILE, os.O_CREAT | os.O_RDWR, FILE_MODE)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        yield
    finally:
        os.close(fd)  # releases the lock


def resolve(db_path: Path, name: str) -> Path:
    """A backup by file name (looked up in the backups directory) or by path."""
    candidate = Path(name)
    if candidate.parent == Path(".") and not candidate.exists():
        candidate = backup_dir(db_path) / name
    return candidate


def restore(db_path: Path, source: Path, now: datetime | None = None) -> RestoreResult:
    """Replace the live database with ``source``. Refuses when ``source`` fails its integrity check or the app
    is running. The database being replaced is saved first as ``backups/pre-restore-<UTC time>.db``."""
    result = integrity(source)
    if result != "ok":
        raise BackupError(f"refusing to restore {source.name}: integrity check: {result}")
    fd = os.open(db_path.parent / LOCK_FILE, os.O_CREAT | os.O_RDWR, FILE_MODE)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError("OpenFLO is running; stop it first (docker compose stop openflo)") from None
        return _swap(db_path, source, now or datetime.now(timezone.utc))
    finally:
        os.close(fd)  # releases the lock

def _swap(db_path: Path, source: Path, now: datetime) -> RestoreResult:
    staged = db_path.with_name(db_path.name + ".restoring")
    staged.unlink(missing_ok=True)
    _create_private(staged)
    try:
        _sqlite_copy(source, staged)
        result = integrity(staged)
        if result != "ok":
            raise BackupError(f"restored copy failed its integrity check: {result}")
        previous: Path | None = None
        if db_path.is_file():
            directory = backup_dir(db_path)
            directory.mkdir(mode=DIR_MODE, exist_ok=True)
            # Not PREFIX-named, so retention never deletes it.
            previous = directory / f"pre-restore-{_timestamp(now)}{SUFFIX}"
            _create_private(previous)
            _sqlite_copy(db_path, previous)  # folds in any WAL left by an unclean stop
        # A WAL or shared-memory file left by the old database must never be replayed onto the restored one.
        for leftover in (db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")):
            leftover.unlink(missing_ok=True)
        os.replace(staged, db_path)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return RestoreResult(source, previous)

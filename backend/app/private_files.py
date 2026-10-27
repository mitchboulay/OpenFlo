"""Owner-only state on disk (Security NFR): the database, its ``-wal``/``-shm``, ``secret.key`` and backups.

OpenFLO creates files 0600 and directories 0700 regardless of umask. Files left broader by an older version
or a hand copy are tightened at startup, with one log line per file. SQLite gives ``-wal``/``-shm`` the main
database file's mode, so creating that file 0600 covers its sidecars too.
"""
from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

FILE_MODE = 0o600
DIR_MODE = 0o700
GROUP_OTHER_BITS = 0o077
SQLITE_SIDECARS = ("-wal", "-shm")


def make_dir(path: Path) -> None:
    """Create ``path`` (and missing parents) 0700. An existing directory, e.g. a mounted volume, is left as is."""
    path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)


def create_file(path: Path) -> None:
    """Create ``path`` empty with mode 0600 unless it exists; never truncates."""
    os.close(os.open(path, os.O_CREAT | os.O_WRONLY, FILE_MODE))


def tighten(path: Path) -> bool:
    """Drop group/other permissions from an existing file; True when it changed something."""
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return False
    if not mode & GROUP_OTHER_BITS:
        return False
    path.chmod(mode & ~GROUP_OTHER_BITS)
    logger.warning("tightened %s from %04o to %04o (owner-only)", path, mode, mode & ~GROUP_OTHER_BITS)
    return True


def tighten_database(db_path: Path) -> None:
    """The live database and its WAL sidecars."""
    for path in (db_path, *(db_path.with_name(db_path.name + suffix) for suffix in SQLITE_SIDECARS)):
        tighten(path)

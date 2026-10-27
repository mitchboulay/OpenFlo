"""``openflo`` operations CLI (I3.1): ``backup``, ``restore <file>``, ``check-address``.

The image puts an ``openflo`` wrapper for ``python -m app.cli`` on PATH. Exit status: 0 success, 1 failure,
2 usage error. Output never includes secrets or row data.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from . import backup
from .config import Settings
from .db import Database
from .services import address_check


def _db_path(settings: Settings) -> Path:
    return Path(settings.db_path).resolve()


def cmd_backup(settings: Settings, args: argparse.Namespace) -> int:
    path = backup.backup(_db_path(settings), keep=args.keep)
    print(f"backup written: {path} (integrity ok, keeping newest {args.keep})")
    return 0


def cmd_restore(settings: Settings, args: argparse.Namespace) -> int:
    db_path = _db_path(settings)
    result = backup.restore(db_path, backup.resolve(db_path, args.file))
    print(f"restored {db_path} from {result.restored_from}")
    if result.previous_saved_as:
        print(f"the replaced database was saved as {result.previous_saved_as}")
    print("start OpenFLO again: docker compose up -d")
    return 0


def cmd_check_address(settings: Settings, args: argparse.Namespace) -> int:
    db_path = _db_path(settings)
    if not db_path.is_file():
        raise backup.BackupError(f"database {db_path} does not exist")
    result = asyncio.run(address_check.check_and_store(Database(str(db_path)), settings, "cli"))
    if result is None:
        print("no server address is set (Settings → Server address)", file=sys.stderr)
        return 1
    print(f"address check of {result.address} at {result.at}")
    for check in result.checks:
        print(f"  {check.status:<4}  {check.check:<22}  {check.detail}")
    return 1 if result.failed else 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="openflo", description="OpenFLO operations")
    commands = root.add_subparsers(dest="command", required=True)
    run_backup = commands.add_parser("backup", help="back up the database to <data>/backups")
    run_backup.add_argument("--keep", type=int, default=backup.KEEP, help="backups to keep (default %(default)s)")
    run_backup.set_defaults(handler=cmd_backup)
    run_restore = commands.add_parser("restore", help="replace the database with a backup (OpenFLO stopped)")
    run_restore.add_argument("file", help="a backup file name in <data>/backups, or a path")
    run_restore.set_defaults(handler=cmd_restore)
    commands.add_parser("check-address", help="check the saved server address the way a device connects"
                        ).set_defaults(handler=cmd_check_address)
    return root


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    args = parser().parse_args(argv)
    if getattr(args, "keep", 1) < 1:
        parser().error("--keep must be at least 1")
    try:
        return args.handler(settings or Settings.from_env(), args)
    except backup.BackupError as exc:
        print(f"openflo {args.command}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

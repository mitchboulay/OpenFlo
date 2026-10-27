"""``openflo backup`` / ``restore`` / ``check-address`` (I3.1): retention, integrity, 0600, the running-app guard."""
from __future__ import annotations

import sqlite3
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import backup, cli
from app.config import Settings
from app.services import address_check
from app.services.address_check import AddressCheck, CheckResult

T0 = datetime(2026, 10, 1, 2, 30, tzinfo=timezone.utc)


def make_db(path: Path, value: str = "original") -> Path:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", (value,))
    conn.commit()
    conn.close()
    return path


def read_value(path: Path) -> str:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT v FROM t").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return make_db(tmp_path / "openflo.db")


def test_backup_is_private_timestamped_and_sound(db: Path) -> None:
    path = backup.backup(db, now=T0)
    assert path == db.parent / "backups" / "openflo-20261001T023000000000Z.db"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert backup.integrity(path) == "ok"
    assert read_value(path) == "original"
    # One self-contained file: no partial, no WAL/SHM sidecars left by the WAL-mode source.
    assert [p.name for p in path.parent.iterdir()] == [path.name]


def test_backup_captures_uncheckpointed_wal(db: Path) -> None:
    live = sqlite3.connect(db)  # held open, so the write stays in the WAL
    live.execute("UPDATE t SET v = 'in-wal'")
    live.commit()
    try:
        assert read_value(backup.backup(db, now=T0)) == "in-wal"
    finally:
        live.close()


def test_retention_keeps_the_newest(db: Path) -> None:
    made = [backup.backup(db, keep=14, now=T0 + timedelta(days=day)) for day in range(16)]
    assert backup.list_backups(db.parent / "backups") == made[2:]


def test_backup_of_a_missing_database_fails_without_creating_it(tmp_path: Path) -> None:
    with pytest.raises(backup.BackupError, match="does not exist"):
        backup.backup(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_restore_round_trip_saves_the_replaced_database(db: Path) -> None:
    saved = backup.backup(db, now=T0)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE t SET v = 'changed'")
    conn.commit()
    conn.close()
    result = backup.restore(db, saved, now=T0 + timedelta(hours=1))
    assert read_value(db) == "original"
    assert stat.S_IMODE(db.stat().st_mode) == 0o600
    assert result.previous_saved_as is not None and read_value(result.previous_saved_as) == "changed"
    assert stat.S_IMODE(result.previous_saved_as.stat().st_mode) == 0o600
    assert not db.with_name(db.name + "-wal").exists()
    # The pre-restore copy is outside retention's name pattern.
    assert result.previous_saved_as not in backup.list_backups(db.parent / "backups")


def test_restore_refuses_a_corrupt_backup(db: Path, tmp_path: Path) -> None:
    corrupt = backup.backup(db, now=T0)
    data = bytearray(corrupt.read_bytes())
    data[100:4096] = b"\xff" * (4096 - 100)  # header tail and the first page
    corrupt.write_bytes(bytes(data))
    with pytest.raises(backup.BackupError, match="refusing to restore"):
        backup.restore(db, corrupt)
    assert read_value(db) == "original"
    assert not list(db.parent.glob("*.restoring"))


def test_restore_refuses_a_file_that_is_not_sqlite(db: Path, tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database" * 100)
    with pytest.raises(backup.BackupError, match="refusing to restore"):
        backup.restore(db, junk)
    assert read_value(db) == "original"


def test_restore_refuses_while_the_app_runs(db: Path) -> None:
    saved = backup.backup(db, now=T0)
    with backup.hold_app_lock(db):
        with pytest.raises(backup.BackupError, match="stop it first"):
            backup.restore(db, saved)
    backup.restore(db, saved)  # released on app shutdown


def test_running_app_holds_the_lock(tmp_path: Path) -> None:
    from conftest import make_client

    client, _ = make_client(tmp_path)
    db = tmp_path / "backend.db"
    saved = backup.backup(db, now=T0)
    with client:
        with pytest.raises(backup.BackupError, match="stop it first"):
            backup.restore(db, saved)
    backup.restore(db, saved)


def test_cli_backup_and_restore_by_name(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(db_path=str(db))
    assert cli.main(["backup"], settings) == 0
    [name] = [p.name for p in backup.list_backups(db.parent / "backups")]
    assert cli.main(["restore", name], settings) == 0
    assert "restored" in capsys.readouterr().out


def test_cli_reports_failure_as_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(db_path=str(tmp_path / "openflo.db"))
    assert cli.main(["backup"], settings) == 1
    assert cli.main(["restore", "openflo-nope.db"], settings) == 1
    assert "does not exist" in capsys.readouterr().err


def _checked(*statuses: str) -> AddressCheck:
    return AddressCheck("https://openflo.example", "2026-10-01T00:00:00+00:00",
                        [CheckResult("dns", status, "detail") for status in statuses])  # type: ignore[arg-type]


@pytest.mark.parametrize(("statuses", "code"), [(("ok", "warn"), 0), (("ok", "fail"), 1)])
def test_cli_check_address_exit_status(db: Path, monkeypatch: pytest.MonkeyPatch,
                                       statuses: tuple[str, ...], code: int) -> None:
    async def fake(*_: object) -> AddressCheck:
        return _checked(*statuses)

    monkeypatch.setattr(address_check, "check_and_store", fake)
    assert cli.main(["check-address"], Settings(db_path=str(db))) == code


def test_cli_check_address_without_an_address_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def none(*_: object) -> None:
        return None

    monkeypatch.setattr(address_check, "check_and_store", none)
    assert cli.main(["check-address"], Settings(db_path=str(make_db(tmp_path / "o.db")))) == 1

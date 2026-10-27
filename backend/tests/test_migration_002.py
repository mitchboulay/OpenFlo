"""Migration 002: lossless pre-002 upgrade, clean fresh install, idempotence, index-backed device path."""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from app.db import Database
from app.repositories import bottles, devices, dosing, flags, syncs
from fixtures.make_lab_db import LAB_DEVICE_ID, REGISTERED_AT, build_lab_db

BASELINE_TABLES = (
    "devices", "registrations", "telemetry", "events", "qc_reports", "sync_state",
    "protocol_logs", "device_controls", "dispenses", "dispense_requests",
)
STANDARD_CURVE = [[1.0, 1.0], [0.83, 0.93], [0.67, 0.89], [0.5, 0.81], [0.33, 0.66], [0.17, 0.25], [0.0, 0.25]]


@pytest.fixture
def connect() -> Iterator[Callable[[Path], sqlite3.Connection]]:
    opened: list[sqlite3.Connection] = []

    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(path)
        opened.append(conn)
        return conn

    yield _connect
    for conn in opened:
        conn.close()


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in BASELINE_TABLES}


def _controls(conn: sqlite3.Connection) -> tuple[Any, ...]:
    return conn.execute(
        "SELECT device_id, dispensing_enabled, sync_interval_seconds, dose_tenths, shift_time_seconds, updated_at"
        " FROM device_controls"
    ).fetchone()


def _assert_system_profiles_and_instance(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT slug, flow_full_ml_s, curve_json, capacity_ml, default_dose_ml, calibrated, actor"
        " FROM liquid_profiles WHERE home_id IS NULL ORDER BY slug"
    ).fetchall()
    assert [(r[0], r[1], json.loads(r[2]), r[3], r[4], r[5], r[6]) for r in rows] == [
        ("standard", 27.2, STANDARD_CURVE, 1065, 177, 1, "system"),
        ("vinegar", 27.2, STANDARD_CURVE, 1000, 120, 0, "system"),
    ]
    instance = json.loads(conn.execute("SELECT value_json FROM settings WHERE key = 'instance_id'").fetchone()[0])
    assert uuid.UUID(instance).version == 4 and str(uuid.UUID(instance)) == instance


def test_lab_db_migrates_losslessly(tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    before_conn = connect(path)
    counts_before, controls_before = _counts(before_conn), _controls(before_conn)
    before_conn.close()

    assert Database(str(path)).init() == [1, 2, 3]

    conn = connect(path)
    assert _counts(conn) == counts_before
    assert _controls(conn) == controls_before
    assert conn.execute("SELECT wake_preset, schedules_enabled, actor FROM device_controls").fetchone() == (
        None, 0, None,
    )
    home = conn.execute("SELECT id, name, timezone, actor FROM homes").fetchall()
    assert [h[1:] for h in home] == [("Home", "UTC", "system")]

    device = devices.get(conn, LAB_DEVICE_ID)
    assert device is not None
    assert (device.home_id, device.name, device.mac, device.last_ip) == (
        home[0][0], "iFLO", None, "192.168.30.80",
    )
    assert (device.hardware_type, device.pcb_version, device.status) == (None, None, "active")
    assert device.installed_at == REGISTERED_AT
    assert device.registered is True and device.firmware_version == "3.0.64"

    standard = conn.execute("SELECT id FROM liquid_profiles WHERE slug = 'standard'").fetchone()[0]
    dose = dosing.get(conn, LAB_DEVICE_ID)
    assert dose is not None
    assert (dose.profile_id, dose.dose_ml, dose.fixed_tenths, dose.compensation_enabled, dose.flow_scale) == (
        standard, 177, None, True, 1.0,
    )
    bottle = bottles.open_for_device(conn, LAB_DEVICE_ID)
    assert bottle is not None
    assert (bottle.profile_id, bottle.capacity_ml, bottle.initial_fill_ml) == (standard, 1065, None)
    assert conn.execute("SELECT COUNT(*) FROM bottles").fetchone()[0] == 1
    assert conn.execute("SELECT DISTINCT dose_count FROM dispenses").fetchall() == [(1,)]
    _assert_system_profiles_and_instance(conn)


def test_lab_dose_tenths_moves_to_fixed_tenths(tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    with closing(sqlite3.connect(path)) as setup, setup:
        setup.execute("UPDATE device_controls SET dose_tenths = 65")
    Database(str(path)).init()
    conn = connect(path)
    dose = dosing.get(conn, LAB_DEVICE_ID)
    assert dose is not None and (dose.dose_ml, dose.fixed_tenths) == (None, 65)
    assert conn.execute("SELECT dose_tenths FROM device_controls").fetchone() == (65,)


def test_installed_at_falls_back_to_first_seen(tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    with closing(sqlite3.connect(path)) as setup, setup:
        setup.execute("DELETE FROM registrations")
    Database(str(path)).init()
    device = devices.get(connect(path), LAB_DEVICE_ID)
    assert device is not None and device.installed_at == device.first_seen


def test_every_existing_device_joins_one_home(
    tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]
) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    with closing(sqlite3.connect(path)) as setup, setup:
        setup.execute(
            "INSERT INTO devices (device_id, first_seen, last_seen, registered, metadata_json)"
            " VALUES ('D8256700000A0002', '2026-10-26T20:00:00+00:00', '2026-10-26T21:00:00+00:00', 1,"
            " '{\"name\": \"Guest bath\"}')"
        )
    Database(str(path)).init()
    conn = connect(path)
    rows = conn.execute(
        "SELECT d.device_id, d.name, d.last_ip, d.installed_at, h.name FROM devices d JOIN homes h ON h.id = d.home_id"
        " ORDER BY d.device_id"
    ).fetchall()
    assert rows == [
        (LAB_DEVICE_ID, "iFLO", "192.168.30.80", REGISTERED_AT, "Home"),
        ("D8256700000A0002", "Guest bath", None, "2026-10-26T20:00:00+00:00", "Home"),
    ]
    assert conn.execute("SELECT COUNT(*) FROM bottles WHERE ended_at IS NULL").fetchone()[0] == 2


def test_fresh_db_has_no_lab_data(tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]) -> None:
    path = tmp_path / "fresh.db"
    assert Database(str(path)).init() == [1, 2, 3]
    conn = connect(path)
    for table in ("homes", "devices", "device_dosing", "bottles"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
    _assert_system_profiles_and_instance(conn)


def test_init_twice_is_idempotent(tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    db = Database(str(path))
    db.init()
    tables = ("settings", "homes", "devices", "liquid_profiles", "device_dosing", "bottles", "schema_migrations")
    snapshot = {t: connect(path).execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tables}
    assert db.init() == [1, 2, 3]
    conn = connect(path)
    assert {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tables} == snapshot


def test_003_replaces_the_legacy_schedules_table(
    tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]
) -> None:
    """002 leaves ``schedules`` alone; 003 drops it, and the lab device must be (re)served its schedule."""
    path = build_lab_db(tmp_path / "lab.db")
    assert len(connect(path).execute("SELECT * FROM schedules").fetchall()) == 1
    Database(str(path)).init()
    conn = connect(path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "schedules" not in tables
    assert {"schedule_rules", "schedule_entries", "schedule_entry_rules"} <= tables
    # A NULL served hash differs from any desired one, so the next update-device says isScheduleSynced:false.
    assert conn.execute("SELECT schedule_hash FROM sync_state WHERE device_id = ?", (LAB_DEVICE_ID,)).fetchone() == (
        None,)


class _RecordingConnection:
    """Delegates to a connection and records every (sql, params) a repository function executes."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, params: Any = ()) -> sqlite3.Cursor:
        self.statements.append((sql, tuple(params)))
        return self._conn.execute(sql, params)


DEVICE_PATH_QUERIES: list[tuple[str, Callable[[Any], object], str, str]] = [
    ("devices by id", lambda c: devices.get(c, LAB_DEVICE_ID), "devices", "sqlite_autoindex_devices_1"),
    ("syncs recent", lambda c: syncs.latest(c, LAB_DEVICE_ID), "device_syncs", "device_syncs_recent"),
    ("syncs other ips", lambda c: syncs.other_ips_since(c, LAB_DEVICE_ID, "10.0.0.1", "2026-10-26T00:00:00+00:00"),
     "device_syncs", "device_syncs_recent"),
    ("flags open", lambda c: flags.has_open(c, LAB_DEVICE_ID), "device_identity_flags", "identity_flags_open"),
    ("flags open list", lambda c: flags.list_open(c, LAB_DEVICE_ID), "device_identity_flags", "identity_flags_open"),
    ("serving latest", lambda c: dosing.latest_serving(c, LAB_DEVICE_ID), "dose_servings", "dose_servings_recent"),
    ("serving at time", lambda c: dosing.latest_serving(c, LAB_DEVICE_ID, "2026-10-26T00:00:00+00:00"),
     "dose_servings", "dose_servings_recent"),
    ("bottle open", lambda c: bottles.open_for_device(c, LAB_DEVICE_ID), "bottles", "bottles_one_open"),
]


@pytest.mark.parametrize("call,table,index", [q[1:] for q in DEVICE_PATH_QUERIES], ids=[q[0] for q in DEVICE_PATH_QUERIES])
def test_device_path_queries_are_index_backed(
    tmp_path: Path, connect: Callable[[Path], sqlite3.Connection], call: Callable[[Any], object], table: str, index: str
) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    Database(str(path)).init()
    conn = connect(path)
    recorder = _RecordingConnection(conn)
    call(recorder)
    assert recorder.statements
    for sql, params in recorder.statements:
        plan = [row[3] for row in conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)]
        assert not [d for d in plan if re.match(rf"SCAN( TABLE)? {table}\b", d)], plan
        assert any(index in d for d in plan if d.startswith("SEARCH")), plan


def test_existing_devices_get_their_last_check_in_as_a_sync(
    tmp_path: Path, connect: Callable[[Path], sqlite3.Connection]
) -> None:
    path = build_lab_db(tmp_path / "lab.db")
    before = connect(path)
    last_seen = before.execute("SELECT last_seen FROM devices WHERE device_id = ?", (LAB_DEVICE_ID,)).fetchone()[0]
    before.close()

    Database(str(path)).init()

    rows = connect(path).execute(
        "SELECT started_at, ended_at, request_count, source_ip FROM device_syncs WHERE device_id = ?",
        (LAB_DEVICE_ID,),
    ).fetchall()
    assert rows == [(last_seen, last_seen, 1, "192.168.30.80")]

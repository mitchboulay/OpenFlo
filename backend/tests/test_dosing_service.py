"""Dosing service (FR-7, FR-8): views, set_dosing, calibration and bottle operations over a migrated DB."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.db import Database
from app.persistence.repository import utcnow
from app.repositories import devices, dispenses, homes, profiles
from app.repositories import dosing as dosing_repo
from app.services import dosing_service as svc

DEVICE = "AABBCCDDEEFF0011"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    path = tmp_path / "svc.db"
    Database(str(path)).init()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    home = homes.create(connection, "Home", "UTC", "t").id
    devices.create(connection, DEVICE, "active", home_id=home)
    yield connection
    connection.close()


def profile(conn: sqlite3.Connection, slug: str) -> profiles.LiquidProfile:
    found = profiles.get_system(conn, slug)
    assert found is not None
    return found


def dispense(conn: sqlite3.Connection, est_ml: float, *, ts: int = 1, at: str | None = None) -> None:
    dispenses.insert(conn, DEVICE, 8, ts, bottle_id=None, est_volume_ml=est_ml, dose_count=1, at=at or utcnow())


def test_new_device_defaults_to_standard_177_ml(conn: sqlite3.Connection) -> None:
    view = svc.get_dosing_view(conn, DEVICE)
    assert (view.profile.slug, view.dose_ml, view.fixed_seconds, view.computed_seconds) == ("standard", 177, None, 6.5)
    assert (view.flow_scale, view.capped_ml_when_low, view.warning, view.bottle) == (1.0, None, None, None)


def test_set_dosing_range_and_capped_warning(conn: sqlite3.Connection) -> None:
    standard = profile(conn, "standard").id
    with pytest.raises(svc.DoseOutOfRange) as err:
        svc.set_dosing(conn, DEVICE, standard, dose_ml=900, actor="t")
    assert (err.value.code, err.value.min_ml, err.value.max_ml) == ("DOSE_OUT_OF_RANGE", 27.2, 816.0)
    view = svc.set_dosing(conn, DEVICE, standard, dose_ml=250, actor="t")
    assert view.warning == "CAPPED_WHEN_LOW" and view.capped_ml_when_low == pytest.approx(204.0)
    assert svc.set_dosing(conn, DEVICE, standard, dose_ml=250, compensation_enabled=False, actor="t").warning is None
    fixed = svc.set_dosing(conn, DEVICE, standard, fixed_seconds=4.2, actor="t")
    assert (fixed.dose_ml, fixed.fixed_seconds, fixed.computed_seconds) == (None, 4.2, 4.2)
    with pytest.raises(ValueError):
        svc.set_dosing(conn, DEVICE, standard, dose_ml=100, fixed_seconds=4.2, actor="t")
    with pytest.raises(svc.ProfileNotFound):
        svc.set_dosing(conn, DEVICE, 9999, dose_ml=100, actor="t")


def test_calibrate_compounds_and_requires_recent_dispense(conn: sqlite3.Connection) -> None:
    standard = profile(conn, "standard").id
    svc.set_dosing(conn, DEVICE, standard, fixed_seconds=6.5, actor="t")
    with pytest.raises(svc.NoRecentDispense):
        svc.calibrate(conn, DEVICE, 181, "t")
    dispense(conn, 27.2 * 6.5)
    first = svc.calibrate(conn, DEVICE, 181, "t").flow_scale
    assert first == pytest.approx(1.02, abs=0.005)
    with pytest.raises(svc.NoRecentDispense):  # the same cup never compounds twice
        svc.calibrate(conn, DEVICE, 181, "t")
    dispense(conn, 27.2 * first * 6.5, ts=2)
    assert svc.calibrate(conn, DEVICE, 190, "t").flow_scale == pytest.approx(190 / (27.2 * 6.5))
    dispense(conn, 180, ts=3)
    with pytest.raises(svc.CalibrationImplausible):
        svc.calibrate(conn, DEVICE, 2000, "t")


def test_calibrate_ignores_dispenses_older_than_24_hours(conn: sqlite3.Connection) -> None:
    svc.ensure_dosing(conn, DEVICE)
    conn.execute("UPDATE device_dosing SET updated_at = '2000-01-01T00:00:00+00:00'")
    dispense(conn, 176.8, at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat())
    with pytest.raises(svc.NoRecentDispense):
        svc.calibrate(conn, DEVICE, 181, "t")


def test_new_bottle_and_adjust_fill(conn: sqlite3.Connection) -> None:
    with pytest.raises(svc.NoOpenBottle):
        svc.adjust_fill(conn, DEVICE, 500, "t")
    full = svc.new_bottle(conn, DEVICE, "full", None, "t")
    assert (full.capacity_ml, full.est_remaining_ml, full.est_doses_left, full.guidance) == (1065, 1065, 6, "ok")
    unknown = svc.new_bottle(conn, DEVICE, "set", None, "t")
    assert (unknown.est_remaining_ml, unknown.guidance) == (None, "unknown")
    assert conn.execute("SELECT count(*) FROM bottles WHERE ended_at IS NULL").fetchone() == (1,)
    assert conn.execute("SELECT end_reason FROM bottles WHERE id = ?", (full.id,)).fetchone() == ("replaced",)
    adjusted = svc.adjust_fill(conn, DEVICE, 300, "t")  # sets the level of an unknown bottle
    assert (adjusted.est_remaining_ml, adjusted.est_doses_left, adjusted.guidance) == (300, 1, "refill_soon")
    dispenses.insert(conn, DEVICE, 8, 9, bottle_id=adjusted.id, est_volume_ml=200, dose_count=1)
    assert svc.adjust_fill(conn, DEVICE, 150, "t").est_remaining_ml == pytest.approx(150)
    assert svc.get_dosing_view(conn, DEVICE).bottle.guidance == "refill_now"
    with pytest.raises(svc.FillOutOfRange):
        svc.adjust_fill(conn, DEVICE, 2000, "t")
    with pytest.raises(svc.FillOutOfRange):
        svc.new_bottle(conn, DEVICE, "set", -1, "t")


def test_serve_dose_records_physical_flow(conn: sqlite3.Connection) -> None:
    svc.new_bottle(conn, DEVICE, "set", 532.5, "t")  # r = 0.5
    serving = svc.serve_dose(conn, DEVICE)
    assert (serving.tenths, serving.flow_ml_s) == (80, pytest.approx(27.2 * 0.81))
    svc.set_dosing(conn, DEVICE, profile(conn, "standard").id, dose_ml=177, compensation_enabled=False, actor="t")
    uncompensated = svc.serve_dose(conn, DEVICE)  # timed for a full bottle, volume still at r = 0.5
    assert (uncompensated.tenths, uncompensated.flow_ml_s) == (65, pytest.approx(27.2 * 0.81))
    assert dosing_repo.latest_serving(conn, DEVICE) == uncompensated

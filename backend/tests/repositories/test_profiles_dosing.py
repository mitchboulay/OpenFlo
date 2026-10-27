from __future__ import annotations

import sqlite3

import pytest

from app.repositories import dosing, profiles
from tests.repositories.conftest import assert_limit_bounds


def test_system_profiles(conn: sqlite3.Connection) -> None:
    standard = profiles.get_system(conn, profiles.STANDARD)
    assert standard is not None and standard.system and standard.calibrated is True
    assert standard.curve[0] == (1.0, 1.0) and standard.curve[-1] == (0.0, 0.25) and len(standard.curve) == 7
    vinegar = profiles.get_system(conn, profiles.VINEGAR)
    assert vinegar is not None and (vinegar.capacity_ml, vinegar.default_dose_ml, vinegar.calibrated) == (
        1000, 120, False,
    )


def test_home_profile_crud_and_visibility(conn: sqlite3.Connection, home_id: int) -> None:
    custom = profiles.create(conn, home_id, "citrus", "Citrus", flow_full_ml_s=20.0, curve=[(1.0, 1.0), (0.0, 0.5)],
                             capacity_ml=900, default_dose_ml=150, actor="alice")
    assert not custom.system and custom.curve == [(1.0, 1.0), (0.0, 0.5)]
    with pytest.raises(sqlite3.IntegrityError):
        profiles.create(conn, home_id, "citrus", "Again", flow_full_ml_s=1, curve=[], capacity_ml=1,
                        default_dose_ml=1, actor="alice")
    assert [p.slug for p in profiles.list_visible(conn, home_id)] == ["citrus", "vinegar", "standard"]
    assert [p.slug for p in profiles.list_visible(conn)] == ["vinegar", "standard"]
    assert [p.slug for p in profiles.list_visible(conn, home_id, limit=1, before_id=custom.id)] == ["vinegar"]
    updated = profiles.update(conn, custom.id, {"name": "Lemon", "calibrated": True})
    assert updated is not None and (updated.name, updated.calibrated) == ("Lemon", True)
    assert profiles.in_use(conn, custom.id) is False
    assert profiles.delete(conn, custom.id) is True
    assert_limit_bounds(lambda limit: profiles.list_visible(conn, home_id, limit=limit))


def test_dosing_put_switch_mode_and_calibrate(conn: sqlite3.Connection, device_id: str) -> None:
    standard = profiles.get_system(conn, profiles.STANDARD)
    assert standard is not None
    assert dosing.get(conn, device_id) is None
    put = dosing.put(conn, device_id, standard.id, dose_ml=177, fixed_tenths=None, actor="alice", at="t0")
    assert dosing.get(conn, device_id) == put
    assert profiles.in_use(conn, standard.id) is True
    fixed = dosing.put(conn, device_id, standard.id, dose_ml=None, fixed_tenths=65, compensation_enabled=False,
                       actor="bob", at="t1")
    assert dosing.get(conn, device_id) == fixed
    scaled = dosing.set_flow_scale(conn, device_id, 1.02, "carol", at="t2")
    assert scaled is not None and (scaled.flow_scale, scaled.actor, scaled.fixed_tenths) == (1.02, "carol", 65)
    with pytest.raises(sqlite3.IntegrityError):
        dosing.put(conn, device_id, standard.id, dose_ml=177, fixed_tenths=65, actor="x")
    with pytest.raises(sqlite3.IntegrityError):
        dosing.put(conn, device_id, standard.id, dose_ml=None, fixed_tenths=301, actor="x")


def test_servings_latest_and_paging(conn: sqlite3.Connection, device_id: str) -> None:
    assert dosing.latest_serving(conn, device_id) is None
    ids = [dosing.record_serving(conn, device_id, 65 + n, 27.2, at=f"2026-10-26T1{n}:00:00+00:00").id
           for n in range(3)]
    latest = dosing.latest_serving(conn, device_id)
    assert latest is not None and latest.id == ids[2]
    at_time = dosing.latest_serving(conn, device_id, "2026-10-26T11:30:00+00:00")
    assert at_time is not None and (at_time.id, at_time.tenths) == (ids[1], 66)
    assert dosing.latest_serving(conn, device_id, "2026-10-26T09:00:00+00:00") is None
    assert [s.id for s in dosing.list_servings(conn, device_id, limit=2, before_id=ids[2])] == [ids[1], ids[0]]
    assert_limit_bounds(lambda limit: dosing.list_servings(conn, device_id, limit=limit))

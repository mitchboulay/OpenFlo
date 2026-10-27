from __future__ import annotations

import sqlite3

import pytest

from app.repositories import devices, homes
from tests.repositories.conftest import DEVICE_ID, assert_limit_bounds


def test_home_crud_and_case_insensitive_name(conn: sqlite3.Connection) -> None:
    home = homes.create(conn, "Beach House", "America/New_York", "alice")
    assert homes.get_by_name(conn, "beach house") == home
    with pytest.raises(sqlite3.IntegrityError):
        homes.create(conn, "BEACH HOUSE", "UTC", "alice")
    updated = homes.update(conn, home.id, {"name": "Cabin", "timezone": "UTC"})
    assert updated is not None and (updated.name, updated.timezone) == ("Cabin", "UTC")
    with pytest.raises(ValueError):
        homes.update(conn, home.id, {"actor": "mallory"})  # type: ignore[typeddict-unknown-key]
    assert homes.delete(conn, home.id) is True
    assert homes.get(conn, home.id) is None


def test_home_list_pages(conn: sqlite3.Connection) -> None:
    ids = [homes.create(conn, f"H{n}", "UTC", "alice").id for n in range(3)]
    assert [h.id for h in homes.list_homes(conn, limit=2)] == [ids[2], ids[1]]
    assert [h.id for h in homes.list_homes(conn, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: homes.list_homes(conn, limit=limit))


def test_non_retired_device_counts(conn: sqlite3.Connection, home_id: int) -> None:
    empty = homes.create(conn, "Empty", "UTC", "alice").id
    devices.create(conn, "D1", "active", home_id=home_id)
    devices.create(conn, "D2", "provisioning", home_id=home_id)
    devices.create(conn, "D3", "retired", home_id=home_id)
    assert homes.non_retired_device_counts(conn, [home_id, empty]) == {home_id: 2, empty: 0}
    assert homes.non_retired_device_counts(conn, []) == {}
    with pytest.raises(ValueError):
        homes.non_retired_device_counts(conn, list(range(501)))


def test_device_create_get_update(conn: sqlite3.Connection, home_id: int) -> None:
    device = devices.create(conn, DEVICE_ID, "active", registered=True, home_id=home_id, name="Kitchen",
                            location="Sink", last_ip="10.0.0.5", at="t0")
    assert device.registered is True and device.installed_at == "t0" and device.status == "active"
    assert devices.get(conn, DEVICE_ID) == device
    updated = devices.update(conn, DEVICE_ID, {"name": "Bath", "pcb_version": "6.3.0", "hardware_type": "valve"})
    assert updated is not None and (updated.name, updated.pcb_version, updated.hardware_type) == ("Bath", "6.3.0", "valve")
    with pytest.raises(sqlite3.IntegrityError):
        devices.update(conn, DEVICE_ID, {"status": "bogus"})  # type: ignore[typeddict-item]
    with pytest.raises(sqlite3.IntegrityError):
        devices.create(conn, DEVICE_ID, "active")


def test_unclaimed_device_has_no_install_date(conn: sqlite3.Connection) -> None:
    device = devices.create(conn, "U1", "unclaimed", last_ip="10.0.0.9")
    assert (device.home_id, device.installed_at, device.registered) == (None, None, False)
    assert devices.count_by_status(conn, "unclaimed") == 1


def test_device_lists_page_by_device_id(conn: sqlite3.Connection, home_id: int) -> None:
    for n in range(4):
        devices.create(conn, f"D{n}", "active", home_id=home_id)
    devices.create(conn, "D9", "retired", home_id=home_id)
    assert [d.device_id for d in devices.list_by_home(conn, home_id, limit=2)] == ["D3", "D2"]
    assert [d.device_id for d in devices.list_by_home(conn, home_id, before_id="D2")] == ["D1", "D0"]
    assert len(devices.list_by_home(conn, home_id, include_retired=True)) == 5
    assert [d.device_id for d in devices.list_by_status(conn, "retired")] == ["D9"]
    assert_limit_bounds(lambda limit: devices.list_by_home(conn, home_id, limit=limit))
    assert_limit_bounds(lambda limit: devices.list_by_status(conn, "active", limit=limit))

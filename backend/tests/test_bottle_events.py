"""Device path: get-bottle servings and send-events bottle lifecycle / dispense attribution (AD-5, FR-8)."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories import bottles, profiles
from app.repositories import dosing as dosing_repo
from app.services import dosing_service
from conftest import DEVICE_ID, make_client, register

DEV = {"x-device-id": DEVICE_ID}
T0 = 1_793_050_000


def iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


@pytest.fixture
def device(tmp_path) -> Iterator[tuple[TestClient, Any]]:
    c, app = make_client(tmp_path)
    with c:
        assert register(c).status_code == 200
        app.state.repo.update_controls(DEVICE_ID, {"dispensing_enabled": True})
        yield c, app


def send(c: TestClient, *items: tuple[int, int, int]) -> None:
    body = {"data": [{"status": s, "code": code, "timestamp": ts} for s, code, ts in items]}
    assert c.post("/device-api/v2/send-events", json=body, headers=DEV).status_code == 200


def rows(app: Any, sql: str) -> list[tuple]:
    with app.state.repo.db.connection() as conn:
        return [tuple(r) for r in conn.execute(sql, (DEVICE_ID,))]


def test_eject_then_install_keeps_one_open_bottle(device) -> None:
    c, app = device
    send(c, (1, 5, T0))  # first install
    send(c, (1, 6, T0 + 100), (1, 5, T0 + 200))
    send(c, (1, 6, T0 + 100), (1, 5, T0 + 200))  # resent batch changes nothing
    history = rows(app, "SELECT initial_fill_ml, started_at, ended_at, end_reason FROM bottles WHERE device_id = ?"
                        " ORDER BY id")
    assert history == [(1065.0, iso(T0), iso(T0 + 100), "ejected"), (1065.0, iso(T0 + 200), None, None)]
    send(c, (1, 6, T0 + 300))
    assert rows(app, "SELECT count(*) FROM bottles WHERE device_id = ? AND ended_at IS NULL") == [(0,)]


def test_vinegar_bottle_opens_with_unknown_fill(device) -> None:
    c, app = device
    with app.state.repo.db.connection() as conn:
        vinegar = profiles.get_system(conn, profiles.VINEGAR)
        assert vinegar is not None
        dosing_service.set_dosing(conn, DEVICE_ID, vinegar.id, dose_ml=120, actor="t")
    send(c, (1, 5, T0))
    assert rows(app, "SELECT capacity_ml, initial_fill_ml FROM bottles WHERE device_id = ?") == [(1000.0, None)]


def test_get_bottle_serves_uniform_table_and_records_serving(device) -> None:
    c, app = device
    send(c, (1, 5, T0))  # standard, full: r = 1
    body = c.post("/device-api/v2/get-bottle", headers=DEV).json()
    assert body["config"] == [{"index": i, "dispenseTime": 65} for i in range(6)]
    assert body["data"]["dispenseLeft"] == body["data"]["dispenseNumber"] == 100
    with app.state.repo.db.connection() as conn:  # half empty: slower flow, longer open time
        bottle = bottles.open_for_device(conn, DEVICE_ID)
        assert bottle is not None
        bottles.add_adjustment(conn, bottle.id, -532.5, "test", "t")
    body = c.post("/device-api/v2/get-bottle", headers=DEV).json()
    assert {e["dispenseTime"] for e in body["config"]} == {80}
    servings = rows(app, "SELECT tenths, round(flow_ml_s, 3) FROM dose_servings WHERE device_id = ? ORDER BY id")
    assert servings == [(65, 27.2), (80, round(27.2 * 0.81, 3))]


def test_dispense_attributed_to_serving_in_force_at_event_time(device) -> None:
    c, app = device
    send(c, (1, 5, T0))
    with app.state.repo.db.connection() as conn:
        dosing_repo.record_serving(conn, DEVICE_ID, 65, 27.2, at=iso(T0 + 100))
        dosing_repo.record_serving(conn, DEVICE_ID, 80, 22.0, at=iso(T0 + 300))
    # Remote dispense ran (T0+200) before this sync's get-bottle (T0+300); double dose (SE 3) at T0+400.
    send(c, (0, 8, T0 + 200), (0, 3, T0 + 400), (0, 9, T0 + 500))
    got = rows(app, "SELECT code, round(est_volume_ml, 3), dose_count, bottle_id IS NOT NULL FROM dispenses"
                    " WHERE device_id = ? ORDER BY device_timestamp")
    assert got == [(8, 176.8, 1, 1), (3, 352.0, 2, 1)]
    with app.state.repo.db.connection() as conn:
        assert dosing_service.get_dosing_view(conn, DEVICE_ID).bottle.est_remaining_ml == pytest.approx(
            1065 - 176.8 - 352.0)


def test_dispense_before_any_serving_falls_back_to_latest(device) -> None:
    c, app = device
    with app.state.repo.db.connection() as conn:
        dosing_repo.record_serving(conn, DEVICE_ID, 70, 25.0, at=iso(T0 + 100))
    send(c, (0, 1, T0))
    assert rows(app, "SELECT est_volume_ml, bottle_id FROM dispenses WHERE device_id = ?") == [(175.0, None)]


def test_locked_get_bottle_is_unchanged_and_serves_nothing(device) -> None:
    c, app = device
    app.state.repo.update_controls(DEVICE_ID, {"dispensing_enabled": False})
    locked = c.post("/device-api/v2/get-bottle", headers=DEV)
    assert locked.status_code == 422
    assert locked.json() == {
        "fields": {},
        "code": "BOTTLE_INSTALLED_NOT_AUTHORIZED",
        "message": "dispensing is locked by the operator",
    }
    assert rows(app, "SELECT count(*) FROM dose_servings WHERE device_id = ?") == [(0,)]

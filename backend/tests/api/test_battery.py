from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.telemetry import BatteryReading
from app.services.battery import project_days_to_replace
from conftest import DEVICE_ID

from .conftest import Api

NOW = datetime.now(timezone.utc)


def _readings(levels_by_day_ago: list[tuple[float, int]]) -> list[BatteryReading]:
    return [BatteryReading((NOW - timedelta(days=d)).isoformat(), level) for d, level in levels_by_day_ago]


def test_projection_is_ols_to_20_percent() -> None:
    # 1 % a day over 6 days, now at 80 %: 60 days to 20 %.
    days, basis = project_days_to_replace(_readings([(6 - d, 86 - d) for d in range(7)]))
    assert days == pytest.approx(60.0) and basis == pytest.approx(6.0)


@pytest.mark.parametrize(("label", "points"), [
    ("under 3 days", [(2, 90), (1, 85), (0, 80)]),
    ("under 2 % change", [(6, 81), (3, 80), (0, 80)]),
    ("rising", [(6, 70), (3, 80), (0, 90)]),
])
def test_not_enough_data(label: str, points: list[tuple[float, int]]) -> None:
    assert project_days_to_replace(_readings(points))[0] is None, label


def test_only_the_last_7_days_count() -> None:
    old_cliff = [(20, 100), (19, 30)]  # a battery swap long ago must not skew the fit
    days, basis = project_days_to_replace(_readings(old_cliff + [(6 - d, 86 - d) for d in range(7)]))
    assert days == pytest.approx(60.0) and basis == pytest.approx(6.0)


def test_no_readings() -> None:
    assert project_days_to_replace([]) == (None, None)


def test_battery_endpoint(api: Api) -> None:
    for days_ago, level in [(40, 99), (6, 86), (3, 83), (0, 80)]:
        api.add_telemetry((NOW - timedelta(days=days_ago)).isoformat(), batteryLevel=level)
    api.add_telemetry(NOW.isoformat(), networkName="no battery field")
    body = api.get(f"/devices/{DEVICE_ID}/battery").json()
    assert [p["level"] for p in body["points"]] == [86, 83, 80]  # 30-day window
    assert body["projection_days_to_20"] == pytest.approx(60.0, rel=1e-3)
    assert body["basis_days"] == pytest.approx(6.0, rel=1e-3)
    assert len(api.get(f"/devices/{DEVICE_ID}/battery", params={"days": 90}).json()["points"]) == 4
    assert api.get(f"/devices/{DEVICE_ID}/battery", params={"days": 91}).status_code == 422


def test_battery_without_data(api: Api) -> None:
    body = api.get(f"/devices/{DEVICE_ID}/battery").json()
    assert body == {"points": [], "projection_days_to_20": None, "basis_days": None}

"""Battery trend (FR-11): readings over a window plus an OLS projection to the 20 % replacement level."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..repositories import telemetry
from ..repositories.telemetry import BatteryReading

REPLACE_AT_LEVEL = 20
PROJECTION_WINDOW = timedelta(days=7)
MIN_BASIS_DAYS = 3.0
MIN_LEVEL_CHANGE = 2
SECONDS_PER_DAY = 86_400.0


@dataclass(frozen=True, slots=True)
class BatteryTrend:
    points: list[BatteryReading]
    projection_days_to_20: float | None
    basis_days: float | None


def project_days_to_replace(readings: list[BatteryReading]) -> tuple[float | None, float | None]:
    """(days until 20 %, basis days) from an OLS fit over the last 7 days of ``readings`` (oldest first).

    Projected only with >= 3 days of basis and >= 2 % change, and only for a falling trend.
    """
    if not readings:
        return None, None
    newest = datetime.fromisoformat(readings[-1].received_at)
    recent = [r for r in readings if newest - datetime.fromisoformat(r.received_at) <= PROJECTION_WINDOW]
    xs = [(datetime.fromisoformat(r.received_at) - newest).total_seconds() / SECONDS_PER_DAY for r in recent]
    ys = [float(r.level) for r in recent]
    basis = xs[-1] - xs[0]
    if basis < MIN_BASIS_DAYS or max(ys) - min(ys) < MIN_LEVEL_CHANGE:
        return None, basis
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)
    if slope >= 0:
        return None, basis
    level_now = mean_y - slope * mean_x  # the fit at x = 0 (the newest reading)
    return max(0.0, (level_now - REPLACE_AT_LEVEL) / -slope), basis


def battery_trend(conn: sqlite3.Connection, device_id: str, days: int, now: datetime | None = None) -> BatteryTrend:
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    readings = telemetry.battery_since(conn, device_id, since.isoformat())
    projection, basis = project_days_to_replace(readings)
    return BatteryTrend(readings, projection, basis)

"""Read side of the device's reported telemetry and raw event batches (written by ``TelemetryService``)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from ._rows import DEFAULT_LIMIT, fetch_page


@dataclass(frozen=True, slots=True)
class TelemetryReport:
    received_at: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BatteryReading:
    received_at: str
    level: int


@dataclass(frozen=True, slots=True)
class EventBatch:
    id: int
    received_at: str
    kind: str
    payload_json: str

    @property
    def payload(self) -> Any:
        return json.loads(self.payload_json)


def latest(conn: sqlite3.Connection, device_id: str) -> TelemetryReport | None:
    """The newest update-device payload (``idx_telemetry_device_ts``)."""
    row = conn.execute(
        "SELECT received_at, payload_json FROM telemetry WHERE device_id = ? ORDER BY received_at DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[1])
    return TelemetryReport(row[0], payload if isinstance(payload, dict) else {})


def battery_since(conn: sqlite3.Connection, device_id: str, since: str) -> list[BatteryReading]:
    """Integer ``batteryLevel`` readings at or after ``since``, oldest first (``idx_telemetry_device_ts``).

    Bounded by the caller's window: one row per sync, at most 96 a day on the Testing preset.
    """
    rows = conn.execute(
        "SELECT received_at, json_extract(payload_json, '$.batteryLevel') FROM telemetry"
        " WHERE device_id = ? AND received_at >= ? ORDER BY received_at",
        (device_id, since),
    )
    return [BatteryReading(at, int(level)) for at, level in rows if isinstance(level, int)]


def events_page(
    conn: sqlite3.Connection, device_id: str, *, limit: int = DEFAULT_LIMIT, before_id: int | None = None
) -> list[EventBatch]:
    """Raw event batches (send-events, get-fw, healthcheck), newest first."""
    return fetch_page(conn, EventBatch, "events", "device_id = ?", (device_id,), limit=limit, before=before_id)

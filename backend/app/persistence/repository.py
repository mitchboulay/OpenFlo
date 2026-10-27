from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from ..db import Database


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Repository:
    def __init__(self, db: Database):
        self.db = db

    # -- devices ---------------------------------------------------------

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def count_devices(self) -> int:
        with self.db.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0])

    # -- telemetry and events -------------------------------------------

    def insert_telemetry(
        self, device_id: str, payload: dict[str, Any], source: str
    ) -> None:
        body = dumps(payload)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO telemetry
                    (device_id, received_at, source, payload_json, payload_sha256)
                VALUES (?, ?, ?, ?, ?)
                """,
                (device_id, utcnow(), source, body, digest),
            )

    def insert_event(self, device_id: str, kind: str, payload: Any) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO events (device_id, received_at, kind, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (device_id, utcnow(), kind, dumps(payload)),
            )

    def insert_qc_report(self, device_id: str, payload: dict[str, Any]) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO qc_reports (device_id, received_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (device_id, utcnow(), dumps(payload)),
            )

    def latest_telemetry(self, device_id: str) -> dict[str, Any] | None:
        with self.db.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM telemetry WHERE device_id=?
                ORDER BY id DESC LIMIT 1
                """,
                (device_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def pending_dispense(self, device_id: str) -> dict[str, Any] | None:
        from ..repositories import dispense_requests  # deferred: the repositories import utcnow from here

        with self.db.connection() as conn:
            row = dispense_requests.pending(conn, device_id)
        return asdict(row) if row else None

    def queue_dispense(self, device_id: str, nonce: int) -> dict[str, Any]:
        from ..repositories import dispense_requests  # deferred: the repositories import utcnow from here

        with self.db.connection() as conn:
            return asdict(dispense_requests.queue(conn, device_id, nonce))

    def take_pending_dispense(self, device_id: str) -> dict[str, Any] | None:
        """Mark the pending request delivered and return it (at most once)."""
        with self.db.connection() as conn:
            row = conn.execute(
                "UPDATE dispense_requests SET delivered_at=? WHERE id = ("
                "SELECT id FROM dispense_requests WHERE device_id=? "
                "AND delivered_at IS NULL AND cancelled_at IS NULL ORDER BY id LIMIT 1"
                ") RETURNING *",
                (utcnow(), device_id),
            ).fetchone()
        return dict(row) if row else None

    # -- operator controls -----------------------------------------------

    def get_controls(self, device_id: str) -> dict[str, Any]:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM device_controls WHERE device_id=?", (device_id,)
            ).fetchone()
        if row is None:
            return {
                "device_id": device_id,
                "dispensing_enabled": False,
                "sync_interval_seconds": None,
                "dose_tenths": None,
                "shift_time_seconds": None,
                "updated_at": None,
                "wake_preset": None,
                "schedules_enabled": False,
                "actor": None,
            }
        controls = dict(row)
        controls["dispensing_enabled"] = bool(controls["dispensing_enabled"])
        controls["schedules_enabled"] = bool(controls["schedules_enabled"])
        return controls

    def update_controls(self, device_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        current = self.get_controls(device_id)
        current.update(changes)
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO device_controls
                    (device_id, dispensing_enabled, sync_interval_seconds, dose_tenths,
                     shift_time_seconds, wake_preset, schedules_enabled, actor, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    dispensing_enabled=excluded.dispensing_enabled,
                    sync_interval_seconds=excluded.sync_interval_seconds,
                    dose_tenths=excluded.dose_tenths,
                    shift_time_seconds=excluded.shift_time_seconds,
                    wake_preset=excluded.wake_preset,
                    schedules_enabled=excluded.schedules_enabled,
                    actor=excluded.actor,
                    updated_at=excluded.updated_at
                """,
                (
                    device_id,
                    int(current["dispensing_enabled"]),
                    current["sync_interval_seconds"],
                    current["dose_tenths"],
                    current["shift_time_seconds"],
                    current["wake_preset"],
                    int(current["schedules_enabled"]),
                    current["actor"],
                    utcnow(),
                ),
            )
        return self.get_controls(device_id)

    def count_telemetry(self) -> int:
        with self.db.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0])

    def count_events(self) -> int:
        with self.db.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    # -- protocol logs ---------------------------------------------------

    def log_protocol(
        self,
        *,
        method: str,
        path: str,
        device_id: str | None,
        status: int,
        request_json: str | None,
        response_json: str | None,
        headers_json: str,
        note: str | None = None,
    ) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO protocol_logs
                    (ts, method, path, device_id, status,
                     request_json, response_json, headers_json, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utcnow(),
                    method,
                    path,
                    device_id,
                    status,
                    request_json,
                    response_json,
                    headers_json,
                    note,
                ),
            )

    def count_logs(self) -> int:
        with self.db.connection() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM protocol_logs").fetchone()[0])

    def recent_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM protocol_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

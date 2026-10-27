"""Build a synthetic, production-shaped pre-002 database: one registered device as it exists before migration 002.

Schema comes from 001 via the runner. The device ID, token digest and payloads are synthetic. Usage: ``python tests/fixtures/make_lab_db.py OUT.db``.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import Database  # noqa: E402
from app.migrations.runner import MIGRATIONS_DIR  # noqa: E402

LAB_DEVICE_ID = "D8256700000A0001"
FIRST_SEEN = "2026-10-26T20:36:34.331206+00:00"
REGISTERED_AT = "2026-10-26T20:36:40.000000+00:00"
FAKE_OTT_SHA256 = "0" * 64


def _seed(conn: sqlite3.Connection) -> None:
    did = LAB_DEVICE_ID
    conn.execute(
        "INSERT INTO devices (device_id, first_seen, last_seen, registered, firmware_version, metadata_json)"
        " VALUES (?, ?, '2026-10-26T23:32:46.332714+00:00', 1, '3.0.64', '{}')",
        (did, FIRST_SEEN),
    )
    conn.execute(
        "INSERT INTO registrations (device_id, ott_sha256, status, remote_addr, created_at)"
        " VALUES (?, ?, 'accepted', '192.168.30.80', ?)",
        (did, FAKE_OTT_SHA256, REGISTERED_AT),
    )
    for minute, battery in ((40, 98), (50, 97), (59, 97)):
        payload = json.dumps({"batteryLevel": battery, "firmwareVersion": "3.0.64"})
        conn.execute(
            "INSERT INTO telemetry (device_id, received_at, source, payload_json, payload_sha256)"
            " VALUES (?, ?, 'update-device', ?, ?)",
            (did, f"2026-10-26T20:{minute}:00+00:00", payload, f"{minute:064d}"),
        )
    for minute, kind in ((41, "send-events"), (42, "get-bottle")):
        conn.execute(
            "INSERT INTO events (device_id, received_at, kind, payload_json) VALUES (?, ?, ?, '{}')",
            (did, f"2026-10-26T21:{minute}:00+00:00", kind),
        )
    for n in range(4):
        conn.execute(
            "INSERT INTO dispenses (device_id, code, device_timestamp, received_at) VALUES (?, 1, ?, ?)",
            (did, 1761510000 + n * 600, f"2026-10-26T22:0{n}:00+00:00"),
        )
    conn.execute(
        "INSERT INTO dispense_requests (device_id, nonce, requested_at, delivered_at)"
        " VALUES (?, 42, '2026-10-26T22:00:00+00:00', '2026-10-26T22:01:00+00:00')",
        (did,),
    )
    conn.execute(
        "INSERT INTO device_controls (device_id, dispensing_enabled, sync_interval_seconds, dose_tenths,"
        " shift_time_seconds, updated_at) VALUES (?, 1, 172800, NULL, 60, '2026-10-26T22:48:22.183930+00:00')",
        (did,),
    )
    conn.execute(
        "INSERT INTO sync_state (device_id, schedule_synced, settings_synced, updated_at)"
        " VALUES (?, 1, 1, '2026-10-26T22:50:00+00:00')",
        (did,),
    )
    conn.execute(
        "INSERT INTO schedules (device_id, timestamp, dose_count, created_at)"
        " VALUES (?, 1761600000, 1, '2026-10-26T22:00:00+00:00')",
        (did,),
    )
    conn.execute(
        "INSERT INTO protocol_logs (ts, method, path, device_id, status, headers_json)"
        " VALUES ('2026-10-26T20:36:34+00:00', 'POST', '/device-api/v2/register', ?, 200, '{}')",
        (did,),
    )


def build_lab_db(path: Path) -> Path:
    """Create the pre-002 lab database at ``path`` (which must not exist) and return it."""
    if path.exists():
        raise FileExistsError(path)
    with tempfile.TemporaryDirectory() as only_001:
        shutil.copy(MIGRATIONS_DIR / "001_baseline.sql", only_001)
        Database(str(path)).init(Path(only_001))
    with closing(sqlite3.connect(path)) as conn, conn:
        _seed(conn)
    return path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_lab_db.py OUT.db")
    print(build_lab_db(Path(sys.argv[1])))

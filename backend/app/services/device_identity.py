"""Identity-flag detection on the device path (FR-13).

Flags are mitigations, not authentication: a device ID is a public identifier, so a second source IP or
changed hardware telemetry only means "someone else may be using this ID". Commands are withheld until
a user acknowledges the flag (``device_policy``).
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..repositories import devices, flags
from ..repositories.devices import DeviceUpdate
from ..repositories.flags import FlagKind


def raise_once(conn: sqlite3.Connection, device_id: str, kind: FlagKind, detail: dict[str, Any], at: str) -> bool:
    """Raise ``kind`` unless an unacknowledged flag of that kind already exists; True when raised."""
    if flags.has_open(conn, device_id, kind):
        return False
    flags.raise_flag(conn, device_id, kind, detail, at)
    return True


def check_telemetry(conn: sqlite3.Connection, device_id: str, payload: dict[str, Any], at: str) -> None:
    """Flag a firmwareVersion/deviceType/pcbVersion change, then store the reported values.

    Values are stored on first sight and after a change, so an acknowledged change is not re-flagged.
    """
    device = devices.get(conn, device_id)
    if device is None:
        return
    metadata: dict[str, Any] = json.loads(device.metadata_json or "{}")
    stored: dict[str, Any] = {
        "firmwareVersion": device.firmware_version,
        "deviceType": metadata.get("deviceType"),
        "pcbVersion": device.pcb_version,
    }
    reported = {key: payload[key] for key in stored if payload.get(key) is not None}
    if "pcbVersion" in reported:
        reported["pcbVersion"] = str(reported["pcbVersion"])
    changed = {
        key: {"stored": stored[key], "reported": value}
        for key, value in reported.items()
        if stored[key] is not None and stored[key] != value
    }
    if changed:
        raise_once(conn, device_id, "telemetry_implausible", {"changed": changed}, at)
    if any(stored[key] != value for key, value in reported.items()):
        devices.update(conn, device_id, _identity_columns(reported, metadata))


def _identity_columns(reported: dict[str, Any], metadata: dict[str, Any]) -> DeviceUpdate:
    changes: DeviceUpdate = {}
    if "firmwareVersion" in reported:
        changes["firmware_version"] = reported["firmwareVersion"]
    if "pcbVersion" in reported:
        changes["pcb_version"] = reported["pcbVersion"]
    if "deviceType" in reported:
        changes["metadata_json"] = json.dumps({**metadata, "deviceType": reported["deviceType"]}, sort_keys=True)
    return changes

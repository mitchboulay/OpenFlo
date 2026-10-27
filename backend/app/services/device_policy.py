"""Command withholding (FR-6, FR-13): what a device may be told to do, independent of the operator controls."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..repositories import devices, flags
from ..repositories.devices import Device

# get-bottle 422 with fields.code BOTTLE_INSTALLED_NOT_AUTHORIZED: the firmware's dispense interlock and the
# ONLY device response that carries "fields" (Critical Constraint 2). Also the operator lock in
# SynchronizationService.bottle_response.
BOTTLE_LOCK_STATUS = 422
BOTTLE_LOCK_BODY: dict[str, Any] = {
    "fields": {},
    "code": "BOTTLE_INSTALLED_NOT_AUTHORIZED",
    "message": "dispensing is locked by the operator",
}


def _commands_allowed(conn: sqlite3.Connection, device: Device) -> bool:
    return device.status == "active" and not flags.has_open(conn, device.device_id)


def may_receive_commands(conn: sqlite3.Connection, device_id: str) -> bool:
    """Active and no unacknowledged identity flag: bottle authorization, remote dispense and schedules allowed."""
    device = devices.get(conn, device_id)
    return device is not None and _commands_allowed(conn, device)


def withholds_bottle(conn: sqlite3.Connection, device_id: str) -> bool:
    """A known device that may not receive commands gets the bottle lock; unknown IDs are answered as unregistered."""
    device = devices.get(conn, device_id)
    return device is not None and not _commands_allowed(conn, device)

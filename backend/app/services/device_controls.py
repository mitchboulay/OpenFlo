"""Operator controls and "Dispense now" (FR-6, FR-10, AD-7). Every change is desired state for the next sync."""
from __future__ import annotations

import logging
import secrets
import sqlite3
from typing import Any, Final

from ..errors import ApiError
from ..persistence.repository import Repository
from ..repositories import devices, dispense_requests, flags
from ..repositories.devices import Device
from ..repositories.dispense_requests import DispenseRequest
from ..repositories.flags import IdentityFlag

logger = logging.getLogger(__name__)

# AD-7: (shift-time, fast-sync-time) per check-in preset. NULL wake_preset = Custom raw seconds.
PRESETS: Final[dict[str, tuple[int, int]]] = {
    "battery_saver": (900, 86_400),
    "balanced": (900, 21_600),
    "responsive": (600, 3_600),
    "testing": (300, 900),
}
WAKE_FIELDS: Final = frozenset({"wake_preset", "sync_interval_seconds", "shift_time_seconds"})
NONCE_MAX = 2**31 - 1  # firmware int; 0 is its boot value


def require_device(conn: sqlite3.Connection, device_id: str) -> Device:
    device = devices.get(conn, device_id)
    if device is None:
        raise ApiError("DEVICE_NOT_FOUND", f"device {device_id} not found", 404)
    return device


def _resolve_wake(current: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Map a preset to its seconds, or mark raw seconds as Custom; then enforce Constraint 4."""
    resolved = dict(changes)
    preset = changes.get("wake_preset")
    if preset is not None:
        if WAKE_FIELDS & (set(changes) - {"wake_preset"}):
            raise ApiError("INVALID_REQUEST", "set wake_preset or raw seconds, not both", 422)
        resolved["shift_time_seconds"], resolved["sync_interval_seconds"] = PRESETS[preset]
    elif WAKE_FIELDS & set(changes):
        resolved["wake_preset"] = None
    interval = resolved.get("sync_interval_seconds", current["sync_interval_seconds"])
    shift = resolved.get("shift_time_seconds", current["shift_time_seconds"])
    if interval is not None and (shift is None or interval <= 2 * shift):
        # shift-time is sent first and the firmware drops fast-sync-time <= 2 x shift-time, silently
        # falling back to 48 h (Constraint 4). The factory shift-time is unknown, so it must be explicit.
        floor = None if shift is None else 2 * shift + 1
        raise ApiError(
            "INTERVAL_TOO_SHORT",
            "sync_interval_seconds must exceed 2 x shift_time_seconds, and shift_time_seconds must be set",
            422,
            {"min_sync_interval_seconds": floor, "shift_time_seconds": shift},
        )
    return resolved


def update_controls(repo: Repository, device_id: str, changes: dict[str, Any], actor: str) -> dict[str, Any]:
    """Apply a partial controls update. Locking cancels a queued dispense (FR-6)."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
    current = repo.get_controls(device_id)
    resolved = _resolve_wake(current, changes) if WAKE_FIELDS & set(changes) else dict(changes)
    controls = repo.update_controls(device_id, {**resolved, "actor": actor})
    if resolved.get("dispensing_enabled") is False:
        with repo.db.connection() as conn:
            dispense_requests.cancel_pending(conn, device_id)
    logger.info("controls device=%s fields=%s actor=%s", device_id, sorted(resolved), actor)
    return controls


def _new_nonce(last: DispenseRequest | None) -> int:
    """A non-zero nonce that differs from the last delivered one (the firmware ignores a repeat)."""
    nonce = secrets.randbelow(NONCE_MAX - 1) + 1
    while last is not None and nonce == last.nonce:
        nonce = secrets.randbelow(NONCE_MAX - 1) + 1
    return nonce


def queue_dispense(repo: Repository, device_id: str, actor: str) -> DispenseRequest:
    """Queue one dispense for the next sync; an already pending request is returned unchanged."""
    dispensing_enabled = repo.get_controls(device_id)["dispensing_enabled"]
    with repo.db.connection() as conn:
        device = require_device(conn, device_id)
        if device.status != "active":
            raise ApiError("DEVICE_NOT_ACTIVE", f"device is {device.status}", 409)
        if not dispensing_enabled:
            raise ApiError("DISPENSING_LOCKED", "dispensing is locked for this device", 409)
        if flags.has_open(conn, device_id):
            raise ApiError("IDENTITY_FLAGGED", "acknowledge the device's identity flag first", 409)
        request = dispense_requests.queue(conn, device_id, _new_nonce(dispense_requests.last_delivered(conn, device_id)))
    logger.info("dispense queued device=%s request=%s actor=%s", device_id, request.id, actor)
    return request


def cancel_dispense(repo: Repository, device_id: str, actor: str) -> DispenseRequest:
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        request = dispense_requests.pending(conn, device_id)
        if request is None:
            raise ApiError("NO_PENDING_DISPENSE", "no dispense is waiting for this device", 409)
        dispense_requests.cancel_pending(conn, device_id)
        cancelled = dispense_requests.get(conn, request.id)
    assert cancelled is not None
    logger.info("dispense cancelled device=%s request=%s actor=%s", device_id, request.id, actor)
    return cancelled


def ack_flag(conn: sqlite3.Connection, flag_id: int, actor: str) -> IdentityFlag:
    """Acknowledge an identity flag (FR-13); an acknowledged flag keeps its first ack."""
    flag = flags.ack(conn, flag_id, actor)
    if flag is None:
        raise ApiError("FLAG_NOT_FOUND", f"flag {flag_id} not found", 404)
    logger.info("identity flag acked id=%s device=%s actor=%s", flag_id, flag.device_id, actor)
    return flag

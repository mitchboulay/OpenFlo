"""Device edits and two-phase retire (FR-2)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..errors import ApiError
from ..persistence.repository import Repository, utcnow
from ..repositories import devices, dispense_requests, profiles
from ..repositories.devices import Device, DeviceUpdate
from . import dosing_service, scheduling
from .device_controls import require_device
from .homes import require_home

logger = logging.getLogger(__name__)


def _leave_home_liquid(conn: sqlite3.Connection, device: Device, actor: str) -> None:
    """A home's custom liquid stays with the home: a moved device falls back to the standard cartridge dose."""
    if dosing_service.current_profile(conn, device.device_id).system:
        return
    standard = profiles.get_system(conn, profiles.STANDARD)
    assert standard is not None
    current = dosing_service.ensure_dosing(conn, device.device_id)
    dosing_service.set_dosing(conn, device.device_id, standard.id, dose_ml=standard.default_dose_ml,
                              compensation_enabled=current.compensation_enabled, actor=actor)


def update_device(conn: sqlite3.Connection, device_id: str, changes: dict[str, Any], actor: str) -> Device:
    """Name, location, install date and home. A move re-expands schedules in the new home's timezone."""
    device = require_device(conn, device_id)
    update: DeviceUpdate = {}
    if "name" in changes:
        update["name"] = changes["name"].strip()
    if "location" in changes:
        update["location"] = changes["location"].strip() if changes["location"] is not None else None
    if "installed_at" in changes:
        installed: datetime = changes["installed_at"]
        aware = installed if installed.tzinfo else installed.replace(tzinfo=timezone.utc)
        update["installed_at"] = aware.astimezone(timezone.utc).isoformat()
    if "home_id" in changes and changes["home_id"] != device.home_id:
        require_home(conn, changes["home_id"])
        update["home_id"] = changes["home_id"]
    updated = devices.update(conn, device_id, update)
    assert updated is not None
    if "home_id" in update:
        _leave_home_liquid(conn, updated, actor)
        scheduling.expand(conn, device_id)
    logger.info("device updated id=%s fields=%s actor=%s", device_id, sorted(update), actor)
    return updated


def claim(repo: Repository, device_id: str, home_id: int, name: str, location: str | None, actor: str) -> Device:
    """Adopt an unclaimed device into a home (FR-5); 409 NOT_UNCLAIMED. Dispensing starts off."""
    with repo.db.connection() as conn:
        device = require_device(conn, device_id)
        if device.status != "unclaimed":
            raise ApiError("NOT_UNCLAIMED", f"device {device_id} is {device.status}, not unclaimed", 409)
        require_home(conn, home_id)
        claimed = devices.update(conn, device_id, {
            "status": "active", "home_id": home_id, "name": name.strip(),
            "location": location.strip() if location is not None else None, "installed_at": utcnow(),
        })
    assert claimed is not None
    if repo.get_controls(device_id)["dispensing_enabled"]:
        repo.update_controls(device_id, {"dispensing_enabled": False, "actor": actor})
    logger.info("device claimed id=%s home=%d actor=%s", device_id, home_id, actor)
    return claimed


def complete_retire(conn: sqlite3.Connection, device_id: str) -> None:
    devices.update(conn, device_id, {"status": "retired"})
    dispense_requests.cancel_pending(conn, device_id)


def complete_if_requested(conn: sqlite3.Connection, device_id: str) -> bool:
    """Device path: retire a device whose retire is pending, as its empty schedule is served; True when done."""
    device = devices.get(conn, device_id)
    if device is None or device.retire_requested_at is None or device.status == "retired":
        return False
    complete_retire(conn, device_id)
    logger.info("retire completed device=%s (empty schedule served)", device_id)
    return True


def retire(repo: Repository, device_id: str, force: bool, actor: str) -> bool:
    """Phase 1 of retire; True when the device is retired now, False while it must first fetch ``[]``.

    Nothing on the device (or ``force``) retires immediately. Otherwise schedules pause: a retiring device
    should hold ``[]``, so the next update-device reports ``isScheduleSynced:false`` and the next get-schedule
    serves ``[]`` and completes the retire.
    """
    with repo.db.connection() as conn:
        device = require_device(conn, device_id)
        if device.status == "retired":
            return True
        if device.retire_requested_at is not None and not force:
            return False  # already waiting for the device to fetch its empty schedule
        must_wait = not force and scheduling.has_served_schedule(conn, device_id)
        if must_wait:
            devices.update(conn, device_id, {"retire_requested_at": utcnow()})
        else:
            complete_retire(conn, device_id)
    logger.info("retire device=%s force=%s pending=%s actor=%s", device_id, force, must_wait, actor)
    return not must_wait

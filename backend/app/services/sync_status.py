"""Sync honesty (FR-14): when the device last synced, when it is next expected, and what it has not received.

A change counts as delivered only once a sync *started* after it, so a change made mid-sync stays pending
until the next one: the UI never shows "Applied" early.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from ..repositories import dispense_requests, syncs
from ..repositories import dosing as dosing_repo
from ..repositories.devices import Device
from ..repositories.syncs import DeviceSync
from . import scheduling
from .schedule_expansion import FIRMWARE_DEFAULT_INTERVAL_S

SYSTEM_ACTOR = "system"

PendingKind = Literal["controls", "dose", "dispense", "schedule", "retire"]


@dataclass(frozen=True, slots=True)
class PendingChange:
    kind: PendingKind
    since: str


@dataclass(frozen=True, slots=True)
class SyncStatus:
    last_sync: DeviceSync | None
    next_expected_sync: str | None
    pending: list[PendingChange]
    next_dose_at: str | None


def _delivered(changed_at: str, last_sync: DeviceSync | None) -> bool:
    return last_sync is not None and datetime.fromisoformat(last_sync.started_at) > datetime.fromisoformat(changed_at)


def next_expected_sync(last_sync: DeviceSync | None, interval_s: int | None) -> str | None:
    """Last sync start + check-in interval (the timer wake, ignoring schedules)."""
    if last_sync is None:
        return None
    start = datetime.fromisoformat(last_sync.started_at)
    return (start + timedelta(seconds=interval_s or FIRMWARE_DEFAULT_INTERVAL_S)).isoformat()


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _schedule_times(conn: sqlite3.Connection, device_id: str,
                    last_sync: DeviceSync | None, timer_wake: str | None) -> tuple[str | None, str | None]:
    """(next dose on the device, next expected sync): a scheduled dose pre-wakes the device 2 x shift-time early
    (FUN_40096da4), which can come before the timer wake (FR-14)."""
    entry = scheduling.next_served(conn, device_id)
    if entry is None or last_sync is None:
        return (_iso(entry.timestamp) if entry else None), timer_wake
    prewake = datetime.fromtimestamp(entry.timestamp - 2 * scheduling.context(conn, device_id).shift_s, timezone.utc)
    if prewake <= datetime.fromisoformat(last_sync.started_at) or timer_wake is None:
        return _iso(entry.timestamp), timer_wake
    return _iso(entry.timestamp), min(prewake, datetime.fromisoformat(timer_wake)).isoformat()


def _pending(conn: sqlite3.Connection, device: Device, controls: dict[str, Any],
             last_sync: DeviceSync | None) -> list[PendingChange]:
    found: list[PendingChange] = []
    # Lock, check-in preset and schedules switch reach the device together at its next sync.
    if controls["updated_at"] and controls["actor"] and not _delivered(controls["updated_at"], last_sync):
        found.append(PendingChange("controls", controls["updated_at"]))
    # A dose is delivered by a get-bottle 200 served after the change; a system default is not a change.
    dosing = dosing_repo.get(conn, device.device_id)
    if dosing is not None and dosing.actor != SYSTEM_ACTOR:
        serving = dosing_repo.latest_serving(conn, device.device_id)
        if serving is None or datetime.fromisoformat(serving.served_at) < datetime.fromisoformat(dosing.updated_at):
            found.append(PendingChange("dose", dosing.updated_at))
    request = dispense_requests.pending(conn, device.device_id)
    if request is not None:
        found.append(PendingChange("dispense", request.requested_at))
    # The schedule the device should hold (rules, pause, flags, retire) differs from the one last served.
    schedule_since = scheduling.pending_since(conn, device.device_id)
    if schedule_since is not None:
        found.append(PendingChange("schedule", schedule_since))
    if device.retire_requested_at and device.status != "retired":
        found.append(PendingChange("retire", device.retire_requested_at))
    return found


def sync_status(conn: sqlite3.Connection, device: Device, controls: dict[str, Any]) -> SyncStatus:
    last_sync = syncs.latest(conn, device.device_id)
    timer_wake = next_expected_sync(last_sync, controls["sync_interval_seconds"])
    next_dose, next_sync = _schedule_times(conn, device.device_id, last_sync, timer_wake)
    return SyncStatus(last_sync, next_sync, _pending(conn, device, controls, last_sync), next_dose)

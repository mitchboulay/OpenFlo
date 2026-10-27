from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..persistence.repository import Repository, utcnow
from ..repositories import bottles, dispenses, profiles
from ..repositories import dosing as dosing_repo
from . import dosing as engine
from . import dosing_service
from . import device_identity
from . import scheduling

# send-events items: status 0 resolves through the firmware's SE_* table, status 1 through EE_*.
SE_STATUS = 0
EE_STATUS = 1
# SE codes 1/2/3/8 are the dispense-success events (Mission 009 prep, bottle research); 3 is a double dose.
DISPENSE_EVENT_CODES = frozenset({1, 2, 3, 8})
# A scheduled dose reports SE 1 (single) or SE 3 (double); these fire the matching schedule entry (FR-9).
SCHEDULE_FIRED_CODES = frozenset({1, 3})
DOUBLE_DOSE_CODE = 3
EE_NEW_BOTTLE_INSTALLED = 5
EE_BOTTLE_EJECTED = 6
# Bottle lifecycle events after which the device's schedule is re-served (AD-6): new, ejected, and EE 7.
SCHEDULE_RESET_BOTTLE_CODES = frozenset({EE_NEW_BOTTLE_INSTALLED, EE_BOTTLE_EJECTED, 7})


@dataclass(frozen=True, slots=True)
class DeviceEvent:
    status: int
    code: int
    timestamp: int | None  # device epoch seconds

    @property
    def at(self) -> str | None:
        """The device time as an ISO UTC string comparable with server timestamps; None when absent or invalid."""
        if self.timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(self.timestamp, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None


def device_events(payload: Any) -> list[DeviceEvent]:
    """Well-formed ``send-events`` items in device-time order (items without a time keep their order, last)."""
    items = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    found = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status, code, ts = item.get("status"), item.get("code"), item.get("timestamp")
        if type(status) is int and type(code) is int:
            found.append(DeviceEvent(status, code, ts if type(ts) is int else None))
    return sorted(found, key=lambda e: (e.timestamp is None, e.timestamp or 0))


def _record_dispense(conn: sqlite3.Connection, device_id: str, event: DeviceEvent) -> None:
    """Attribute the dispense to the open bottle and the serving in force at its device time (AD-5).

    A remote dispense runs from an update-device response before that sync's get-bottle, so it belongs to the
    previous serving; with no serving at or before the event the latest one is the best estimate.
    """
    at = event.at
    serving = (dosing_repo.latest_serving(conn, device_id, at) if at else None) or dosing_repo.latest_serving(
        conn, device_id)
    dose_count = 2 if event.code == DOUBLE_DOSE_CODE else 1
    volume = engine.est_volume(serving.flow_ml_s, serving.tenths, dose_count) if serving else None
    bottle = bottles.open_for_device(conn, device_id)
    dispenses.insert(conn, device_id, event.code, event.timestamp, bottle_id=bottle.id if bottle else None,
                     est_volume_ml=volume, dose_count=dose_count)


def _bottle_ejected(conn: sqlite3.Connection, device_id: str, at: str) -> None:
    current = bottles.open_for_device(conn, device_id)
    # A bottle opened at or after this eject is newer than it (a resent or late batch).
    if current is not None and current.started_at < at:
        bottles.close_open(conn, device_id, "ejected", at)


def _bottle_installed(conn: sqlite3.Connection, device_id: str, at: str) -> None:
    current = bottles.open_for_device(conn, device_id)
    if current is not None and current.started_at >= at:
        return  # already recorded (resent batch) or superseded by a newer bottle
    profile = dosing_service.current_profile(conn, device_id)
    # FR-8: a standard cartridge starts full; any other liquid waits for "Set the level".
    standard = profile.system and profile.slug == profiles.STANDARD
    dosing_service.install_bottle(conn, device_id, profile.capacity_ml if standard else None, reason="replaced", at=at)


def _apply_schedule(conn: sqlite3.Connection, device_id: str, event: DeviceEvent) -> None:
    if event.status == SE_STATUS and event.code in SCHEDULE_FIRED_CODES and event.timestamp is not None:
        scheduling.record_fired(conn, device_id, event.timestamp, event.at or utcnow())
    elif event.status == EE_STATUS and event.code in SCHEDULE_RESET_BOTTLE_CODES:
        scheduling.reset_served(conn, device_id)


def _apply(conn: sqlite3.Connection, device_id: str, event: DeviceEvent) -> None:
    _apply_schedule(conn, device_id, event)
    if event.status == SE_STATUS and event.code in DISPENSE_EVENT_CODES:
        _record_dispense(conn, device_id, event)
    elif event.status == EE_STATUS and event.code == EE_BOTTLE_EJECTED:
        _bottle_ejected(conn, device_id, event.at or utcnow())
    elif event.status == EE_STATUS and event.code == EE_NEW_BOTTLE_INSTALLED:
        _bottle_installed(conn, device_id, event.at or utcnow())


class TelemetryService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def ingest_update(self, device_id: str, payload: dict[str, Any]) -> None:
        self.repo.insert_telemetry(device_id, payload, "cloud")
        with self.repo.db.connection() as conn:
            device_identity.check_telemetry(conn, device_id, payload, utcnow())

    def record_event(self, device_id: str, kind: str, payload: Any) -> None:
        self.repo.insert_event(device_id, kind, payload)
        if kind != "send-events":
            return
        # One transaction: a bottle change and the dispenses around it land together or not at all.
        with self.repo.db.connection() as conn:
            for event in device_events(payload):
                _apply(conn, device_id, event)
            # FR-9: missed is decided only now, once the device has reported what it dispensed.
            scheduling.after_ingest(conn, device_id)

    def record_qc_report(self, device_id: str, payload: dict[str, Any]) -> None:
        self.repo.insert_qc_report(device_id, payload)

"""Read models for devices and homes: everything one device card or detail page shows, in one transaction."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Literal

from ..persistence.repository import Repository
from ..repositories._rows import MAX_LIMIT
from ..repositories import devices, dispense_requests, dispenses, flags, homes, telemetry
from ..repositories.devices import Device
from ..repositories.dispense_requests import DispenseRequest
from ..repositories.flags import IdentityFlag
from ..repositories.homes import Home
from ..repositories.telemetry import TelemetryReport
from . import dosing_service
from .device_controls import require_device
from .dosing_service import DosingView
from .homes import require_home
from .sync_status import SyncStatus, sync_status

ATTENTION_GUIDANCE = frozenset({"refill_soon", "refill_now"})
# Bounded per device: a flag is raised at most once per kind until acknowledged.
OPEN_FLAGS_LIMIT = 50


@dataclass(frozen=True, slots=True)
class DispenseRequestView:
    request: DispenseRequest
    confirmed_at: str | None


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    device: Device
    telemetry: TelemetryReport | None
    controls: dict[str, Any]
    dosing: DosingView
    sync: SyncStatus
    open_flags: list[IdentityFlag]
    pending_dispense: DispenseRequestView | None
    last_delivered_dispense: DispenseRequestView | None

    @property
    def guidance(self) -> str:
        return self.dosing.bottle.guidance if self.dosing.bottle else "unknown"

    @property
    def needs_attention(self) -> bool:
        return bool(self.open_flags) or self.guidance in ATTENTION_GUIDANCE


@dataclass(frozen=True, slots=True)
class HomeSnapshot:
    home: Home
    device_count: int
    attention_count: int

    @property
    def summary(self) -> Literal["ok", "attention", "empty"]:
        if self.device_count == 0:
            return "empty"
        return "attention" if self.attention_count else "ok"


def dispense_view(conn: sqlite3.Connection, request: DispenseRequest | None) -> DispenseRequestView | None:
    """``confirmed_at`` = the first SE dispense received after delivery.

    ponytail: the firmware's event carries no nonce, so a scheduled dose landing in the same window would also
    confirm it; good enough while schedules (B3.1) and remote dispenses rarely overlap.
    """
    if request is None:
        return None
    confirmed = None
    if request.delivered_at is not None:
        first = dispenses.first_received_since(conn, request.device_id, request.delivered_at)
        confirmed = first.received_at if first else None
    return DispenseRequestView(request, confirmed)


def _snapshot(conn: sqlite3.Connection, repo: Repository, device: Device) -> DeviceSnapshot:
    device_id = device.device_id
    controls = repo.get_controls(device_id)
    return DeviceSnapshot(
        device=device,
        telemetry=telemetry.latest(conn, device_id),
        controls=controls,
        dosing=dosing_service.get_dosing_view(conn, device_id),
        sync=sync_status(conn, device, controls),
        open_flags=flags.list_open(conn, device_id, limit=OPEN_FLAGS_LIMIT),
        pending_dispense=dispense_view(conn, dispense_requests.pending(conn, device_id)),
        last_delivered_dispense=dispense_view(conn, dispense_requests.last_delivered(conn, device_id)),
    )


def device_snapshot(repo: Repository, device_id: str) -> DeviceSnapshot:
    with repo.db.connection() as conn:
        return _snapshot(conn, repo, require_device(conn, device_id))


def home_device_snapshots(
    repo: Repository, home_id: int, *, limit: int, before_id: str | None
) -> list[DeviceSnapshot]:
    """One page of a home's non-retired devices.

    ponytail: about a dozen indexed in-process SQLite reads per device (no network round trips); batch them
    if a page of 500 devices ever misses the 200 ms p95.
    """
    with repo.db.connection() as conn:
        require_home(conn, home_id)
        page = devices.list_by_home(conn, home_id, limit=limit, before_id=before_id)
        return [_snapshot(conn, repo, device) for device in page]


def _attention_count(repo: Repository, home_id: int) -> int:
    attention, before = 0, None
    while True:
        page = home_device_snapshots(repo, home_id, limit=MAX_LIMIT, before_id=before)
        attention += sum(1 for snap in page if snap.needs_attention)
        if len(page) < MAX_LIMIT:
            return attention
        before = page[-1].device.device_id


def home_snapshots(repo: Repository, *, limit: int, before_id: int | None) -> list[HomeSnapshot]:
    """A page of homes with device and attention counts (same per-device ceiling as above)."""
    with repo.db.connection() as conn:
        page = homes.list_homes(conn, limit=limit, before_id=before_id)
        counts = homes.non_retired_device_counts(conn, [home.id for home in page])
    return [HomeSnapshot(home, counts[home.id], _attention_count(repo, home.id)) for home in page]

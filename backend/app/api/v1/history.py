"""Battery trend (FR-11) and device history pages."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from .. import schemas
from ...repositories.dispenses import Dispense
from ...repositories.syncs import DeviceSync
from ...services import battery, device_history
from ...services.device_controls import require_device
from ...services.device_history import HistoryKind
from .common import DEFAULT_LIMIT, Limit, RepoDep

router = APIRouter(tags=["history"])

MAX_BATTERY_DAYS = 90


@router.get("/devices/{device_id}/battery", response_model=schemas.Battery)
def get_battery(
    device_id: str, repo: RepoDep, days: Annotated[int, Query(ge=1, le=MAX_BATTERY_DAYS)] = 30
) -> schemas.Battery:
    """Readings over ``days`` and the days until 20 % (OLS over 7 days; null without enough data)."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        trend = battery.battery_trend(conn, device_id, days)
    return schemas.Battery(
        points=[schemas.BatteryPoint(at=p.received_at, level=p.level) for p in trend.points],
        projection_days_to_20=trend.projection_days_to_20,
        basis_days=trend.basis_days,
    )


def _item(row: device_history.HistoryRow) -> schemas.DispenseItem | schemas.EventItem | schemas.SyncItem:
    if isinstance(row, Dispense):
        return schemas.DispenseItem(
            id=row.id, code=row.code, device_timestamp=row.device_timestamp, received_at=row.received_at,
            est_volume_ml=row.est_volume_ml, dose_count=row.dose_count,
        )
    if isinstance(row, DeviceSync):
        return schemas.SyncItem(
            id=row.id, started_at=row.started_at, ended_at=row.ended_at, request_count=row.request_count,
            source_ip=row.source_ip,
        )
    return schemas.EventItem(id=row.id, received_at=row.received_at, kind=row.kind, payload=row.payload)


@router.get("/devices/{device_id}/history", response_model=schemas.History)
def get_history(
    device_id: str, kind: HistoryKind, repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: int | None = None
) -> schemas.History:
    """One page, newest first; pass ``next_before_id`` back as ``before_id`` for the next page."""
    with repo.db.connection() as conn:
        page = device_history.history(conn, device_id, kind, limit=limit, before_id=before_id)
    items = [_item(row) for row in page.items]
    return schemas.History(kind=page.kind, items=items, next_before_id=page.next_before_id)  # type: ignore[arg-type]

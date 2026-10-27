"""Device history pages (dispenses, raw event batches, syncs), newest first with a ``before_id`` cursor."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal, Union

from ..repositories import dispenses, syncs, telemetry
from ..repositories.dispenses import Dispense
from ..repositories.syncs import DeviceSync
from ..repositories.telemetry import EventBatch
from .device_controls import require_device

HistoryKind = Literal["dispenses", "events", "syncs"]
HistoryRow = Union[Dispense, EventBatch, DeviceSync]


@dataclass(frozen=True, slots=True)
class HistoryPage:
    kind: HistoryKind
    items: list[HistoryRow]
    next_before_id: int | None


def history(
    conn: sqlite3.Connection, device_id: str, kind: HistoryKind, *, limit: int, before_id: int | None
) -> HistoryPage:
    require_device(conn, device_id)
    items: list[HistoryRow]
    if kind == "dispenses":
        items = list(dispenses.list_for_device(conn, device_id, limit=limit, before_id=before_id))
    elif kind == "events":
        items = list(telemetry.events_page(conn, device_id, limit=limit, before_id=before_id))
    else:
        items = list(syncs.list_recent(conn, device_id, limit=limit, before_id=before_id))
    # A full page may have more behind it; the cursor is the last (oldest) id returned.
    next_before_id = items[-1].id if len(items) == limit else None
    return HistoryPage(kind, items, next_before_id)

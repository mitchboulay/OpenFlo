"""Request and response models for schedules (FR-9, API Specification ``Rule`` and ``Entry``)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .schemas import Model, Timestamp

RuleKind = Literal["daily", "weekly", "interval", "once"]
EntryStatus = Literal["pending", "served", "fired", "missed", "cleared"]
DoseCount = Literal[1, 2]
LOCAL_TIME = r"^([01]\d|2[0-3]):[0-5]\d$"
DAYS = "Bitmask of weekdays, bit 0 = Monday"


class RuleCreate(Model):
    kind: RuleKind
    local_time: str | None = Field(None, pattern=LOCAL_TIME, description="HH:MM in the home timezone")
    days_mask: int | None = Field(None, ge=1, le=127, description=DAYS)
    interval_hours: int | None = Field(None, ge=6, le=720)
    at: datetime | None = Field(None, description="once: the dose time; interval: the first dose (default now). "
                                                  "A time without an offset is UTC.")
    dose_count: DoseCount = 1
    enabled: bool = True


class RuleUpdate(Model):
    kind: RuleKind = Field(None)
    local_time: str | None = Field(None, pattern=LOCAL_TIME)
    days_mask: int | None = Field(None, ge=1, le=127, description=DAYS)
    interval_hours: int | None = Field(None, ge=6, le=720)
    at: datetime | None = Field(None)
    dose_count: DoseCount = Field(None)
    enabled: bool = Field(None)


class Rule(Model):
    id: int
    kind: RuleKind
    local_time: str | None
    days_mask: int | None
    interval_hours: int | None
    at: Timestamp | None
    dose_count: DoseCount
    enabled: bool
    summary: str


class Entry(Model):
    id: int
    at: Timestamp
    dose_count: DoseCount
    status: EntryStatus = Field(description="pending = waiting for device, served = on device, fired = dispensed")
    reason: Literal["too_soon", "paused"] | None
    rule_ids: list[int]


class Schedule(Model):
    rules: list[Rule]
    upcoming: list[Entry]

"""Pure schedule-rule expansion (FR-9, AD-6): rules in the home timezone -> at most 33 UTC epoch entries.

Wall-clock rules (daily, weekly) are resolved per local date with ``zoneinfo``, so 02:30 stays 02:30 across DST.
A time that does not exist on a spring-forward date resolves with the pre-transition offset (02:30 -> 03:30
EDT); an ambiguous fall-back time takes its first occurrence. Interval rules count elapsed hours from their
anchor, and once rules are a single instant.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from ..repositories.schedules import ScheduleRule

# The firmware's schedule table holds 33 entries (0x21, FUN_40097504).
MAX_ENTRIES: Final = 33
MIN_HORIZON_S: Final = 14 * 86_400
HORIZON_SYNC_MULTIPLE: Final = 3
# The firmware's own check-in interval when no fast-sync-time was ever sent (Constraint 4).
FIRMWARE_DEFAULT_INTERVAL_S: Final = 172_800
WEEKDAYS: Final = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True, slots=True)
class PlannedEntry:
    timestamp: int
    dose_count: int
    rule_ids: tuple[int, ...]


def horizon_seconds(sync_interval_s: int | None) -> int:
    """max(14 d, 3 x check-in interval): the device sees every dose before its next scheduled check-in."""
    interval = sync_interval_s or FIRMWARE_DEFAULT_INTERVAL_S
    return max(MIN_HORIZON_S, HORIZON_SYNC_MULTIPLE * interval)


def _local_time(rule: ScheduleRule) -> time:
    assert rule.local_time is not None
    hour, minute = rule.local_time.split(":")
    return time(int(hour), int(minute))


def _wall_clock(rule: ScheduleRule, tz: ZoneInfo, start: int, end: int) -> Iterator[int]:
    at = _local_time(rule)
    day = datetime.fromtimestamp(start, tz).date() - timedelta(days=1)
    last: date = datetime.fromtimestamp(end, tz).date() + timedelta(days=1)
    while day <= last:
        if rule.kind == "daily" or (rule.days_mask or 0) & (1 << day.weekday()):
            ts = int(datetime.combine(day, at, tzinfo=tz).timestamp())
            if start < ts <= end:
                yield ts
        day += timedelta(days=1)


def _interval(rule: ScheduleRule, start: int, end: int) -> Iterator[int]:
    assert rule.interval_hours is not None and rule.at_epoch is not None
    step = rule.interval_hours * 3600
    k = max(0, (start - rule.at_epoch) // step + 1)
    ts = rule.at_epoch + k * step
    while ts <= end:
        if ts > start:
            yield ts
        ts += step


def occurrences(rule: ScheduleRule, tz: ZoneInfo, start: int, end: int) -> Iterator[int]:
    """The rule's dose times in ``(start, end]``, ascending."""
    if rule.kind in ("daily", "weekly"):
        yield from _wall_clock(rule, tz, start, end)
    elif rule.kind == "interval":
        yield from _interval(rule, start, end)
    elif rule.at_epoch is not None and start < rule.at_epoch <= end:
        yield rule.at_epoch


def plan(rules: Iterable[ScheduleRule], tz: ZoneInfo, now: int, sync_interval_s: int | None) -> list[PlannedEntry]:
    """Enabled rules over the horizon, merged per timestamp (dose_count = max, all rules linked), capped at 33."""
    end = now + horizon_seconds(sync_interval_s)
    merged: dict[int, tuple[int, list[int]]] = {}
    for rule in rules:
        if not rule.enabled:
            continue
        for ts in occurrences(rule, tz, now, end):
            dose, ids = merged.get(ts, (0, []))
            merged[ts] = (max(dose, rule.dose_count), [*ids, rule.id])
    return [PlannedEntry(ts, merged[ts][0], tuple(sorted(merged[ts][1]))) for ts in sorted(merged)[:MAX_ENTRIES]]


def schedule_hash(items: Iterable[tuple[int, int]]) -> str:
    """Content hash of a served ``(timestamp, doseCount)`` set; drives ``isScheduleSynced``."""
    body = json.dumps(sorted(items), separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


EMPTY_HASH: Final = schedule_hash([])


def summary(rule: ScheduleRule, tz: ZoneInfo) -> str:
    """Plain language, in the home timezone: "Every Mon, Wed at 09:00 · double dose"."""
    if rule.kind == "daily":
        text = f"Every day at {rule.local_time}"
    elif rule.kind == "weekly":
        days = [name for bit, name in enumerate(WEEKDAYS) if (rule.days_mask or 0) & (1 << bit)]
        text = f"Every {', '.join(days)} at {rule.local_time}"
    elif rule.kind == "interval":
        text = f"Every {rule.interval_hours} hours"
    else:
        assert rule.at_epoch is not None
        text = f"Once on {datetime.fromtimestamp(rule.at_epoch, tz):%Y-%m-%d at %H:%M}"
    return f"{text} · double dose" if rule.dose_count == 2 else text

"""Schedule rules for the management API (FR-9): validation, CRUD, and the upcoming list.

Every change re-expands the device's entries in the same transaction, so the next update-device sees a new
schedule hash and reports ``isScheduleSynced:false``.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Final

from ..errors import ApiError
from ..repositories import schedules
from ..repositories.schedules import RuleFields, RuleKind, ScheduleEntry, ScheduleRule
from . import scheduling
from .device_controls import require_device
from .schedule_expansion import summary

logger = logging.getLogger(__name__)

MAX_RULES_PER_DEVICE: Final = 20
UPCOMING_LIMIT: Final = 10
# ponytail: the upcoming list starts a day back so a just-fired or missed dose stays visible; a paged history
# endpoint can replace the lookback if anyone needs older entries.
UPCOMING_LOOKBACK_S: Final = 86_400
KIND_FIELDS: Final[dict[str, frozenset[str]]] = {
    "daily": frozenset({"local_time"}),
    "weekly": frozenset({"local_time", "days_mask"}),
    "interval": frozenset({"interval_hours", "at_epoch"}),
    "once": frozenset({"at_epoch"}),
}
REQUIRED_FIELDS: Final[dict[str, frozenset[str]]] = {**KIND_FIELDS, "interval": frozenset({"interval_hours"})}
SHAPE_FIELDS: Final = frozenset({"local_time", "days_mask", "interval_hours", "at_epoch"})


@dataclass(frozen=True, slots=True)
class RuleView:
    rule: ScheduleRule
    summary: str


@dataclass(frozen=True, slots=True)
class EntryView:
    entry: ScheduleEntry
    rule_ids: list[int]


@dataclass(frozen=True, slots=True)
class ScheduleView:
    rules: list[RuleView]
    upcoming: list[EntryView]


def _invalid(message: str) -> ApiError:
    return ApiError("SCHEDULE_INVALID", message, 422)


def validate(fields: RuleFields, now: int) -> RuleFields:
    """Cross-field rules per kind (ranges are checked by the request schema); an interval anchors at now."""
    kind = fields["kind"]
    present = {name for name in SHAPE_FIELDS if fields.get(name) is not None}
    missing = REQUIRED_FIELDS[kind] - present
    extra = present - KIND_FIELDS[kind]
    if missing:
        raise _invalid(f"a {kind} rule needs {', '.join(sorted(missing))}")
    if extra:
        raise _invalid(f"a {kind} rule does not take {', '.join(sorted(extra))}")
    checked = RuleFields(**fields)
    if kind == "interval" and checked.get("at_epoch") is None:
        checked["at_epoch"] = now
    if kind == "once" and (checked.get("at_epoch") or 0) <= now:
        raise _invalid("a once rule must be in the future")
    return checked


def _require_rule(conn: sqlite3.Connection, rule_id: int) -> ScheduleRule:
    rule = schedules.get_rule(conn, rule_id)
    if rule is None:
        raise ApiError("RULE_NOT_FOUND", f"schedule rule {rule_id} not found", 404)
    return rule


def _view(conn: sqlite3.Connection, rule: ScheduleRule) -> RuleView:
    return RuleView(rule, summary(rule, scheduling.context(conn, rule.device_id).tz))


def create_rule(conn: sqlite3.Connection, device_id: str, fields: RuleFields, actor: str) -> RuleView:
    device = require_device(conn, device_id)
    if device.status == "retired":
        raise ApiError("DEVICE_NOT_ACTIVE", "device is retired", 409)
    if len(schedules.list_rules(conn, device_id)) >= MAX_RULES_PER_DEVICE:
        raise _invalid(f"a device has at most {MAX_RULES_PER_DEVICE} rules")
    now = scheduling.now_epoch()
    rule = schedules.create_rule(conn, device_id, validate(fields, now), actor)
    scheduling.expand(conn, device_id, now)
    logger.info("schedule rule created id=%s device=%s kind=%s actor=%s", rule.id, device_id, rule.kind, actor)
    return _view(conn, rule)


def _merged(rule: ScheduleRule, changes: RuleFields) -> RuleFields:
    """The rule after ``changes``; a kind change drops the old kind's shape fields."""
    kind: RuleKind = changes.get("kind", rule.kind)
    base = RuleFields(kind=kind, local_time=rule.local_time, days_mask=rule.days_mask,
                      interval_hours=rule.interval_hours, at_epoch=rule.at_epoch, dose_count=rule.dose_count,
                      enabled=rule.enabled)
    if kind != rule.kind:
        for name in SHAPE_FIELDS:
            base[name] = None
    return RuleFields(**{**base, **changes})


def update_rule(conn: sqlite3.Connection, rule_id: int, changes: RuleFields, actor: str) -> RuleView:
    rule = _require_rule(conn, rule_id)
    now = scheduling.now_epoch()
    merged = _merged(rule, changes)
    if merged["kind"] != "once" or merged.get("at_epoch") != rule.at_epoch:
        merged = validate(merged, now)  # an unchanged past once-rule may still be toggled or recounted
    updated = schedules.update_rule(conn, rule_id, merged)
    assert updated is not None
    scheduling.expand(conn, rule.device_id, now)
    logger.info("schedule rule updated id=%s fields=%s actor=%s", rule_id, sorted(changes), actor)
    return _view(conn, updated)


def delete_rule(conn: sqlite3.Connection, rule_id: int, actor: str) -> None:
    rule = _require_rule(conn, rule_id)
    schedules.delete_rule(conn, rule_id)
    scheduling.expand(conn, rule.device_id)
    logger.info("schedule rule deleted id=%s device=%s actor=%s", rule_id, rule.device_id, actor)


def schedule_view(conn: sqlite3.Connection, device_id: str) -> ScheduleView:
    """Rules plus the next ``UPCOMING_LIMIT`` entries from a day back (FR-9 upcoming list)."""
    require_device(conn, device_id)
    tz = scheduling.context(conn, device_id).tz
    rules = [RuleView(rule, summary(rule, tz)) for rule in schedules.list_rules(conn, device_id)]
    since = scheduling.now_epoch() - UPCOMING_LOOKBACK_S
    entries = schedules.entries_after(conn, device_id, since, limit=UPCOMING_LIMIT)
    links = schedules.rule_ids_by_entry(conn, [e.id for e in entries])
    return ScheduleView(rules, [EntryView(e, links[e.id]) for e in entries])

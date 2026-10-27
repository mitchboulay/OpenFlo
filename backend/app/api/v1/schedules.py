"""Schedules (FR-9): rules in the home timezone and the upcoming entries they expand into."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Response

from .. import schedule_schemas as schemas
from ...repositories.schedules import RuleFields
from ...services import schedule_rules
from ...services.schedule_rules import EntryView, RuleView
from .auth import ActorDep
from .common import RepoDep

router = APIRouter(tags=["schedules"])


def _iso(epoch: int | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _fields(body: schemas.RuleCreate | schemas.RuleUpdate) -> RuleFields:
    """Request body -> rule columns: ``at`` becomes UTC epoch seconds."""
    data: dict[str, Any] = body.model_dump(exclude_unset=True)
    if "at" in data:
        at: datetime | None = data.pop("at")
        aware = at if at is None or at.tzinfo else at.replace(tzinfo=timezone.utc)
        data["at_epoch"] = None if aware is None else int(aware.timestamp())
    return cast(RuleFields, data)


def _rule(view: RuleView) -> schemas.Rule:
    rule = view.rule
    return schemas.Rule(
        id=rule.id, kind=cast(schemas.RuleKind, rule.kind), local_time=rule.local_time, days_mask=rule.days_mask,
        interval_hours=rule.interval_hours, at=_iso(rule.at_epoch), dose_count=cast(schemas.DoseCount, rule.dose_count),
        enabled=rule.enabled, summary=view.summary,
    )


def _entry(view: EntryView) -> schemas.Entry:
    entry = view.entry
    return schemas.Entry(
        id=entry.id, at=cast(str, _iso(entry.timestamp)), dose_count=cast(schemas.DoseCount, entry.dose_count),
        status=cast(schemas.EntryStatus, entry.status), reason=cast(Any, entry.reason), rule_ids=view.rule_ids,
    )


@router.get("/devices/{device_id}/schedule", response_model=schemas.Schedule)
def get_schedule(device_id: str, repo: RepoDep) -> schemas.Schedule:
    """Rules plus the next 10 entries (from a day back, so a just-dispensed or missed dose stays listed)."""
    with repo.db.connection() as conn:
        view = schedule_rules.schedule_view(conn, device_id)
    return schemas.Schedule(rules=[_rule(r) for r in view.rules], upcoming=[_entry(e) for e in view.upcoming])


@router.post("/devices/{device_id}/schedule/rules", response_model=schemas.Rule, status_code=201)
def create_rule(device_id: str, body: schemas.RuleCreate, repo: RepoDep, actor: ActorDep) -> schemas.Rule:
    """Add a rule; served at the device's next sync. 422 SCHEDULE_INVALID."""
    with repo.db.connection() as conn:
        view = schedule_rules.create_rule(conn, device_id, _fields(body), actor.name)
    return _rule(view)


@router.patch("/schedule/rules/{rule_id}", response_model=schemas.Rule)
def update_rule(rule_id: int, body: schemas.RuleUpdate, repo: RepoDep, actor: ActorDep) -> schemas.Rule:
    with repo.db.connection() as conn:
        view = schedule_rules.update_rule(conn, rule_id, _fields(body), actor.name)
    return _rule(view)


@router.delete("/schedule/rules/{rule_id}", status_code=204, response_class=Response)
def delete_rule(rule_id: int, repo: RepoDep, actor: ActorDep) -> Response:
    with repo.db.connection() as conn:
        schedule_rules.delete_rule(conn, rule_id, actor.name)
    return Response(status_code=204)

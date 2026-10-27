"""Homes (FR-1) and the devices in a home."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Response

from .. import schemas
from ...repositories.homes import HomeUpdate
from ...services import device_views, homes
from . import views
from .auth import ActorDep
from .common import DEFAULT_LIMIT, Limit, RepoDep, SettingsDep

router = APIRouter(tags=["homes"])


@router.get("/homes", response_model=list[schemas.HomeSummary])
def list_homes(repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: int | None = None) -> list[schemas.HomeSummary]:
    """Homes, newest first, with device counts and an attention summary."""
    return [views.home_summary(s) for s in device_views.home_snapshots(repo, limit=limit, before_id=before_id)]


@router.post("/homes", response_model=schemas.Home, status_code=201)
def create_home(body: schemas.HomeCreate, repo: RepoDep, settings: SettingsDep, actor: ActorDep) -> schemas.Home:
    with repo.db.connection() as conn:
        home = homes.create_home(conn, body.name, body.timezone or settings.default_timezone, actor.name)
    return views.home(home)


@router.patch("/homes/{home_id}", response_model=schemas.Home)
def update_home(home_id: int, body: schemas.HomeUpdate, repo: RepoDep, actor: ActorDep) -> schemas.Home:
    changes = cast(HomeUpdate, body.model_dump(exclude_unset=True))
    with repo.db.connection() as conn:
        home = homes.update_home(conn, home_id, changes, actor.name)
    return views.home(home)


@router.delete("/homes/{home_id}", status_code=204, response_class=Response)
def delete_home(home_id: int, repo: RepoDep, actor: ActorDep) -> Response:
    with repo.db.connection() as conn:
        homes.delete_home(conn, home_id, actor.name)
    return Response(status_code=204)


@router.get("/homes/{home_id}/devices", response_model=list[schemas.DeviceSummary])
def list_home_devices(
    home_id: int, repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: str | None = None
) -> list[schemas.DeviceSummary]:
    """Non-retired devices in the home, by descending device ID (``before_id`` = the last device ID seen)."""
    snaps = device_views.home_device_snapshots(repo, home_id, limit=limit, before_id=before_id)
    return [views.device_summary(s) for s in snaps]

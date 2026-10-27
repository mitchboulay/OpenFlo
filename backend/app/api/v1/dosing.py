"""Liquid profiles, dosing and bottles (FR-7, FR-8). The numbers come from ``dosing_service``."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Response

from .. import schemas
from ...repositories.profiles import ProfileUpdate
from ...services import dosing_service, liquid_profiles
from ...services.device_controls import require_device
from . import views
from .auth import ActorDep
from .common import DEFAULT_LIMIT, Limit, RepoDep

router = APIRouter(tags=["dosing"])


@router.get("/liquid-profiles", response_model=list[schemas.Profile])
def list_profiles(
    repo: RepoDep, home_id: int | None = None, limit: Limit = DEFAULT_LIMIT, before_id: int | None = None
) -> list[schemas.Profile]:
    """System liquids, plus the home's own when ``home_id`` is given."""
    with repo.db.connection() as conn:
        rows = liquid_profiles.list_profiles(conn, home_id, limit, before_id)
    return [views.profile(row) for row in rows]


@router.post("/homes/{home_id}/liquid-profiles", response_model=schemas.Profile, status_code=201)
def create_profile(home_id: int, body: schemas.ProfileCreate, repo: RepoDep, actor: ActorDep) -> schemas.Profile:
    with repo.db.connection() as conn:
        row = liquid_profiles.create_profile(
            conn, home_id, body.name, capacity_ml=body.capacity_ml, flow_full_ml_s=body.flow_full_ml_s,
            default_dose_ml=body.default_dose_ml, actor=actor.name,
        )
    return views.profile(row)


@router.patch("/liquid-profiles/{profile_id}", response_model=schemas.Profile)
def update_profile(
    profile_id: int, body: schemas.ProfileUpdate, repo: RepoDep, actor: ActorDep
) -> schemas.Profile:
    changes = cast(ProfileUpdate, body.model_dump(exclude_unset=True))
    with repo.db.connection() as conn:
        row = liquid_profiles.update_profile(conn, profile_id, changes, actor.name)
    return views.profile(row)


@router.delete("/liquid-profiles/{profile_id}", status_code=204, response_class=Response)
def delete_profile(profile_id: int, repo: RepoDep, actor: ActorDep) -> Response:
    with repo.db.connection() as conn:
        liquid_profiles.delete_profile(conn, profile_id, actor.name)
    return Response(status_code=204)


@router.get("/devices/{device_id}/dosing", response_model=schemas.Dosing)
def get_dosing(device_id: str, repo: RepoDep) -> schemas.Dosing:
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        view = dosing_service.get_dosing_view(conn, device_id)
    return views.dosing(view)


@router.put("/devices/{device_id}/dosing", response_model=schemas.Dosing)
def set_dosing(device_id: str, body: schemas.DosingUpdate, repo: RepoDep, actor: ActorDep) -> schemas.Dosing:
    """Dose by volume or fixed seconds. 422 DOSE_OUT_OF_RANGE {min_ml, max_ml}; warns CAPPED_WHEN_LOW."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        compensation = body.compensation_enabled
        if compensation is None:
            compensation = dosing_service.ensure_dosing(conn, device_id).compensation_enabled
        view = dosing_service.set_dosing(
            conn, device_id, body.profile_id, dose_ml=body.dose_ml, fixed_seconds=body.fixed_seconds,
            compensation_enabled=compensation, actor=actor.name,
        )
    return views.dosing(view)


@router.post("/devices/{device_id}/dosing/calibration", response_model=schemas.Dosing)
def calibrate(
    device_id: str, body: schemas.CalibrationRequest, repo: RepoDep, actor: ActorDep
) -> schemas.Dosing:
    """Scale the flow by measured / estimated mL of the last confirmed dispense (409 NO_RECENT_DISPENSE)."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        view = dosing_service.calibrate(conn, device_id, body.measured_ml, actor.name)
    return views.dosing(view)


@router.post("/devices/{device_id}/bottles", response_model=schemas.Bottle, status_code=201)
def new_bottle(device_id: str, body: schemas.BottleCreate, repo: RepoDep, actor: ActorDep) -> schemas.Bottle:
    """Start a bottle: ``full`` = the liquid's capacity; ``set`` = ``fill_ml``, or unknown when omitted."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        view = dosing_service.new_bottle(conn, device_id, body.fill, body.fill_ml, actor.name)
    return views.bottle(view)


@router.post("/devices/{device_id}/bottles/current/adjust", response_model=schemas.Bottle)
def adjust_fill(device_id: str, body: schemas.FillAdjust, repo: RepoDep, actor: ActorDep) -> schemas.Bottle:
    """Set the open bottle's level (409 NO_OPEN_BOTTLE)."""
    with repo.db.connection() as conn:
        require_device(conn, device_id)
        view = dosing_service.adjust_fill(conn, device_id, body.fill_ml, actor.name)
    return views.bottle(view)

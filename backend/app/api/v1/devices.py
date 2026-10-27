"""Devices (FR-2, FR-3, FR-5, FR-6, FR-10, FR-13). Fixed paths are registered before ``/devices/{device_id}``."""
from __future__ import annotations

from fastapi import APIRouter, Response

from .. import provisioning_schemas, schemas
from ...repositories import devices, flags
from ...services import device_controls, device_lifecycle, device_views
from . import views
from .auth import ActorDep
from .common import DEFAULT_LIMIT, Limit, RepoDep

router = APIRouter(tags=["devices"])


@router.get("/devices/unclaimed", response_model=list[schemas.UnclaimedDevice])
def list_unclaimed(
    repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: str | None = None
) -> list[schemas.UnclaimedDevice]:
    """Devices that sync without being registered (FR-5), by descending device ID."""
    with repo.db.connection() as conn:
        rows = devices.list_by_status(conn, "unclaimed", limit=limit, before_id=before_id)
    return [views.unclaimed(row) for row in rows]


@router.get("/devices/{device_id}", response_model=schemas.DeviceDetail)
def get_device(device_id: str, repo: RepoDep) -> schemas.DeviceDetail:
    return views.device_detail(device_views.device_snapshot(repo, device_id))


@router.patch("/devices/{device_id}", response_model=schemas.DeviceDetail)
def update_device(
    device_id: str, body: schemas.DeviceUpdate, repo: RepoDep, actor: ActorDep
) -> schemas.DeviceDetail:
    with repo.db.connection() as conn:
        device_lifecycle.update_device(conn, device_id, body.model_dump(exclude_unset=True), actor.name)
    return views.device_detail(device_views.device_snapshot(repo, device_id))


@router.post("/devices/{device_id}/claim", response_model=schemas.DeviceDetail)
def claim_device(
    device_id: str, body: provisioning_schemas.ClaimRequest, repo: RepoDep, actor: ActorDep
) -> schemas.DeviceDetail:
    """Claim an unclaimed device into a home (FR-5); dispensing starts off. 409 NOT_UNCLAIMED."""
    device_lifecycle.claim(repo, device_id, body.home_id, body.name, body.location, actor.name)
    return views.device_detail(device_views.device_snapshot(repo, device_id))


@router.post(
    "/devices/{device_id}/retire",
    response_model=schemas.DeviceDetail,
    responses={202: {"model": schemas.DeviceDetail, "description": "RETIRE_PENDING: waits for an empty schedule"}},
)
def retire_device(
    device_id: str, repo: RepoDep, actor: ActorDep, response: Response,
    body: schemas.RetireRequest | None = None,
) -> schemas.DeviceDetail:
    """Retire now (200) or once the device fetches an empty schedule (202, pending kind ``retire``)."""
    force = body.force if body is not None else False
    if not device_lifecycle.retire(repo, device_id, force, actor.name):
        response.status_code = 202
    return views.device_detail(device_views.device_snapshot(repo, device_id))


@router.patch("/devices/{device_id}/controls", response_model=schemas.Controls)
def update_controls(
    device_id: str, body: schemas.ControlsUpdate, repo: RepoDep, actor: ActorDep
) -> schemas.Controls:
    """Desired state for the next sync. A preset sets shift-time and fast-sync-time per AD-7."""
    changes = body.model_dump(exclude_unset=True)
    return views.controls(device_controls.update_controls(repo, device_id, changes, actor.name))


@router.post("/devices/{device_id}/dispense", response_model=schemas.DispenseRequest)
def queue_dispense(device_id: str, repo: RepoDep, actor: ActorDep) -> schemas.DispenseRequest:
    """Queue one dispense, sent exactly once at the next sync; a pending request is returned as is."""
    request = device_controls.queue_dispense(repo, device_id, actor.name)
    return views.dispense_request(device_views.DispenseRequestView(request, None))


@router.delete("/devices/{device_id}/dispense", response_model=schemas.DispenseRequest)
def cancel_dispense(device_id: str, repo: RepoDep, actor: ActorDep) -> schemas.DispenseRequest:
    request = device_controls.cancel_dispense(repo, device_id, actor.name)
    return views.dispense_request(device_views.DispenseRequestView(request, None))


@router.get("/devices/{device_id}/flags", response_model=list[schemas.Flag])
def list_flags(
    device_id: str, repo: RepoDep, limit: Limit = DEFAULT_LIMIT, before_id: int | None = None
) -> list[schemas.Flag]:
    """Every identity flag, acknowledged or not, newest first."""
    with repo.db.connection() as conn:
        device_controls.require_device(conn, device_id)
        rows = flags.list_for_device(conn, device_id, limit=limit, before_id=before_id)
    return [views.flag(row) for row in rows]


@router.post("/flags/{flag_id}/ack", response_model=schemas.Flag)
def ack_flag(flag_id: int, repo: RepoDep, actor: ActorDep) -> schemas.Flag:
    """Acknowledge a flag; commands resume once none is open (FR-13). Idempotent."""
    with repo.db.connection() as conn:
        row = device_controls.ack_flag(conn, flag_id, actor.name)
    return views.flag(row)

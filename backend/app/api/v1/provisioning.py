"""The provisioning wizard (FR-4, AD-4): sessions bound by a one-time token, shown once."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter

from .. import provisioning_schemas as schemas
from ...repositories.provisioning import ProvisioningSession
from ...services import provisioning
from .auth import ActorDep
from .common import RepoDep, SettingsDep

router = APIRouter(tags=["provisioning"])


def _session(row: ProvisioningSession, local_device_access: bool) -> schemas.Session:
    return schemas.Session(
        id=row.id, home_id=row.home_id, kind=cast(schemas.SessionKind, row.kind),
        target_device_id=row.target_device_id, device_name=row.device_name, location=row.location,
        status=cast(schemas.SessionStatus, row.status), bound_device_id=row.bound_device_id,
        reset_mode=provisioning.reset_mode(row, local_device_access), reset_result=row.reset_result,
        created_at=row.created_at, expires_at=row.expires_at, completed_at=row.completed_at,
    )


@router.post("/provisioning", response_model=schemas.ProvisioningCreated, status_code=201)
def create_session(
    body: schemas.ProvisioningCreate, repo: RepoDep, settings: SettingsDep, actor: ActorDep
) -> schemas.ProvisioningCreated:
    """Open a wizard. The token is in this response only. 409 ADDRESS_UNVERIFIED / WIZARD_OPEN."""
    with repo.db.connection() as conn:
        created = provisioning.create_session(
            conn, settings, home_id=body.home_id, kind=body.kind, target_device_id=body.target_device_id,
            device_name=body.device_name.strip(), location=body.location, actor=actor.name,
        )
    return schemas.ProvisioningCreated(
        session=_session(created.session, settings.local_device_access), token=created.token,
        pairing_url=created.pairing_url, wifi_qr=created.wifi_qr,
    )


@router.get("/provisioning/{session_id}", response_model=schemas.ProvisioningStatus)
def get_session(session_id: int, repo: RepoDep, settings: SettingsDep) -> schemas.ProvisioningStatus:
    status = provisioning.session_status(repo, session_id)
    return schemas.ProvisioningStatus(
        session=_session(status.session, settings.local_device_access),
        steps=[schemas.ProvisioningStep(step=e.step, at=e.at, detail=e.detail) for e in status.steps],
        next_expected_sync=status.next_expected_sync,
    )


@router.post("/provisioning/{session_id}/reset", response_model=schemas.Session)
async def lan_reset(session_id: int, repo: RepoDep, settings: SettingsDep, actor: ActorDep) -> schemas.Session:
    """Send the factory reset over the LAN, once (409 LAN_RESET_UNAVAILABLE when it cannot be sent)."""
    row = await provisioning.send_lan_reset(repo.db, settings, session_id, actor.name)
    return _session(row, settings.local_device_access)


@router.post("/provisioning/{session_id}/manual-reset", response_model=schemas.Session)
def manual_reset(session_id: int, repo: RepoDep, settings: SettingsDep, actor: ActorDep) -> schemas.Session:
    """The operator held the reset button: wait for the hotspot."""
    with repo.db.connection() as conn:
        row = provisioning.confirm_manual_reset(conn, session_id, actor.name)
    return _session(row, settings.local_device_access)


@router.post("/provisioning/{session_id}/cancel", response_model=schemas.Session)
def cancel_session(session_id: int, repo: RepoDep, settings: SettingsDep, actor: ActorDep) -> schemas.Session:
    with repo.db.connection() as conn:
        row = provisioning.cancel(conn, session_id, actor.name)
    return _session(row, settings.local_device_access)

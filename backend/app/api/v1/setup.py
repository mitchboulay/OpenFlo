"""First-run setup and the server address (FR-16, AD-9).

While setup is required these routes need no sign-in (FR-15, Jellyfin-style); the setup gate lets only them
(and ``/server-info``) through. Once setup is ready they need an actor like every other route.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from ...errors import ApiError
from ...services import address_check, server_address, setup
from ...services.oidc import OidcClient
from .. import setup_schemas
from .auth import Actor, current_actor, require_csrf, start_session
from .common import RepoDep, SettingsDep

router = APIRouter(tags=["setup"])
SETUP_ACTOR = "setup:wizard"


def wizard_actor(request: Request) -> Actor:
    """The setup wizard during ``setup_required`` (cross-site browser mutations still refused), else
    :func:`current_actor`."""
    with request.app.state.db.connection() as conn:
        required = setup.state(conn) == "setup_required"
    if not required:
        return current_actor(request)
    require_csrf(request, "none")
    return Actor(SETUP_ACTOR, "none")


WizardActorDep = Annotated[Actor, Depends(wizard_actor)]


async def _steps(request: Request, repo: RepoDep, settings: SettingsDep) -> setup.Steps:
    oidc: OidcClient | None = request.app.state.oidc
    discovered = await oidc.discovered() if oidc is not None else False
    with repo.db.connection() as conn:
        return setup.steps(conn, settings, discovered)


StepsDep = Annotated[setup.Steps, Depends(_steps)]


@router.get("/setup", response_model=setup_schemas.SetupStatus)
def get_setup(_: WizardActorDep, steps: StepsDep, repo: RepoDep) -> setup_schemas.SetupStatus:
    """The setup state and each wizard step."""
    with repo.db.connection() as conn:
        state = setup.state(conn)
    return setup_schemas.SetupStatus(setup_state=state, steps=setup_schemas.SetupSteps(**asdict(steps)))


@router.post("/setup/admin", status_code=204, response_class=Response)
def create_admin(body: setup_schemas.AdminCreate, request: Request, repo: RepoDep, settings: SettingsDep,
                 actor: WizardActorDep) -> Response:
    """Basic mode: create the admin and sign in as them (the same session cookie as ``/auth/login``).
    409 ``ALREADY_SET``, 422 ``WEAK_PASSWORD`` (< 12 characters)."""
    with repo.db.connection() as conn:
        admin = setup.create_admin(conn, settings, body.username, body.password, actor.name)
    start_session(request, admin)
    return Response(status_code=204)


@router.post("/setup/complete", response_model=setup_schemas.SetupComplete)
def complete_setup(actor: WizardActorDep, steps: StepsDep, repo: RepoDep) -> setup_schemas.SetupComplete:
    """``setup_required -> ready``. 409 ``SETUP_INCOMPLETE`` (``detail`` = the steps) until every step is done."""
    with repo.db.connection() as conn:
        return setup_schemas.SetupComplete(setup_state=setup.complete(conn, steps, actor.name))


@router.put("/settings/server-address", response_model=setup_schemas.ServerAddress)
def put_server_address(body: setup_schemas.ServerAddress, repo: RepoDep,
                       actor: WizardActorDep) -> setup_schemas.ServerAddress:
    """Save ``scheme://host[:port]``. A failing check does not block saving. 422 ``ADDRESS_INVALID``."""
    with repo.db.connection() as conn:
        return setup_schemas.ServerAddress(server_address=server_address.save(conn, body.server_address, actor.name))


@router.get("/settings/server-address/check", response_model=setup_schemas.AddressCheckResult)
def get_address_check(repo: RepoDep, _: WizardActorDep) -> setup_schemas.AddressCheckResult:
    """The last stored check (by the wizard, Settings or the nightly run). 404 ``NOT_CHECKED``."""
    with repo.db.connection() as conn:
        result = address_check.last(conn)
    if result is None:
        raise ApiError("NOT_CHECKED", "the server address has not been checked yet", 404)
    return setup_schemas.AddressCheckResult.model_validate(asdict(result))


@router.post("/settings/server-address/check", response_model=setup_schemas.AddressCheckResult)
async def run_address_check(repo: RepoDep, settings: SettingsDep,
                            actor: WizardActorDep) -> setup_schemas.AddressCheckResult:
    """Run the six device-view checks against the server address now (≤ 5 s each, concurrently)."""
    result = await address_check.check_and_store(repo.db, settings, actor.name)
    if result is None:
        raise ApiError("ADDRESS_NOT_SET", "save a server address first", 409)
    return setup_schemas.AddressCheckResult.model_validate(asdict(result))

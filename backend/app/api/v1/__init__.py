"""``/api/v1`` (AD-10): errors are ``{code, message, detail?}``; every route but sign-in and server info needs an
actor (AD-8)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..schemas import ErrorBody
from . import auth_routes, devices, dosing, history, homes, provisioning, schedules, setup, tokens
from .auth import current_actor

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorBody, "description": description}
    for status, description in (
        (401, "Not authenticated (AUTH_REQUIRED, INVALID_TOKEN)"),
        (403, "Refused (CSRF_REJECTED, GROUP_DENIED)"),
        (404, "Not found"),
        (409, "Conflict with the current state (SETUP_REQUIRED until first-run setup is complete)"),
        (422, "Invalid request (INVALID_REQUEST and per-route codes)"),
        (503, "Database busy (DB_BUSY)"),
    )
}

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
# FR-15 exemptions: sign-in, OIDC and server info resolve no actor; the setup wizard needs none while setup
# is required (FR-16).
router.include_router(auth_routes.router)
router.include_router(setup.router)
protected = APIRouter(dependencies=[Depends(current_actor)])
# Order matters within each module: fixed paths before parameterized ones (API Specification).
for module in (tokens, homes, devices, dosing, schedules, history, provisioning):
    protected.include_router(module.router)
router.include_router(protected)

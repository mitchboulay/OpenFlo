"""First-run setup (FR-16, AD-9): the ``setup_required -> ready`` state machine and its wizard steps.

Steps: 1. authentication (create the basic admin, or OIDC discovery answers); 2. a server address (saved,
or seeded from ``OPENFLO_PUBLIC_URL``); 3. the address check has run for that address (a failing check
does not block setup, only provisioning). ``POST /setup/complete`` moves to ``ready`` once all three are
done; there is no way back.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Literal

from ..config import Settings
from ..errors import ApiError
from ..repositories import settings as settings_repo
from . import address_check, basic_auth, server_address
from .auth_policy import require_auth_mode

logger = logging.getLogger(__name__)

SETUP_STATE = "setup_state"
SetupState = Literal["setup_required", "ready"]
StepState = Literal["pending", "done"]
CheckStep = Literal["pending", "ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class Steps:
    auth: StepState
    server_address: StepState
    address_check: CheckStep

    @property
    def complete(self) -> bool:
        return self.auth == "done" and self.server_address == "done" and self.address_check != "pending"


def state(conn: sqlite3.Connection) -> SetupState:
    return "ready" if settings_repo.get_value(conn, SETUP_STATE) == "ready" else "setup_required"


def steps(conn: sqlite3.Connection, settings: Settings, oidc_discovered: bool) -> Steps:
    """``oidc_discovered``: the IdP's discovery document loads (checked by the caller; it is network I/O)."""
    if settings.auth_mode == "basic":
        auth_done = basic_auth.credential(conn, settings) is not None
    else:
        auth_done = oidc_discovered or settings.auth_mode != "oidc"  # none/proxy: nothing to set up
    address = server_address.effective(conn, settings)
    return Steps(
        auth="done" if auth_done else "pending",
        server_address="done" if address else "pending",
        address_check=_check_step(conn, address),
    )


def _check_step(conn: sqlite3.Connection, address: str | None) -> CheckStep:
    result = address_check.last(conn)
    if address is None or result is None or result.address != address:
        return "pending"  # never run, or run for an address that has since changed
    statuses = {check.status for check in result.checks}
    return "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"


def create_admin(conn: sqlite3.Connection, settings: Settings, username: str, password: str, actor: str) -> str:
    """Wizard step 1 in basic mode; returns the new admin's actor name, for signing them in.
    409 ``ALREADY_SET`` once an admin exists (env or setup)."""
    require_auth_mode(settings, "basic")
    return basic_auth.create_admin(conn, settings, username, password, actor)


def complete(conn: sqlite3.Connection, current: Steps, actor: str) -> SetupState:
    """``setup_required -> ready``; idempotent. 409 ``SETUP_INCOMPLETE`` (with the steps) until all are done."""
    if state(conn) == "ready":
        return "ready"
    if not current.complete:
        raise ApiError("SETUP_INCOMPLETE", "finish every setup step first", 409,
                       {"auth": current.auth, "server_address": current.server_address,
                        "address_check": current.address_check})
    settings_repo.put(conn, SETUP_STATE, "ready", actor)
    logger.info("first-run setup completed by %s", actor)
    return "ready"

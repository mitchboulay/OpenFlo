"""``GET /api/v1/server-info`` (FR-17, AD-10): what any client needs to connect to this server by address."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..config import AuthMode, Settings
from ..repositories import settings as settings_repo
from . import server_address, setup

SERVER_NAME = "OpenFLO"
API_VERSION = "1"

AUTH_METHODS: dict[AuthMode, list[str]] = {
    "none": ["none", "token"],
    "basic": ["password", "token"],
    "oidc": ["oidc", "token"],
    "proxy": ["proxy", "token"],
}


def server_info(conn: sqlite3.Connection, settings: Settings) -> dict[str, Any]:
    oidc = settings.auth_mode == "oidc"
    return {
        "name": SERVER_NAME,
        "version": settings.emulator_version,
        "api_version": API_VERSION,
        "instance_id": settings_repo.instance_id(conn),
        "setup_state": setup.state(conn),
        "auth": {
            "mode": settings.auth_mode,
            "methods": AUTH_METHODS[settings.auth_mode],
            "oidc_issuer": settings.oidc_issuer if oidc else None,
            "oidc_client_id": settings.oidc_client_id if oidc else None,
        },
        "server_address": server_address.effective(conn, settings),
    }

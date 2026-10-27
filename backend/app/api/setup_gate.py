"""The first-run setup gate (FR-16): while setup is required, ``/api/v1`` answers 409 ``SETUP_REQUIRED``.

Exempt: ``/server-info``, the setup wizard (``/setup*``, ``/settings/server-address*``) and the OpenAPI
document. Everything outside ``/api/v1`` (``/healthz``, ``/device-api/*``, the SPA that shows the wizard) is
never gated.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..db import Database
from ..services import setup
from .error_handlers import API_V1_PREFIX, is_api_v1

CallNext = Callable[[Request], Awaitable[Response]]
EXEMPT_PATHS = frozenset({f"{API_V1_PREFIX}/server-info", f"{API_V1_PREFIX}/openapi.json"})
EXEMPT_PREFIXES = (f"{API_V1_PREFIX}/setup", f"{API_V1_PREFIX}/settings/server-address")


def exempt(path: str) -> bool:
    return path in EXEMPT_PATHS or any(path == prefix or path.startswith(prefix + "/") for prefix in EXEMPT_PREFIXES)


class SetupGate:
    """HTTP middleware. Reads the state per gated request (one primary-key lookup) so it never goes stale."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        if is_api_v1(request) and not exempt(request.url.path):
            with self.db.connection() as conn:
                state = setup.state(conn)
            if state == "setup_required":
                return JSONResponse({"code": "SETUP_REQUIRED", "message": "finish first-run setup at /setup",
                                     "detail": {"setup_url": "/setup"}}, status_code=409)
        return await call_next(request)

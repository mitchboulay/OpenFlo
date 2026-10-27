from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from . import backup
from .api import error_handlers
from .api.device_v2 import router as device_router
from .api.setup_gate import SetupGate
from .api.v1 import router as api_v1_router
from .config import Settings, check_startup
from .db import Database
from .device_gate import DeviceGate
from .persistence.repository import Repository
from .protocol_log import ProtocolLog
from .repositories import settings as settings_repo
from .services import address_check, api_tokens, nightly, provisioning, secret_key, setup
from .services.auth_policy import SlidingWindowLimiter
from .services.oidc import OidcClient
from .spa import mount_spa


SESSION_COOKIE = "openflo_session"
SESSION_IDLE_SECONDS = 12 * 3600  # FR-15; the cookie is re-signed on every response, so this is idle time


def _install_auth(app: FastAPI, settings: Settings) -> None:
    """Signed session cookies (Secure, HttpOnly, SameSite=Lax), the login limiter and the OIDC client (AD-8)."""
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key.load_or_create(settings.data_dir),
        session_cookie=SESSION_COOKIE,
        max_age=SESSION_IDLE_SECONDS,
        same_site="lax",
        https_only=True,
    )
    app.state.login_limiter = SlidingWindowLimiter()
    app.state.oidc = OidcClient(settings) if settings.auth_mode == "oidc" else None


def _lifespan(database: Database, settings: Settings) -> Callable[[FastAPI], contextlib.AbstractAsyncContextManager[None]]:
    """Background jobs live as long as the app: the nightly address check (FR-16) and the provisioning sweep
    (AD-4), which also expires sessions left open by a restart. The app lock tells ``openflo restore`` the app
    is running."""

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        with backup.hold_app_lock(Path(settings.db_path).resolve()):
            with database.connection() as conn:
                provisioning.expire_open(conn)
            tasks = [
                asyncio.create_task(nightly.run_address_check_nightly(database, settings)),
                asyncio.create_task(provisioning.sweep_forever(database)),
            ]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                for task in tasks:
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    return lifespan


def _install_healthz(app: FastAPI, settings: Settings, database: Database) -> None:
    """``/healthz``: always 200; setup state and degraded reasons (Reliability NFR) never turn into a 503."""

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        with database.connection() as conn:
            last_check = address_check.last(conn)
            state = setup.state(conn)
        return {
            "status": "ok",
            "service": "openflo-device-backend",
            "version": settings.emulator_version,
            "firmware_version": settings.firmware_version,
            "setup_state": state,
            "degraded": ["address_check_failed"] if last_check is not None and last_check.failed else [],
            "safe_mode": {
                "ota": "suppressed",
                "remote_dispense": "suppressed",
                "schedule": "per-device operator control (default off)",
                "dispensing": "per-device operator control (default locked)",
            },
        }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    check_startup(settings)
    database = Database(settings.db_path)
    database.init()
    repo = Repository(database)

    app = FastAPI(
        title="OpenFLO device backend emulator",
        version=settings.emulator_version,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        lifespan=_lifespan(database, settings),
    )
    app.state.settings = settings
    app.state.db = database
    app.state.repo = repo
    with database.connection() as conn:
        instance_id = settings_repo.instance_id(conn)
        api_tokens.seed_bootstrap(conn, settings.api_token)

    app.include_router(device_router)
    app.include_router(api_v1_router)
    error_handlers.install(app)

    _install_healthz(app, settings, database)

    app.middleware("http")(ProtocolLog(settings, repo))

    # Added after protocol_log, so it runs first: rate-limited and over-cap requests are never logged.
    app.state.device_gate = DeviceGate(settings, database, instance_id)
    app.middleware("http")(app.state.device_gate)
    app.middleware("http")(SetupGate(database))
    _install_auth(app, settings)

    # Registered last: every backend route takes precedence over the SPA.
    mount_spa(app, Path(settings.ui_dist))
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("OPENFLO_BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("OPENFLO_BACKEND_PORT", "8099")),
    )

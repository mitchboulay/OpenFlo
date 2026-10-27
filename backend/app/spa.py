"""Serves the built SPA (``ui/dist``) with history fallback (AD-1).

Fallback runs only when no route matched (a 404), so every backend route keeps
its exact behavior, including 405s on the POST-only device API.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

# First path segments that belong to the backend and never fall back to the SPA.
BACKEND_SEGMENTS = frozenset({"api", "device-api", "healthz", "assets"})


def is_spa_path(path: str) -> bool:
    """True when ``path`` is a client-side route rather than a backend path."""
    first_segment = path.split("/", 2)[1] if path.startswith("/") else path
    return first_segment not in BACKEND_SEGMENTS


def mount_spa(app: FastAPI, dist_dir: Path) -> bool:
    """Serve ``dist_dir`` if it holds a build. Returns whether it was mounted."""
    index = dist_dir / "index.html"
    if not index.is_file():
        return False

    assets = dist_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    async def spa_fallback(request: Request, exc: StarletteHTTPException) -> Response:
        if request.method in ("GET", "HEAD") and is_spa_path(request.url.path):
            # Hashed assets cache forever; index.html must revalidate after upgrades.
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        # The app's own HTTPException handler (the /api/v1 error shape, FastAPI's elsewhere).
        return await request.app.exception_handlers[StarletteHTTPException](request, exc)

    app.add_exception_handler(404, spa_fallback)
    return True

"""Exception handlers for both APIs.

``/api/v1`` errors are ``{code, message, detail?}`` (AD-10). Device-API errors are ``{code, message}`` only:
no ``fields`` (the 3.0.64 firmware ignores such bodies, FUN_40094c80) and no ``detail``.
"""
from __future__ import annotations

import logging
import sqlite3
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from ..errors import ApiError
from ..services.dosing_service import DoseOutOfRange, DosingError

log = logging.getLogger("openflo.backend")

API_V1_PREFIX = "/api/v1"

# HTTP status for each dosing-service error code (FR-7, FR-8 and the API table).
DOSING_STATUS: dict[str, int] = {
    "DOSE_OUT_OF_RANGE": 422,
    "NO_RECENT_DISPENSE": 409,
    "CALIBRATION_IMPLAUSIBLE": 422,
    "NO_OPEN_BOTTLE": 409,
    "PROFILE_NOT_FOUND": 404,
    "FILL_OUT_OF_RANGE": 422,
}


def is_api_v1(request: Request) -> bool:
    path = request.url.path
    return path == API_V1_PREFIX or path.startswith(API_V1_PREFIX + "/")


def error_response(
    request: Request, code: str, message: str, status: int, detail: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None and is_api_v1(request):
        body["detail"] = detail
    return JSONResponse(body, status_code=status)


def _status_code(status: int) -> str:
    try:
        return HTTPStatus(status).name
    except ValueError:
        return "HTTP_ERROR"


async def _api_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiError)
    return error_response(request, exc.code, exc.message, exc.status, exc.detail)


async def _dosing_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, DosingError)
    detail = {"min_ml": exc.min_ml, "max_ml": exc.max_ml} if isinstance(exc, DoseOutOfRange) else None
    return error_response(request, exc.code, exc.message, DOSING_STATUS.get(exc.code, 422), detail)


async def _validation_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"loc": [str(part) for part in error.get("loc", [])], "msg": str(error.get("msg", "invalid value"))}
        for error in exc.errors()
    ]
    problems = "; ".join(".".join(e["loc"]) + ": " + e["msg"] for e in errors)
    return error_response(
        request, "INVALID_REQUEST", f"request validation failed: {problems}", 422, {"errors": errors}
    )


async def _http_error(request: Request, exc: Exception) -> Response:
    """Unknown routes and wrong methods under /api/v1 get the error shape; other paths keep FastAPI's."""
    assert isinstance(exc, StarletteHTTPException)
    if not is_api_v1(request):
        return await http_exception_handler(request, exc)
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    response = error_response(request, _status_code(exc.status_code), message, exc.status_code)
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _db_operational(request: Request, exc: Exception) -> Response:
    """SQLite busy past ``busy_timeout``: 503 DB_BUSY on /api/v1 (Failure Modes); the device API keeps its 500."""
    if is_api_v1(request) and "locked" in str(exc):
        log.warning("database busy on %s", request.url.path)
        return error_response(request, "DB_BUSY", "the database is busy, try again", 503)
    return await _unhandled(request, exc)


async def _unhandled(request: Request, exc: Exception) -> Response:
    log.exception("unhandled backend error", exc_info=exc)
    return error_response(request, "INTERNAL_ERROR", "internal backend error", 500)


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(DosingError, _dosing_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(sqlite3.OperationalError, _db_operational)
    app.add_exception_handler(Exception, _unhandled)

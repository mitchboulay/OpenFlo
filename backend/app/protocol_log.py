"""Protocol log middleware: the body-size limit, plus a redacted request/response record of device-API traffic.

Only ``/device-api/*`` is recorded: it is the firmware protocol under study. Management calls (``/api/v1``,
polled by the UI) are not protocol traffic and would only bloat the table.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from .config import Settings
from .device_gate import DEVICE_API_PREFIX
from .persistence.repository import Repository

log = logging.getLogger("openflo.backend")

SENSITIVE_KEY = re.compile(r"(token|ott|password|secret|authorization|api[_-]?key)", re.IGNORECASE)
CallNext = Callable[[Request], Awaitable[Response]]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def _parse_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except (ValueError, TypeError):
        return None


def _headers_for_log(request: Request) -> dict[str, str]:
    # x-device-ott is deliberately not logged.
    keep = ("content-type", "user-agent", "x-device-id")
    return {k: request.headers[k] for k in keep if k in request.headers}


def device_error(code: str, message: str, status: int) -> JSONResponse:
    # No "fields" key: the 3.0.64 firmware ignores error bodies without it
    # (FUN_40094c80), so no error code can ever drive device behavior.
    return JSONResponse({"code": code, "message": message}, status_code=status)


def _redacted(value: Any, keep: bool) -> str | None:
    return json.dumps(redact(value), sort_keys=True) if keep and value is not None else None


class ProtocolLog:
    def __init__(self, settings: Settings, repo: Repository) -> None:
        self.settings = settings
        self.repo = repo

    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        body = await request.body()
        if len(body) > self.settings.max_body_bytes:
            return device_error("PAYLOAD_TOO_LARGE", "request body exceeds configured limit", 413)
        try:
            response = await call_next(request)
            response_body = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
            response = Response(content=response_body, status_code=response.status_code,
                                headers=dict(response.headers), media_type=response.media_type)
        except Exception:
            log.exception("unhandled backend error")
            response, response_body = device_error("INTERNAL_ERROR", "internal backend error", 500), b""
        if self.settings.log_payloads and request.url.path.startswith(DEVICE_API_PREFIX):
            self._record(request, body, response, response_body)
        return response

    def _record(self, request: Request, body: bytes, response: Response, response_body: bytes) -> None:
        # The device gate marks unknown device IDs; their payloads are never stored (FR-13).
        keep = getattr(request.state, "device_known", True)
        try:
            self.repo.log_protocol(
                method=request.method,
                path=request.url.path,
                device_id=request.headers.get("x-device-id"),
                status=response.status_code,
                request_json=_redacted(_parse_json(body), keep),
                response_json=_redacted(_parse_json(response_body), keep),
                headers_json=json.dumps(_headers_for_log(request), sort_keys=True),
                note=None,
            )
        except Exception:
            log.exception("failed to write protocol log")

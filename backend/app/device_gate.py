"""Abuse controls for ``/device-api/*`` (AD-3, FR-13): mitigations for public device IDs, not authentication.

Limiter state is in memory and per process: OpenFLO runs a single uvicorn process, and a restart resets it.
Gate DB work runs on the event loop, which serializes the unclaimed-cap check with its insert (at most
three indexed reads per request).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from .config import Settings
from .db import Database
from .models import DEVICE_ID_RE
from .repositories import devices
from .services import device_syncs

log = logging.getLogger("openflo.device_gate")

DEVICE_API_PREFIX = "/device-api/"
INSTANCE_HEADER = "X-OpenFLO-Instance"
# Pairing endpoints answer unknown IDs themselves (AD-4) and never create unclaimed rows.
PAIRING_PATHS = frozenset({"/device-api/v2/healthcheck", "/device-api/v2/register"})
REJECTION_LOG_INTERVAL_S = 60.0

CallNext = Callable[[Request], Awaitable[Response]]


@dataclass
class TokenBucket:
    """``capacity`` requests per ``per_seconds``, refilled continuously, keyed by client IP."""

    capacity: float
    per_seconds: float
    _state: dict[str, tuple[float, float]] = field(default_factory=dict)

    def _tokens(self, key: str, now: float) -> float:
        tokens, last = self._state.get(key, (self.capacity, now))
        return min(self.capacity, tokens + (now - last) * self.capacity / self.per_seconds)

    def allow(self, key: str, now: float) -> bool:
        tokens = self._tokens(key, now)
        allowed = tokens >= 1.0
        self._state[key] = (tokens - 1.0 if allowed else tokens, now)
        return allowed

    def prune(self, now: float) -> None:
        """Forget full buckets so memory tracks only recently active IPs."""
        for key in [k for k in self._state if self._tokens(k, now) >= self.capacity]:
            del self._state[key]


def _error(code: str, message: str, status: int) -> JSONResponse:
    # No "fields": the firmware ignores the body (errors.py).
    return JSONResponse({"code": code, "message": message}, status_code=status)


class DeviceGate:
    """HTTP middleware: rate limits, unclaimed cap, sync derivation and the instance header."""

    def __init__(self, settings: Settings, db: Database, instance_id: str,
                 clock: Callable[[], float] | None = None) -> None:
        self.settings = settings
        self.db = db
        self.instance_id = instance_id
        self.clock: Callable[[], float] = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self.per_ip = TokenBucket(capacity=300, per_seconds=300)
        self.unknown_per_ip = TokenBucket(capacity=10, per_seconds=60)
        self.rejected_unknown = 0
        self._last_tick = self.clock()

    async def __call__(self, request: Request, call_next: CallNext) -> Response:
        if not request.url.path.startswith(DEVICE_API_PREFIX):
            return await call_next(request)
        now = self.clock()
        self._tick(now)
        source_ip = request.client.host if request.client else "unknown"
        rejection: Response | None = None
        if not self.per_ip.allow(source_ip, now):
            rejection = _error("RATE_LIMITED", "too many device requests from this address", 429)
        else:
            device_id = await self._device_id(request)
            request.state.device_known = False
            if device_id is not None:
                rejection = self._admit(request, device_id, source_ip, now)
        response = rejection or await call_next(request)
        response.headers[INSTANCE_HEADER] = self.instance_id
        return response

    def _admit(self, request: Request, device_id: str, source_ip: str, now: float) -> Response | None:
        """Gate one identified request; returns a rejection, or None to continue to the route."""
        at = datetime.fromtimestamp(now, timezone.utc)
        with self.db.connection() as conn:
            known = devices.get(conn, device_id) is not None
            request.state.device_known = known
            if not known:
                if not self.unknown_per_ip.allow(source_ip, now):
                    return _error("RATE_LIMITED", "too many unknown device IDs from this address", 429)
                if request.url.path in PAIRING_PATHS:
                    return None
                admitted = DEVICE_ID_RE.fullmatch(device_id) is not None and device_syncs.admit_unclaimed(
                    conn, device_id, source_ip, at, self.settings.unclaimed_cap
                )
                if not admitted:
                    self.rejected_unknown += 1
                    return _error("DEVICE_NOT_REGISTERED", "device is not registered with this backend", 422)
            device_syncs.record_request(conn, device_id, source_ip, at)
        return None

    async def _device_id(self, request: Request) -> str | None:
        """``x-device-id``, else the JSON body's ``deviceId`` (register, healthcheck, get-fw)."""
        header = request.headers.get("x-device-id")
        if header:
            return header
        body = await request.body()
        if not body or len(body) > self.settings.max_body_bytes:
            return None
        try:
            parsed = json.loads(body)
        except ValueError:
            return None
        value = parsed.get("deviceId") if isinstance(parsed, dict) else None
        return value if isinstance(value, str) and value else None

    def _tick(self, now: float) -> None:
        """Once a minute at most: report rejected unknown IDs (count only, never payloads) and prune buckets."""
        if now - self._last_tick < REJECTION_LOG_INTERVAL_S:
            return
        self._last_tick = now
        if self.rejected_unknown:
            log.warning("device gate rejected %d requests from unknown device IDs over the unclaimed cap",
                        self.rejected_unknown)
            self.rejected_unknown = 0
        self.per_ip.prune(now)
        self.unknown_per_ip.prune(now)

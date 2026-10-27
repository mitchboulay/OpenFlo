"""LAN-direct factory reset of an iFLO (FR-4 reset kind, AD-4): one POST, no retry.

The firmware's local HTTP server exposes ``POST /dev_actions {"restoreToDefault": true}``
(research/local-http-interface.md); it answered HTTP 200 and then wiped and restarted the lab device
(research/mission-008c.md, research/migration-runbook.md step 2b). The reset wipes Wi-Fi, registration and
cartridge state, so it is sent at most once per call: a 1 s TCP probe, then one POST with a 3 s timeout.
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
from dataclasses import dataclass
from typing import Any

import httpx

LAN_RESET_PORT = 80
CONNECT_TIMEOUT_S = 1.0
POST_TIMEOUT_S = 3.0
RESET_PATH = "/dev_actions"
RESET_BODY: dict[str, Any] = {"restoreToDefault": True}


@dataclass(frozen=True, slots=True)
class ResetResult:
    ok: bool
    detail: str

    @property
    def recorded(self) -> str:
        """The ``provisioning_sessions.reset_result`` text: ``ok: …`` or ``failed: …``."""
        return f"{'ok' if self.ok else 'failed'}: {self.detail}"


def lan_address(value: object) -> str | None:
    """The device-reported ``localIpAddress`` when it is a private unicast address, else None.

    The value comes from the device path, which cannot authenticate (Constraint 7), so the server only ever
    connects to a private LAN host: never loopback, link-local, multicast or a public address.
    """
    if not isinstance(value, str):
        return None
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return None
    return str(ip)


async def _reachable(host: str, port: int) -> str | None:
    """None when a TCP connect succeeds within 1 s, else why it did not."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT_S)
    except asyncio.TimeoutError:
        return "connect timed out after 1 s"
    except OSError as exc:
        return f"connect failed: {exc.strerror or type(exc).__name__}"
    writer.close()
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return None


async def send_factory_reset(host: str) -> ResetResult:
    """Probe ``host:80``, then POST the reset once. Never retried: a lost reply may still have reset it."""
    port = LAN_RESET_PORT
    unreachable = await _reachable(host, port)
    if unreachable is not None:
        return ResetResult(False, unreachable)
    url = f"http://{f'[{host}]' if ':' in host else host}:{port}{RESET_PATH}"
    try:
        async with httpx.AsyncClient(timeout=POST_TIMEOUT_S, follow_redirects=False) as client:
            response = await client.post(url, json=RESET_BODY)
    except httpx.HTTPError as exc:
        return ResetResult(False, f"POST {RESET_PATH} failed: {type(exc).__name__}")
    if response.is_success:
        return ResetResult(True, f"HTTP {response.status_code}")
    return ResetResult(False, f"HTTP {response.status_code}")

"""Provisioning bound by a one-time token (AD-4, FR-4).

Sessions move ``awaiting_reset`` (reset kind) → ``awaiting_softap`` → ``awaiting_join`` → ``completed``, or end
``expired`` / ``cancelled``. The server cannot see the phone on the device's hotspot, so a session waiting for
it advances to ``awaiting_join`` ("device found") on the first pairing healthcheck that could be its device:
an unknown ID for ``new``, the target ID for ``reset``. Only ``register`` binds a device, and only with the
session's token (stored as SHA-256, never logged) from the IP its healthcheck was sighted at.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from ..config import Settings
from ..db import Database
from ..errors import ApiError
from ..persistence.repository import Repository, utcnow
from ..repositories import bottles, devices, provisioning, syncs, telemetry
from ..repositories.devices import Device
from ..repositories._rows import MAX_LIMIT
from ..repositories.provisioning import ProvisioningEvent, ProvisioningSession, SessionKind
from . import address_check, lan_reset, server_address
from .device_syncs import SYNC_GAP
from .homes import require_home
from .sync_status import next_expected_sync

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(minutes=20)
SIGHTING_TTL = timedelta(minutes=20)
SWEEP_INTERVAL_S = 30.0
# FR-4: the iFLO hotspot, and the address checks whose failure would leave a device unable to reach us.
HOTSPOT_SSID = "iFLO device"
HOTSPOT_PASSWORD = "13106423"
BLOCKING_CHECKS = frozenset({"tls_no_sni", "chain_firmware_bundle", "leaf_rsa"})
OPEN_STATUSES = frozenset({"awaiting_reset", "awaiting_softap", "awaiting_join"})
ResetMode = Literal["lan", "manual"]


@dataclass(frozen=True, slots=True)
class NewSession:
    session: ProvisioningSession
    token: str  # plaintext, returned once by POST /provisioning and never stored or logged
    pairing_url: str
    wifi_qr: str


@dataclass(frozen=True, slots=True)
class SessionStatus:
    session: ProvisioningSession
    steps: list[ProvisioningEvent]  # oldest first
    next_expected_sync: str | None


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> ApiError:
    # The register rejection: no "fields", so the firmware ignores the body and keeps its pairing loop.
    return ApiError("NOT_FOUND", "no provisioning session matches this token")


# -- wizard side (/api/v1/provisioning) ------------------------------------------------------------------------


def require_verified_address(conn: sqlite3.Connection, settings: Settings) -> str:
    """The server address devices will persist; 409 ADDRESS_UNVERIFIED unless its last check passed the TLS
    checks the firmware depends on (FR-4, FR-16). A check of an older address does not count."""
    address = server_address.effective(conn, settings)
    last = address_check.last(conn)
    if address is None or last is None or last.address != address:
        raise ApiError("ADDRESS_UNVERIFIED", "check the server address in Settings before adding a device", 409,
                       {"failed_checks": [], "checked": last is not None})
    failed = sorted(c.check for c in last.checks if c.check in BLOCKING_CHECKS and c.status == "fail")
    if failed:
        raise ApiError("ADDRESS_UNVERIFIED", "devices cannot reach this server address; fix it in Settings", 409,
                       {"failed_checks": failed, "checked": True})
    return address


def _check_target(conn: sqlite3.Connection, kind: SessionKind, target_device_id: str | None) -> None:
    if kind == "new":
        if target_device_id is not None:
            raise ApiError("INVALID_REQUEST", "target_device_id is only for kind 'reset'", 422)
        return
    target = devices.get(conn, target_device_id) if target_device_id else None
    if target is None:
        raise ApiError("DEVICE_NOT_FOUND", f"device {target_device_id} not found", 404)
    if target.status != "active":
        raise ApiError("DEVICE_NOT_ACTIVE", f"device {target_device_id} is {target.status}", 409)


def create_session(conn: sqlite3.Connection, settings: Settings, *, home_id: int, kind: SessionKind,
                   target_device_id: str | None, device_name: str, location: str | None,
                   actor: str) -> NewSession:
    """Open a wizard session: 409 WIZARD_OPEN while the home has one, 409 ADDRESS_UNVERIFIED (FR-4)."""
    conn.execute("BEGIN IMMEDIATE")  # serializes the one-open-wizard-per-home check with the insert
    expire_open(conn)
    require_home(conn, home_id)
    current = provisioning.open_for_home(conn, home_id)
    if current is not None:
        raise ApiError("WIZARD_OPEN", "this home already has an open provisioning wizard", 409,
                       {"session_id": current.id})
    _check_target(conn, kind, target_device_id)
    address = require_verified_address(conn, settings)
    token = secrets.token_hex(12)
    session = provisioning.create(
        conn, home_id, kind, device_name, token_digest(token), expires_at=(_now() + SESSION_TTL).isoformat(),
        actor=actor, target_device_id=target_device_id, location=location,
        status="awaiting_reset" if kind == "reset" else "awaiting_softap",
    )
    provisioning.add_event(conn, session.id, session.status, {"kind": kind})
    logger.info("provisioning session=%d opened home=%d kind=%s target=%s actor=%s",
                session.id, home_id, kind, target_device_id, actor)
    pairing_url = f"http://192.168.4.1/index.html?ott={token}&apiUrl={address}&deviceType=0"
    return NewSession(session, token, pairing_url, f"WIFI:T:WPA;S:{HOTSPOT_SSID};P:{HOTSPOT_PASSWORD};;")


def require_session(conn: sqlite3.Connection, session_id: int) -> ProvisioningSession:
    """A session after the on-access expiry check; 404 SESSION_NOT_FOUND."""
    expire_open(conn)
    session = provisioning.get(conn, session_id)
    if session is None:
        raise ApiError("SESSION_NOT_FOUND", f"provisioning session {session_id} not found", 404)
    return session


def session_status(repo: Repository, session_id: int) -> SessionStatus:
    """A session, its steps and (reset kind) when the target device next checks in; polled by the wizard."""
    with repo.db.connection() as conn:
        session = require_session(conn, session_id)
        # ponytail: a session logs a handful of steps; 500 (one page) bounds it without a cursor.
        steps = list(reversed(provisioning.list_events(conn, session.id, limit=MAX_LIMIT)))
        target = session.target_device_id
        last_sync = syncs.latest(conn, target) if target else None
    if target is None:
        return SessionStatus(session, steps, None)
    interval = repo.get_controls(target)["sync_interval_seconds"]
    return SessionStatus(session, steps, next_expected_sync(last_sync, interval))


def reset_mode(session: ProvisioningSession, local_device_access: bool) -> ResetMode | None:
    """``lan`` while the server may send the reset itself; ``manual`` (hold the reset button) otherwise."""
    if session.kind != "reset":
        return None
    failed = session.reset_result is not None and not session.reset_result.startswith("ok")
    return "lan" if local_device_access and not failed else "manual"


def _require_awaiting_reset(session: ProvisioningSession) -> None:
    if session.kind != "reset" or session.status != "awaiting_reset":
        raise ApiError("SESSION_STATE", f"session {session.id} is not waiting for a reset", 409,
                       {"status": session.status})


def enter_softap(conn: sqlite3.Connection, session: ProvisioningSession, step: str,
                 detail: dict[str, Any]) -> ProvisioningSession:
    """The device was reset: it is ``provisioning`` until it registers or the session ends (AD-4)."""
    if session.target_device_id is not None:
        devices.update(conn, session.target_device_id, {"status": "provisioning"})
    provisioning.add_event(conn, session.id, step, detail)
    updated = provisioning.update(conn, session.id, {"status": "awaiting_softap"})
    assert updated is not None
    return updated


def confirm_manual_reset(conn: sqlite3.Connection, session_id: int, actor: str) -> ProvisioningSession:
    """The operator held the device's reset button."""
    session = require_session(conn, session_id)
    _require_awaiting_reset(session)
    logger.info("provisioning session=%d manual reset confirmed actor=%s", session.id, actor)
    return enter_softap(conn, session, "manual_reset", {"actor": actor})


def _lan_target(conn: sqlite3.Connection, settings: Settings, session: ProvisioningSession) -> str:
    """The target's LAN address, only while LAN access is on and the device is mid-sync (awake, FR-4)."""
    def unavailable(reason: str, message: str) -> ApiError:
        return ApiError("LAN_RESET_UNAVAILABLE", message, 409, {"reason": reason})

    if not settings.local_device_access:
        raise unavailable("disabled", "this server cannot reach devices on its LAN; hold the reset button")
    assert session.target_device_id is not None
    latest = syncs.latest(conn, session.target_device_id)
    if latest is None or _now() - datetime.fromisoformat(latest.ended_at) > SYNC_GAP:
        raise unavailable("device_asleep", "the device is asleep; wake it (twist the bottle) and try again")
    report = telemetry.latest(conn, session.target_device_id)
    host = lan_reset.lan_address(report.payload.get("localIpAddress") if report else None)
    if host is None:
        raise unavailable("no_lan_address", "the device has not reported a private LAN address")
    return host


def _record_reset(conn: sqlite3.Connection, session_id: int, result: lan_reset.ResetResult,
                  actor: str) -> ProvisioningSession:
    """Store the one attempt's outcome; success moves the wizard on, failure switches it to manual."""
    session = require_session(conn, session_id)
    provisioning.update(conn, session.id, {"reset_requested_at": utcnow(), "reset_result": result.recorded})
    logger.info("provisioning session=%d LAN reset %s actor=%s", session.id, result.recorded, actor)
    detail = {"result": result.recorded, "actor": actor}
    if result.ok and session.status == "awaiting_reset":
        refreshed = provisioning.get(conn, session.id)
        assert refreshed is not None
        return enter_softap(conn, refreshed, "reset_sent", detail)
    provisioning.add_event(conn, session.id, "reset_sent" if result.ok else "reset_failed", detail)
    updated = provisioning.get(conn, session.id)
    assert updated is not None
    return updated


async def send_lan_reset(db: Database, settings: Settings, session_id: int, actor: str) -> ProvisioningSession:
    """LAN-direct factory reset (FR-4): checked in one transaction, sent once, recorded in another."""
    with db.connection() as conn:
        session = require_session(conn, session_id)
        _require_awaiting_reset(session)
        host = _lan_target(conn, settings, session)
    result = await lan_reset.send_factory_reset(host)
    with db.connection() as conn:
        return _record_reset(conn, session_id, result, actor)


def cancel(conn: sqlite3.Connection, session_id: int, actor: str) -> ProvisioningSession:
    session = require_session(conn, session_id)
    if session.status not in OPEN_STATUSES:
        raise ApiError("SESSION_STATE", f"session {session.id} is already {session.status}", 409,
                       {"status": session.status})
    _end(conn, session, "cancelled", {"actor": actor})
    logger.info("provisioning session=%d cancelled actor=%s", session.id, actor)
    updated = provisioning.get(conn, session.id)
    assert updated is not None
    return updated


def _end(conn: sqlite3.Connection, session: ProvisioningSession, status: Literal["expired", "cancelled"],
         detail: dict[str, Any]) -> None:
    """End an open session; a reset target that never registered returns to ``active``."""
    if status == "cancelled":
        provisioning.update(conn, session.id, {"status": "cancelled"})
    target = devices.get(conn, session.target_device_id) if session.target_device_id else None
    if target is not None and target.status == "provisioning":
        devices.update(conn, target.device_id, {"status": "active"})
    provisioning.add_event(conn, session.id, status, detail)


def expire_open(conn: sqlite3.Connection) -> list[int]:
    """Expire open sessions past ``expires_at`` (on every access, and by the 30 s sweep)."""
    expired = provisioning.expire_due(conn)
    for session_id in expired:
        session = provisioning.get(conn, session_id)
        assert session is not None
        _end(conn, session, "expired", {})
        logger.info("provisioning session=%d expired", session_id)
    return expired


async def sweep_forever(db: Database) -> None:
    """Every 30 s: expire sessions and prune pairing sightings older than 20 min. Errors never stop it."""
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_S)
        try:
            with db.connection() as conn:
                expire_open(conn)
                provisioning.prune_sightings(conn, (_now() - SIGHTING_TTL).isoformat())
        except Exception:  # a failed sweep must not stop the next one
            logger.exception("provisioning sweep failed")


# -- device side (/device-api/v2/healthcheck and register) -----------------------------------------------------


def observe_healthcheck(conn: sqlite3.Connection, device: Device | None, device_id: str,
                        source_ip: str | None) -> bool:
    """Advance sessions this healthcheck could belong to, and record a sighting while any awaits a join.

    Returns whether a session is ``awaiting_join`` (the unknown-ID healthcheck policy, AD-4).
    """
    expire_open(conn)
    for session in provisioning.awaiting_softap(conn, None if device is None else device_id):
        provisioning.update(conn, session.id, {"status": "awaiting_join"})
        provisioning.add_event(conn, session.id, "awaiting_join", {})
    joinable = provisioning.any_awaiting_join(conn)
    if joinable and source_ip:
        provisioning.record_sighting(conn, device_id, source_ip)
    return joinable


def _bind_device(conn: sqlite3.Connection, session: ProvisioningSession, device_id: str, source_ip: str) -> None:
    """Make the device ``active`` in the session's home with a fresh registration; a re-provisioned device's
    open bottle ends (``reset``: the factory reset wiped the cartridge state)."""
    now = utcnow()
    existing = devices.get(conn, device_id)
    if existing is None:
        devices.create(conn, device_id, "active", registered=True, home_id=session.home_id,
                       name=session.device_name, location=session.location, last_ip=source_ip, at=now)
    else:
        bottles.close_open(conn, device_id, "reset", at=now)
        devices.update(conn, device_id, {
            "status": "active", "registered": True, "home_id": session.home_id, "name": session.device_name,
            "location": session.location, "retire_requested_at": None, "last_seen": now, "last_ip": source_ip,
        })
    devices.add_registration(conn, device_id, session.ott_sha256, source_ip, at=now)
    provisioning.update(conn, session.id, {
        "status": "completed", "bound_device_id": device_id, "bound_ip": source_ip, "completed_at": now,
    })
    provisioning.add_event(conn, session.id, "completed", {"device_id": device_id})


def _rejected(conn: sqlite3.Connection, session: ProvisioningSession | None, reason: str, device_id: str,
              source_ip: str) -> ApiError:
    """Log (never the token) and answer a refused register with 422 NOT_FOUND."""
    if session is not None:
        provisioning.add_event(conn, session.id, reason, {"device_id": device_id, "source_ip": source_ip})
    logger.warning("register refused reason=%s session=%s device=%s ip=%s",
                   reason, session.id if session else None, device_id, source_ip)
    return _not_found()


def register(conn: sqlite3.Connection, device_id: str, ott: str | None, source_ip: str) -> ProvisioningSession:
    """Bind ``device_id`` to the session whose token it presents (AD-4); 422 NOT_FOUND otherwise.

    The caller must commit even when this raises, so the refusal's session event is kept.
    """
    expire_open(conn)
    session = provisioning.get_by_ott(conn, token_digest(ott)) if ott else None
    if session is None or session.status != "awaiting_join":
        raise _rejected(conn, session, "wrong_token" if session is None else "session_not_joinable",
                        device_id, source_ip)
    since = (_now() - SIGHTING_TTL).isoformat()
    sighting = provisioning.latest_sighting_for_ip(conn, source_ip, since)
    if sighting is None or sighting.device_id != device_id:
        raise _rejected(conn, session, "no_sighting", device_id, source_ip)
    if session.kind == "reset" and session.target_device_id != device_id:
        raise _rejected(conn, session, "session_device_mismatch", device_id, source_ip)
    _bind_device(conn, session, device_id, source_ip)
    logger.info("provisioning session=%d completed device=%s home=%d", session.id, device_id, session.home_id)
    completed = provisioning.get(conn, session.id)
    assert completed is not None
    return completed

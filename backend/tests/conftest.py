from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))

from app.config import Settings
from app.main import create_app
from app.repositories import devices, homes, provisioning
from app.repositories import settings as settings_repo
from app.services import schedule_rules, setup
from app.repositories.devices import DeviceStatus
from app.repositories.provisioning import SessionKind, SessionStatus


DEVICE_ID = "D8256700000A0001"


def mark_setup_ready(app: Any) -> Any:
    """First-run setup done (FR-16), so ``/api/v1`` is not gated. tests/test_setup.py covers the gate itself."""
    with app.state.db.connection() as conn:
        settings_repo.put(conn, setup.SETUP_STATE, "ready", "test")
    return app


def make_client(tmp_path, **overrides) -> tuple[TestClient, Any]:
    settings = Settings(db_path=str(tmp_path / "backend.db"), **overrides)
    app = mark_setup_ready(create_app(settings))
    return TestClient(app), app


def seed_device(app: Any, device_id: str = DEVICE_ID, status: DeviceStatus = "active") -> None:
    """Create the device row a provisioning session (B2.3) or a claim would create; no-op when it exists."""
    with app.state.db.connection() as conn:
        if devices.get(conn, device_id) is None:
            devices.create(conn, device_id, status)


def add_once_rule(app: Any, device_id: str = DEVICE_ID, at: int | None = None, dose_count: int = 1) -> int:
    """Turn dispensing and schedules on and add a once rule (default: a day ahead); returns its epoch."""
    at = at if at is not None else int(time.time()) + 86_400
    app.state.repo.update_controls(device_id, {"dispensing_enabled": True, "schedules_enabled": True})
    with app.state.db.connection() as conn:
        schedule_rules.create_rule(conn, device_id, {"kind": "once", "at_epoch": at, "dose_count": dose_count}, "test")
    return at


def register(client: TestClient, device_id: str = DEVICE_ID, ott: str = "ott-test"):
    """Pair ``device_id`` as the firmware does (AD-4): with a session for ``ott`` awaiting the join, one
    healthcheck (recording the sighting), then register with the token."""
    with client.app.state.db.connection() as conn:
        known = provisioning.get_by_ott(conn, hashlib.sha256(ott.encode()).hexdigest()) is not None
    if not known:
        pairing_session(client.app, ott)
    client.post("/device-api/v2/healthcheck", json={"deviceId": device_id}, headers={"x-device-id": device_id})
    return client.post(
        "/device-api/v2/register",
        json={"deviceId": device_id},
        headers={"x-device-ott": ott},
    )


def update_payload(**overrides) -> dict[str, Any]:
    payload = {
        "batteryLevel": 98,
        "firmwareVersion": "3.0.64",
        "connectionLevel": 100,
        "localIpAddress": "192.168.30.80",
        "bottleSensorStatus": "inserted",
        "networkName": "OpenFLO",
        "extPowerState": False,
        "isProVersion": False,
        "ramUsed": 120000,
        "ramTotal": 320000,
        "ramUsedPercent": 37,
        "HeapFailureCount": 0,
        "deviceType": 0,
        "pingQuality": 100,
        "pingLatency": 22,
        "pingFailureCount": 0,
        "dnsFailureCount": 0,
        "noAppMode": 0,
    }
    payload.update(overrides)
    return payload


def update(client: TestClient, device_id: str = DEVICE_ID, **overrides):
    return client.post(
        "/device-api/v2/update-device",
        json=update_payload(**overrides),
        headers={"x-device-id": device_id},
    )


@pytest.fixture
def client(tmp_path):
    c, _ = make_client(tmp_path)
    with c as test_client:
        yield test_client


@pytest.fixture
def app_client(tmp_path):
    c, app = make_client(tmp_path)
    with c as test_client:
        yield test_client, app


class FrozenClock:
    """Epoch-seconds clock for the device gate; moves only when a test advances it."""

    def __init__(self, start: float = 1_793_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


SOURCE_IP_HEADER = b"x-test-source-ip"


def _with_source_ip(app: Any) -> Any:
    """ASGI wrapper: the x-test-source-ip header becomes request.client (TestClient's peer is fixed)."""

    async def wrapped(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == SOURCE_IP_HEADER:
                    scope = {**scope, "client": (value.decode(), 50000)}
        await app(scope, receive, send)

    return wrapped


@pytest.fixture
def gated(tmp_path):
    """(client, app, clock): requests may set x-test-source-ip; the gate runs on a frozen clock."""
    app = mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "backend.db"))))
    clock = FrozenClock()
    app.state.device_gate.clock = clock
    with TestClient(_with_source_ip(app)) as test_client:
        yield test_client, app, clock


def pairing_session(
    app: Any, ott: str, *, kind: SessionKind = "new", target_device_id: str | None = None,
    status: SessionStatus = "awaiting_join", expires_at: str = "2999-01-01T00:00:00+00:00",
) -> provisioning.ProvisioningSession:
    """A provisioning session for the token ``ott`` in the "Test home" (sessions are driven by B2.3)."""
    with app.state.db.connection() as conn:
        home = homes.get_by_name(conn, "Test home") or homes.create(conn, "Test home", "UTC", "tester")
        return provisioning.create(
            conn, home.id, kind, "New device", hashlib.sha256(ott.encode()).hexdigest(),
            expires_at=expires_at, actor="tester", target_device_id=target_device_id, status=status,
        )


def open_awaiting_join_session(app: Any, expires_at: str = "2999-01-01T00:00:00+00:00") -> None:
    """A session waiting for a device to join, for the token ``session-ott``."""
    pairing_session(app, "session-ott", expires_at=expires_at)

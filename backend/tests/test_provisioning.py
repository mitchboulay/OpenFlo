"""Provisioning sessions bound by a one-time token (AD-4, FR-4), driven through the API and the device path."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import threading
from collections.abc import Iterator
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import bottles, devices, homes, profiles, provisioning
from app.repositories import settings as settings_repo
from app.services import lan_reset
from app.services import provisioning as provisioning_service
from app.services.address_check import ADDRESS_CHECK, AddressCheck, CheckResult
from app.services.server_address import SERVER_ADDRESS
from conftest import _with_source_ip, mark_setup_ready, update_payload

ADDRESS = "https://openflo.example.com"
NEW_ID = "AABBCCDDEEFF0011"
OTHER_ID = "AABBCCDDEEFF0022"
CHECKS = ("dns", "tls_no_sni", "chain_firmware_bundle", "leaf_rsa", "healthcheck_reachable", "port_non_443")


def store_check(app: Any, address: str = ADDRESS, failing: tuple[str, ...] = ()) -> None:
    result = AddressCheck(address, "2026-10-26T00:00:00+00:00",
                          [CheckResult(c, "fail" if c in failing else "ok", "") for c in CHECKS])  # type: ignore[arg-type]
    with app.state.db.connection() as conn:
        settings_repo.put(conn, SERVER_ADDRESS, ADDRESS, "test")
        settings_repo.put(conn, ADDRESS_CHECK, asdict(result), "test")


class Harness:
    """``none`` auth, a verified address, two homes; requests may come from any source IP."""

    def __init__(self, client: TestClient, app: Any) -> None:
        self.client, self.app = client, app
        store_check(app)
        with app.state.db.connection() as conn:
            self.home_a = homes.create(conn, "Alpha", "UTC", "tester").id
            self.home_b = homes.create(conn, "Beta", "UTC", "tester").id

    def open(self, home_id: int, kind: str = "new", target: str | None = None) -> Any:
        body = {"home_id": home_id, "kind": kind, "device_name": "Kitchen", "location": "Sink"}
        if target is not None:
            body["target_device_id"] = target
        return self.client.post("/api/v1/provisioning", json=body)

    def device(self, endpoint: str, device_id: str, ip: str = "10.0.0.5", ott: str | None = None,
               body: dict[str, Any] | None = None) -> Any:
        headers = {"x-device-id": device_id, "x-test-source-ip": ip}
        if ott is not None:
            headers = {"x-device-ott": ott, "x-test-source-ip": ip}
        return self.client.post(f"/device-api/v2/{endpoint}", json=body or {"deviceId": device_id},
                                headers=headers)

    def pair(self, device_id: str, token: str, ip: str = "10.0.0.5") -> Any:
        """The firmware's sequence: healthcheck until 200 (x3 here), then register."""
        for _ in range(3):
            assert self.device("healthcheck", device_id, ip).status_code == 200
        return self.device("register", device_id, ip, ott=token)

    def session(self, session_id: int) -> dict[str, Any]:
        response = self.client.get(f"/api/v1/provisioning/{session_id}")
        assert response.status_code == 200
        return response.json()

    def device_row(self, device_id: str) -> devices.Device | None:
        with self.app.state.db.connection() as conn:
            return devices.get(conn, device_id)


def _harness(tmp_path: Any, **overrides: Any) -> Iterator[Harness]:
    app = mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "p.db"), auth_mode="none", **overrides)))
    with TestClient(_with_source_ip(app)) as client:
        yield Harness(client, app)


@pytest.fixture
def h(tmp_path: Any) -> Iterator[Harness]:
    yield from _harness(tmp_path)


@pytest.fixture
def lan(tmp_path: Any) -> Iterator[Harness]:
    yield from _harness(tmp_path, local_device_access=True)


def _assert_not_found(response: Any) -> None:
    assert response.status_code == 422
    assert response.json() == {"code": "NOT_FOUND", "message": response.json()["message"]}  # never "fields"


def test_new_kind_happy_path_with_the_firmware_sequence(h: Harness) -> None:
    created = h.open(h.home_a)
    assert created.status_code == 201
    body = created.json()
    token = body["token"]
    assert re.fullmatch(r"[0-9a-f]{24}", token)
    assert body["pairing_url"] == f"http://192.168.4.1/index.html?ott={token}&apiUrl={ADDRESS}&deviceType=0"
    assert body["wifi_qr"] == "WIFI:T:WPA;S:iFLO device;P:13106423;;"
    session = body["session"]
    assert session["status"] == "awaiting_softap" and session["reset_mode"] is None
    assert h.pair(NEW_ID, token).status_code == 200
    assert h.device("update-device", NEW_ID, body=update_payload()).status_code == 200
    device = h.device_row(NEW_ID)
    assert device is not None and device.status == "active" and device.registered
    assert (device.home_id, device.name, device.location) == (h.home_a, "Kitchen", "Sink")
    status = h.session(session["id"])
    assert status["session"]["status"] == "completed" and status["session"]["bound_device_id"] == NEW_ID
    assert [s["step"] for s in status["steps"]] == ["awaiting_softap", "awaiting_join", "completed"]
    listed = h.client.get(f"/api/v1/homes/{h.home_a}/devices").json()
    assert [(d["device_id"], d["status"]) for d in listed] == [(NEW_ID, "active")]
    with h.app.state.db.connection() as conn:
        assert provisioning.get_by_ott(conn, hashlib.sha256(token.encode()).hexdigest()) is not None


def _seed_active_with_bottle(h: Harness) -> None:
    with h.app.state.db.connection() as conn:
        devices.create(conn, NEW_ID, "active", registered=True, home_id=h.home_a, name="Old")
        devices.add_registration(conn, NEW_ID, "0" * 64, "10.0.0.5")
        standard = profiles.get_system(conn, profiles.STANDARD)
        assert standard is not None
        bottles.open_bottle(conn, NEW_ID, standard.id, 1062.0, None)


def test_reset_kind_rotates_registration_and_closes_the_bottle(h: Harness) -> None:
    _seed_active_with_bottle(h)
    body = h.open(h.home_b, "reset", NEW_ID).json()
    session_id = body["session"]["id"]
    assert body["session"]["status"] == "awaiting_reset" and body["session"]["reset_mode"] == "manual"
    reset = h.client.post(f"/api/v1/provisioning/{session_id}/manual-reset")
    assert reset.status_code == 200 and reset.json()["status"] == "awaiting_softap"
    assert h.device_row(NEW_ID).status == "provisioning"  # type: ignore[union-attr]
    assert h.pair(NEW_ID, body["token"]).status_code == 200
    device = h.device_row(NEW_ID)
    assert device is not None and device.status == "active" and device.home_id == h.home_b
    with h.app.state.db.connection() as conn:
        assert bottles.open_for_device(conn, NEW_ID) is None
        closed = bottles.list_for_device(conn, NEW_ID)[0]
        rows = conn.execute("SELECT ott_sha256 FROM registrations WHERE device_id = ? ORDER BY id", (NEW_ID,))
        digests = [row[0] for row in rows]
    assert closed.end_reason == "reset"
    assert digests == ["0" * 64, hashlib.sha256(body["token"].encode()).hexdigest()]


def test_session_device_mismatch_is_refused_and_logged(h: Harness, caplog: Any) -> None:
    _seed_active_with_bottle(h)
    body = h.open(h.home_a, "reset", NEW_ID).json()
    session_id = body["session"]["id"]
    h.client.post(f"/api/v1/provisioning/{session_id}/manual-reset")
    assert h.device("healthcheck", NEW_ID, "10.0.0.5").status_code == 200  # target found: awaiting_join
    assert h.device("healthcheck", OTHER_ID, "10.0.0.9").status_code == 200  # unknown ID sighted
    with caplog.at_level(logging.WARNING):
        _assert_not_found(h.device("register", OTHER_ID, "10.0.0.9", ott=body["token"]))
    assert "session_device_mismatch" in caplog.text
    assert [s["step"] for s in h.session(session_id)["steps"]][-1] == "session_device_mismatch"
    assert h.device_row(OTHER_ID) is None
    assert h.pair(NEW_ID, body["token"]).status_code == 200  # the real target still completes


def test_wrong_or_absent_token_is_not_found_without_fields(h: Harness) -> None:
    h.open(h.home_a)
    assert h.device("healthcheck", NEW_ID).status_code == 200
    _assert_not_found(h.device("register", NEW_ID, ott="f" * 24))
    _assert_not_found(h.client.post("/device-api/v2/register", json={"deviceId": NEW_ID},
                                    headers={"x-test-source-ip": "10.0.0.5"}))
    assert h.device_row(NEW_ID) is None


def test_register_needs_a_sighting_from_the_same_ip(h: Harness) -> None:
    token = h.open(h.home_a).json()["token"]
    assert h.device("healthcheck", NEW_ID, "10.0.0.5").status_code == 200
    _assert_not_found(h.device("register", NEW_ID, "10.0.0.6", ott=token))
    assert h.device("register", NEW_ID, "10.0.0.5", ott=token).status_code == 200


def _expire(h: Harness, session_id: int) -> None:
    with h.app.state.db.connection() as conn:
        conn.execute("UPDATE provisioning_sessions SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
                     (session_id,))


def test_expiry_on_access_releases_the_target(h: Harness) -> None:
    _seed_active_with_bottle(h)
    body = h.open(h.home_a, "reset", NEW_ID).json()
    session_id = body["session"]["id"]
    h.client.post(f"/api/v1/provisioning/{session_id}/manual-reset")
    _expire(h, session_id)
    assert h.session(session_id)["session"]["status"] == "expired"
    assert h.device_row(NEW_ID).status == "active"  # type: ignore[union-attr]
    _assert_not_found(h.device("register", NEW_ID, ott=body["token"]))
    assert h.open(h.home_a).status_code == 201  # an expired wizard no longer blocks the home


def test_unknown_healthcheck_closes_after_expiry(h: Harness) -> None:
    session_id = h.open(h.home_a).json()["session"]["id"]
    assert h.device("healthcheck", NEW_ID).status_code == 200
    _expire(h, session_id)
    response = h.device("healthcheck", NEW_ID)
    assert response.status_code == 422 and response.json()["code"] == "DEVICE_NOT_REGISTERED"


def test_sweep_expires_sessions_and_prunes_sightings(h: Harness, monkeypatch: Any) -> None:
    session_id = h.open(h.home_a).json()["session"]["id"]
    _expire(h, session_id)
    with h.app.state.db.connection() as conn:
        provisioning.record_sighting(conn, NEW_ID, "10.0.0.5", at="2000-01-01T00:00:00+00:00")
    monkeypatch.setattr(provisioning_service, "SWEEP_INTERVAL_S", 0.01)

    async def one_sweep() -> None:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(provisioning_service.sweep_forever(h.app.state.db), 0.2)

    asyncio.run(one_sweep())
    with h.app.state.db.connection() as conn:
        assert provisioning.get(conn, session_id).status == "expired"  # type: ignore[union-attr]
        assert conn.execute("SELECT COUNT(*) FROM pairing_sightings").fetchone()[0] == 0


def test_two_homes_provision_concurrently(h: Harness) -> None:
    token_a = h.open(h.home_a).json()["token"]
    token_b = h.open(h.home_b).json()["token"]
    wizard_open = h.open(h.home_a)
    assert wizard_open.status_code == 409 and wizard_open.json()["code"] == "WIZARD_OPEN"
    assert h.device("healthcheck", NEW_ID, "10.0.0.5").status_code == 200
    assert h.device("healthcheck", OTHER_ID, "10.0.1.5").status_code == 200
    assert h.device("register", OTHER_ID, "10.0.1.5", ott=token_b).status_code == 200
    assert h.device("register", NEW_ID, "10.0.0.5", ott=token_a).status_code == 200
    assert h.device_row(NEW_ID).home_id == h.home_a  # type: ignore[union-attr]
    assert h.device_row(OTHER_ID).home_id == h.home_b  # type: ignore[union-attr]


@pytest.mark.parametrize("address, failing", [
    (ADDRESS, ("tls_no_sni",)),
    (ADDRESS, ("chain_firmware_bundle", "leaf_rsa")),
    ("https://old.example.com", ()),
])
def test_address_unverified_blocks_provisioning(h: Harness, address: str, failing: tuple[str, ...]) -> None:
    store_check(h.app, address, failing)
    response = h.open(h.home_a)
    assert response.status_code == 409
    assert response.json()["code"] == "ADDRESS_UNVERIFIED"
    assert response.json()["detail"]["failed_checks"] == sorted(failing)


def test_warnings_outside_the_tls_checks_do_not_block(h: Harness) -> None:
    store_check(h.app, ADDRESS, ("dns", "healthcheck_reachable"))
    assert h.open(h.home_a).status_code == 201


class _StubDevice(BaseHTTPRequestHandler):
    status = 200
    posts: list[tuple[str, Any]] = []

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        length = int(self.headers.get("content-length", 0))
        type(self).posts.append((self.path, json.loads(self.rfile.read(length))))
        self.send_response(self.status)
        self.end_headers()

    def log_message(self, *_: Any) -> None:
        return


@pytest.fixture
def stub_device(monkeypatch: Any) -> Iterator[type[_StubDevice]]:
    handler = type("Stub", (_StubDevice,), {"posts": [], "status": 200})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(lan_reset, "LAN_RESET_PORT", server.server_address[1])
    # The stub listens on loopback, which the private-LAN guard refuses (tested separately below).
    monkeypatch.setattr(lan_reset, "lan_address", lambda value: value)
    yield handler
    server.shutdown()


def _awake_reset_session(h: Harness) -> tuple[int, str]:
    _seed_active_with_bottle(h)
    body = h.open(h.home_a, "reset", NEW_ID).json()
    assert body["session"]["reset_mode"] == "lan"
    sync = h.device("update-device", NEW_ID, body=update_payload(localIpAddress="127.0.0.1"))
    assert sync.status_code == 200  # the device is mid-sync
    return body["session"]["id"], body["token"]


def test_lan_reset_is_sent_once_and_recorded(lan: Harness, stub_device: type[_StubDevice]) -> None:
    session_id, _ = _awake_reset_session(lan)
    reset = lan.client.post(f"/api/v1/provisioning/{session_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "awaiting_softap" and reset.json()["reset_result"] == "ok: HTTP 200"
    assert stub_device.posts == [("/dev_actions", {"restoreToDefault": True})]
    again = lan.client.post(f"/api/v1/provisioning/{session_id}/reset")
    assert again.status_code == 409 and again.json()["code"] == "SESSION_STATE"
    assert len(stub_device.posts) == 1
    assert lan.device_row(NEW_ID).status == "provisioning"  # type: ignore[union-attr]


def test_failed_lan_reset_is_not_retried_and_falls_back_to_manual(
    lan: Harness, stub_device: type[_StubDevice]
) -> None:
    stub_device.status = 500
    session_id, _ = _awake_reset_session(lan)
    reset = lan.client.post(f"/api/v1/provisioning/{session_id}/reset").json()
    assert (reset["status"], reset["reset_mode"], reset["reset_result"]) == (
        "awaiting_reset", "manual", "failed: HTTP 500")
    assert len(stub_device.posts) == 1
    assert lan.client.post(f"/api/v1/provisioning/{session_id}/manual-reset").json()["status"] == "awaiting_softap"


def test_lan_reset_needs_the_flag_and_an_open_sync(h: Harness) -> None:
    _seed_active_with_bottle(h)
    session_id = h.open(h.home_a, "reset", NEW_ID).json()["session"]["id"]
    disabled = h.client.post(f"/api/v1/provisioning/{session_id}/reset")
    assert disabled.status_code == 409 and disabled.json()["detail"] == {"reason": "disabled"}
    h.app.state.settings = Settings(db_path=h.app.state.settings.db_path, local_device_access=True,
                                    auth_mode="none")
    asleep = h.client.post(f"/api/v1/provisioning/{session_id}/reset")
    assert asleep.status_code == 409 and asleep.json()["detail"] == {"reason": "device_asleep"}


@pytest.mark.parametrize("value, expected", [
    ("192.168.30.80", "192.168.30.80"), ("10.1.2.3", "10.1.2.3"), ("127.0.0.1", None), ("8.8.8.8", None),
    ("169.254.1.1", None), ("not-an-ip", None), (None, None),
])
def test_lan_address_accepts_private_unicast_only(value: Any, expected: str | None) -> None:
    assert lan_reset.lan_address(value) == expected


def test_token_never_reaches_logs_or_storage(h: Harness, caplog: Any) -> None:
    with caplog.at_level(logging.DEBUG):
        token = h.open(h.home_a).json()["token"]
        assert h.pair(NEW_ID, token).status_code == 200
        _assert_not_found(h.device("register", NEW_ID, ott=token))  # replay, logged as a refusal
    assert token not in caplog.text
    assert all(token not in str(row) for row in h.app.state.repo.recent_logs(100))
    with h.app.state.db.connection() as conn:
        assert token not in "\n".join(conn.iterdump())

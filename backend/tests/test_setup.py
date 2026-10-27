"""First-run setup (FR-16): the SETUP_REQUIRED gate, the wizard steps, the server-address seed and precedence."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import ApiError
from app.main import create_app
from app.services import address_check, oidc, server_address
from app.services.address_check import AddressCheck, CheckResult, CheckTarget

API = "/api/v1"
PASSWORD = "correct horse battery"
CROSS_SITE = {"Sec-Fetch-Site": "cross-site"}


@pytest.fixture
def fake_checks(monkeypatch: pytest.MonkeyPatch) -> list[CheckTarget]:
    """``address_check.run`` without the network: every check ok, the targets recorded."""
    targets: list[CheckTarget] = []

    async def run(target: CheckTarget) -> AddressCheck:
        targets.append(target)
        return AddressCheck(target.address.url, "2026-10-26T12:00:00+00:00",
                            [CheckResult(name, "ok", "fine") for name, _ in address_check.CHECKS])

    monkeypatch.setattr(address_check, "run", run)
    return targets


def _client(tmp_path: Any, **overrides: Any) -> Iterator[TestClient]:
    settings = Settings(db_path=str(tmp_path / "setup.db"), **{"auth_mode": "basic", **overrides})
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        yield client


@pytest.fixture
def client(tmp_path: Any) -> Iterator[TestClient]:
    yield from _client(tmp_path)


def steps(client: TestClient) -> dict[str, str]:
    response = client.get(f"{API}/setup")
    assert response.status_code == 200
    return response.json()["steps"]


def walk_setup(client: TestClient, address: str = "https://flo.example.com") -> None:
    assert client.post(f"{API}/setup/admin", json={"username": "admin", "password": PASSWORD}).status_code == 204
    assert client.put(f"{API}/settings/server-address", json={"server_address": address}).status_code == 200
    assert client.post(f"{API}/settings/server-address/check").status_code == 200
    assert client.post(f"{API}/setup/complete").json() == {"setup_state": "ready"}


@pytest.mark.parametrize("path", ["/homes", "/devices/unclaimed", "/tokens", "/me", "/nope"])
def test_management_routes_are_gated_until_setup_is_done(client: TestClient, path: str) -> None:
    response = client.get(API + path)
    assert response.status_code == 409
    assert response.json()["code"] == "SETUP_REQUIRED"


def test_login_is_gated_too(client: TestClient) -> None:
    response = client.post(f"{API}/auth/login", json={"username": "a", "password": "b"})
    assert response.status_code == 409 and response.json()["code"] == "SETUP_REQUIRED"


def test_exempt_routes_answer_during_setup(client: TestClient) -> None:
    assert client.get("/healthz").json()["setup_state"] == "setup_required"
    assert client.get(f"{API}/server-info").json()["setup_state"] == "setup_required"
    assert client.get(f"{API}/openapi.json").status_code == 200
    assert client.get(f"{API}/setup").json()["setup_state"] == "setup_required"
    # The device API is never gated (unknown device: the device gate's answer, not SETUP_REQUIRED).
    assert client.post("/device-api/v2/update-device", json={}).json()["code"] != "SETUP_REQUIRED"


def test_wizard_steps_then_ready(client: TestClient, fake_checks: list[CheckTarget]) -> None:
    assert steps(client) == {"auth": "pending", "server_address": "pending", "address_check": "pending"}
    incomplete = client.post(f"{API}/setup/complete")
    assert incomplete.status_code == 409 and incomplete.json()["code"] == "SETUP_INCOMPLETE"
    assert incomplete.json()["detail"]["auth"] == "pending"

    walk_setup(client)

    assert [t.address.url for t in fake_checks] == ["https://flo.example.com"]
    assert client.get(f"{API}/homes").status_code == 200  # creating the admin signed the wizard in
    client.cookies.clear()
    assert client.get(f"{API}/homes").status_code == 401  # ungated; now it needs a sign-in
    assert client.get(f"{API}/setup").status_code == 401  # the wizard is no longer open
    login = client.post(f"{API}/auth/login", json={"username": "admin", "password": PASSWORD})
    assert login.status_code == 204
    assert client.get(f"{API}/homes").status_code == 200
    assert client.post(f"{API}/setup/complete", headers={"Sec-Fetch-Site": "same-origin"}).json() == {
        "setup_state": "ready"}


def test_admin_rules(client: TestClient) -> None:
    weak = client.post(f"{API}/setup/admin", json={"username": "admin", "password": "short"})
    assert weak.status_code == 422 and weak.json()["code"] == "WEAK_PASSWORD"
    assert "openflo_session" not in weak.headers.get("set-cookie", "")
    assert client.post(f"{API}/setup/admin", json={"username": "admin", "password": PASSWORD}).status_code == 204
    client.cookies.clear()
    again = client.post(f"{API}/setup/admin", json={"username": "other", "password": PASSWORD})
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_SET"
    assert "openflo_session" not in again.headers.get("set-cookie", "")
    assert steps(client)["auth"] == "done"


def test_creating_the_admin_signs_in(client: TestClient, fake_checks: list[CheckTarget]) -> None:
    created = client.post(f"{API}/setup/admin", json={"username": " admin ", "password": PASSWORD})
    cookie = created.headers["set-cookie"]
    assert created.status_code == 204 and cookie.startswith("openflo_session=")
    for flag in ("httponly", "secure", "samesite=lax"):  # the same cookie as /auth/login
        assert flag in cookie.lower()
    walk_rest = (client.put(f"{API}/settings/server-address", json={"server_address": "https://flo.example.com"}),
                 client.post(f"{API}/settings/server-address/check"), client.post(f"{API}/setup/complete"))
    assert [r.status_code for r in walk_rest] == [200, 200, 200]
    assert client.get(f"{API}/me").json() == {"actor": "user:admin", "auth_mode": "basic", "method": "session"}
    assert client.post(f"{API}/homes", json={"name": "Cabin"}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 201


def test_cross_site_browser_cannot_drive_the_wizard(client: TestClient) -> None:
    response = client.post(f"{API}/setup/admin", json={"username": "admin", "password": PASSWORD},
                           headers=CROSS_SITE)
    assert response.status_code == 403 and response.json()["code"] == "CSRF_REJECTED"


def test_none_and_proxy_modes_need_no_auth_step(tmp_path: Any) -> None:
    for mode, extra in (("none", {}), ("proxy", {"trusted_proxy_cidr": "10.0.0.0/8"})):
        for c in _client(tmp_path / mode, auth_mode=mode, **extra):
            assert steps(c)["auth"] == "done"
            wrong = c.post(f"{API}/setup/admin", json={"username": "admin", "password": PASSWORD})
            assert wrong.status_code == 409 and wrong.json()["code"] == "WRONG_AUTH_MODE"


def test_env_seed_then_db_precedence(tmp_path: Any, fake_checks: list[CheckTarget]) -> None:
    for c in _client(tmp_path, public_url="https://seed.example.com:8443/"):
        assert steps(c)["server_address"] == "done"
        assert c.get(f"{API}/server-info").json()["server_address"] == "https://seed.example.com:8443"
        c.post(f"{API}/settings/server-address/check")
        assert fake_checks[-1].address.url == "https://seed.example.com:8443"
        assert steps(c)["address_check"] == "ok"

        saved = c.put(f"{API}/settings/server-address", json={"server_address": "https://Saved.example.com:443"})
        assert saved.json() == {"server_address": "https://saved.example.com"}
        assert c.get(f"{API}/server-info").json()["server_address"] == "https://saved.example.com"
        assert steps(c)["address_check"] == "pending"  # the last check was for another address
    # A restart with a different env value: the saved address still wins.
    for c in _client(tmp_path, public_url="https://other.example.com"):
        assert c.get(f"{API}/server-info").json()["server_address"] == "https://saved.example.com"


def test_address_check_needs_an_address(client: TestClient) -> None:
    response = client.post(f"{API}/settings/server-address/check")
    assert response.status_code == 409 and response.json()["code"] == "ADDRESS_NOT_SET"
    assert client.get(f"{API}/settings/server-address/check").json()["code"] == "NOT_CHECKED"


def test_failing_check_is_stored_and_degrades_healthz(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(target: CheckTarget) -> AddressCheck:
        return AddressCheck(target.address.url, "2026-10-26T03:00:00+00:00",
                            [CheckResult("chain_firmware_bundle", "fail", "not ISRG Root X1")])

    monkeypatch.setattr(address_check, "run", failing)
    assert client.get("/healthz").json()["degraded"] == []
    client.put(f"{API}/settings/server-address", json={"server_address": "https://flo.example.com"})
    assert client.post(f"{API}/settings/server-address/check").json()["checks"][0]["status"] == "fail"
    assert client.get(f"{API}/settings/server-address/check").json()["address"] == "https://flo.example.com"
    assert client.get("/healthz").json()["degraded"] == ["address_check_failed"]
    assert steps(client)["address_check"] == "fail"  # a failing check does not block setup (FR-16)


@pytest.mark.parametrize("raw", [
    "flo.example.com", "ftp://flo.example.com", "https://flo.example.com/api", "https://u:p@flo.example.com",
    "https://flo.example.com?x=1", "https://flo.example.com:99999", "https://",
])
def test_invalid_addresses_are_refused(client: TestClient, raw: str) -> None:
    response = client.put(f"{API}/settings/server-address", json={"server_address": raw})
    assert response.status_code == 422 and response.json()["code"] == "ADDRESS_INVALID"


@pytest.mark.parametrize("raw, url", [
    ("https://FLO.example.com/", "https://flo.example.com"),
    ("https://flo.example.com:8443", "https://flo.example.com:8443"),
    ("http://192.168.1.5:8099", "http://192.168.1.5:8099"),
    ("https://[fd00::1]:443", "https://[fd00::1]"),
])
def test_address_normalization(raw: str, url: str) -> None:
    assert server_address.parse(raw).url == url


def test_oidc_auth_step_follows_discovery(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oidc, "IDP_RETRY_DELAY_S", 0.0)
    issuer = "https://idp.test/o/openflo"
    with respx.mock(assert_all_called=False) as router:
        discovery = router.get(f"{issuer}/.well-known/openid-configuration")
        discovery.side_effect = httpx.ConnectError("down")
        for c in _client(tmp_path, auth_mode="oidc", oidc_issuer=issuer, oidc_client_id="openflo"):
            assert steps(c)["auth"] == "pending"
            discovery.side_effect = None
            discovery.respond(json={"issuer": issuer, "authorization_endpoint": f"{issuer}/authorize"})
            assert steps(c)["auth"] == "done"


def test_invalid_env_seed_is_ignored(tmp_path: Any) -> None:
    for c in _client(tmp_path, public_url="not a url"):
        assert steps(c)["server_address"] == "pending"
    with pytest.raises(ApiError):
        server_address.parse("not a url")

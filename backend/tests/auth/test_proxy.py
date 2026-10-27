"""Proxy mode (FR-15): user headers count only from OPENFLO_TRUSTED_PROXY_CIDR; spoofed ones are ignored."""
from __future__ import annotations

from typing import Any

import pytest

from .conftest import API, SAME_ORIGIN, auth_client

TRUSTED = "10.0.0.5"
SPOOFER = "203.0.113.9"


def _me(client: Any, ip: str, **headers: str) -> Any:
    return client.get(f"{API}/me", headers={"x-test-source-ip": ip, **headers})


@pytest.mark.parametrize("header", ["Remote-User", "X-authentik-username"])
def test_trusted_proxy_headers(tmp_path: Any, header: str) -> None:
    with auth_client(tmp_path, auth_mode="proxy", trusted_proxy_cidr="10.0.0.0/24") as (client, _):
        assert _me(client, TRUSTED, **{header: "alice"}).json() == {
            "actor": "proxy:alice", "auth_mode": "proxy", "method": "proxy"}


def test_email_header_is_the_fallback_identity(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="proxy", trusted_proxy_cidr="10.0.0.0/24") as (client, _):
        assert _me(client, TRUSTED, **{"Remote-Email": "a@example.com"}).json()["actor"] == "proxy:a@example.com"


def test_spoofed_headers_from_another_ip_are_ignored(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="proxy", trusted_proxy_cidr="10.0.0.0/24") as (client, _):
        for headers in ({"Remote-User": "alice"}, {"X-authentik-username": "alice"}):
            response = _me(client, SPOOFER, **headers)
            assert response.status_code == 401 and response.json()["code"] == "AUTH_REQUIRED"
        assert _me(client, TRUSTED).status_code == 401  # trusted peer, but no user header


def test_several_cidrs_and_ipv6(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="proxy", trusted_proxy_cidr="10.0.0.0/24, fd00::/8") as (client, _):
        assert _me(client, "fd00::1", **{"Remote-User": "bob"}).status_code == 200
        assert _me(client, "fe80::1", **{"Remote-User": "bob"}).status_code == 401


def test_proxy_headers_ignored_in_other_modes(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic", trusted_proxy_cidr="10.0.0.0/24") as (client, _):
        assert _me(client, TRUSTED, **{"Remote-User": "alice"}).status_code == 401


def test_allowed_groups_apply_to_proxy_users(tmp_path: Any) -> None:
    settings = {"auth_mode": "proxy", "trusted_proxy_cidr": "10.0.0.0/24", "oidc_allowed_groups": ("ops",)}
    with auth_client(tmp_path, **settings) as (client, _):
        denied = _me(client, TRUSTED, **{"Remote-User": "eve", "Remote-Groups": "staff,guests"})
        assert denied.status_code == 403 and denied.json()["code"] == "GROUP_DENIED"
        assert _me(client, TRUSTED, **{"X-authentik-username": "al", "X-authentik-groups": "staff|ops"}).status_code == 200


def test_proxy_mutations_need_same_origin(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="proxy", trusted_proxy_cidr="10.0.0.0/24") as (client, app):
        headers = {"x-test-source-ip": TRUSTED, "Remote-User": "alice"}
        refused = client.post(f"{API}/homes", json={"name": "Cabin"}, headers=headers)
        assert refused.status_code == 403 and refused.json()["code"] == "CSRF_REJECTED"
        created = client.post(f"{API}/homes", json={"name": "Cabin"}, headers={**headers, **SAME_ORIGIN})
        assert created.status_code == 201
        with app.state.db.connection() as conn:
            assert conn.execute("SELECT actor FROM homes").fetchone()[0] == "proxy:alice"

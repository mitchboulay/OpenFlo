"""Startup refusals (Security NFR) and the unauthenticated ``/server-info`` (FR-17)."""
from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings, StartupRefused
from app.main import create_app

from .conftest import API, auth_client


@pytest.mark.parametrize(("overrides", "message"), [
    ({"auth_mode": "none", "public": True}, "OPENFLO_PUBLIC=true"),
    ({"auth_mode": "proxy"}, "requires OPENFLO_TRUSTED_PROXY_CIDR"),
    ({"auth_mode": "proxy", "trusted_proxy_cidr": "not-a-cidr"}, "invalid"),
    ({"auth_mode": "oidc", "oidc_client_id": "c"}, "OPENFLO_OIDC_ISSUER"),
    ({"auth_mode": "oidc", "oidc_issuer": "https://idp.example"}, "OPENFLO_OIDC_CLIENT_ID"),
])
def test_refused(tmp_path: Any, overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(StartupRefused, match=message):
        create_app(Settings(db_path=str(tmp_path / "x.db"), **overrides))
    assert not (tmp_path / "x.db").exists()  # refused before touching the data dir


@pytest.mark.parametrize("overrides", [
    {"auth_mode": "none", "public": False},
    {"auth_mode": "basic", "public": True},
    {"auth_mode": "proxy", "public": True, "trusted_proxy_cidr": "172.30.0.0/16"},
    {"auth_mode": "oidc", "public": True, "oidc_issuer": "https://idp.example", "oidc_client_id": "c"},
])
def test_allowed(tmp_path: Any, overrides: dict[str, Any]) -> None:
    create_app(Settings(db_path=str(tmp_path / "x.db"), **overrides))


def test_server_info_is_public_and_cacheable(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        response = client.get(f"{API}/server-info")
        assert response.status_code == 200 and response.headers["cache-control"] == "public, max-age=60"
        body = response.json()
        with app.state.db.connection() as conn:
            instance_id = conn.execute("SELECT value_json FROM settings WHERE key = 'instance_id'").fetchone()[0]
        assert body == {
            "name": "OpenFLO", "version": app.state.settings.emulator_version, "api_version": "1",
            "instance_id": instance_id.strip('"'), "setup_state": "ready",
            "auth": {"mode": "basic", "methods": ["password", "token"], "oidc_issuer": None, "oidc_client_id": None},
            "server_address": None,
        }

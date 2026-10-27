"""CSRF (FR-15): cookie-authenticated mutations need ``Sec-Fetch-Site: same-origin``; bearer actors skip it."""
from __future__ import annotations

from typing import Any

import pytest

from app.services.auth_policy import csrf_ok

from .conftest import API, SAME_ORIGIN, auth_client, create_admin, login

TOKEN = "bootstrap-token-0123456789"


def _post_home(client: Any, name: str, **headers: str) -> Any:
    return client.post(f"{API}/homes", json={"name": name}, headers=headers)


def test_session_mutations_need_same_origin(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        assert login(client).status_code == 204
        for headers in ({}, {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"}):
            refused = _post_home(client, "A", **headers)
            assert refused.status_code == 403 and refused.json()["code"] == "CSRF_REJECTED"
        assert _post_home(client, "A", **SAME_ORIGIN).status_code == 201
        assert client.get(f"{API}/homes").status_code == 200  # reads are not gated


def test_bearer_actors_skip_csrf(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic", api_token=TOKEN) as (client, app):
        create_admin(app)
        login(client)  # a session cookie too: the bearer still wins (AD-8 order)
        response = _post_home(client, "B", Authorization=f"Bearer {TOKEN}", **{"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 201


def test_none_mode_refuses_browser_cross_site_only(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="none") as (client, _):
        assert _post_home(client, "C").status_code == 201  # curl/scripts send no Sec-Fetch-Site
        refused = _post_home(client, "D", **{"Sec-Fetch-Site": "cross-site"})
        assert refused.status_code == 403 and refused.json()["code"] == "CSRF_REJECTED"


def test_device_api_is_untouched(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, _):
        response = client.post("/device-api/v2/healthcheck", json={}, headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code != 403


@pytest.mark.parametrize(("method", "actor", "site", "ok"), [
    ("GET", "session", None, True),
    ("DELETE", "session", None, False),
    ("PATCH", "proxy", "same-origin", True),
    ("POST", "token", "cross-site", True),
    ("PUT", "none", "none", True),
])
def test_policy_table(method: str, actor: Any, site: str | None, ok: bool) -> None:
    assert csrf_ok(method, actor, site) is ok

"""Personal API tokens (FR-15, AD-10): shown once, SHA-256 stored, 8-char fingerprint, revocable, expiring."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import pytest

from .conftest import API, PASSWORD, SAME_ORIGIN, auth_client, create_admin, login


def _create(client: Any, **body: Any) -> dict[str, Any]:
    response = client.post(f"{API}/tokens", json={"name": "laptop", **body}, headers=SAME_ORIGIN)
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_list_use_and_revoke(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        login(client)
        created = _create(client)
        plaintext = created.pop("token")
        digest = hashlib.sha256(plaintext.encode()).hexdigest()
        assert plaintext.startswith("ofl_") and created["fingerprint"] == digest[:8]
        assert created["kind"] == "personal" and created["expires_at"] is None
        listed = client.get(f"{API}/tokens").json()
        assert listed == [created]  # no plaintext, no hash
        with app.state.db.connection() as conn:
            rows = conn.execute("SELECT token_sha256, actor FROM api_tokens").fetchall()
        assert [tuple(r) for r in rows] == [(digest, "user:admin")]

        client.cookies.clear()
        me = client.get(f"{API}/me", headers=_bearer(plaintext)).json()
        assert me == {"actor": "user:admin", "auth_mode": "basic", "method": "token"}
        assert client.delete(f"{API}/tokens/{created['id']}", headers=_bearer(plaintext)).status_code == 204
        assert client.get(f"{API}/me", headers=_bearer(plaintext)).json()["code"] == "INVALID_TOKEN"


def test_revoking_twice_or_unknown_is_404(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="none") as (client, _):
        token_id = _create(client)["id"]
        assert client.delete(f"{API}/tokens/{token_id}").status_code == 204
        response = client.delete(f"{API}/tokens/{token_id}")
        assert response.status_code == 404 and response.json()["code"] == "TOKEN_NOT_FOUND"
        assert client.get(f"{API}/tokens").json() == []


def test_expiry(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic", api_token="bootstrap-token-0123456789") as (client, app):
        boot = _bearer("bootstrap-token-0123456789")
        created = client.post(f"{API}/tokens", json={"name": "ci", "expires_in_days": 30}, headers=boot).json()
        assert created["expires_at"] is not None
        assert client.get(f"{API}/me", headers=_bearer(created["token"])).status_code == 200
        with app.state.db.connection() as conn:
            conn.execute("UPDATE api_tokens SET expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
                         (created["id"],))
        assert client.get(f"{API}/me", headers=_bearer(created["token"])).json()["code"] == "INVALID_TOKEN"


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "x", "expires_in_days": 0}, {"name": "x", "extra": 1}])
def test_create_validation(tmp_path: Any, body: dict[str, Any]) -> None:
    with auth_client(tmp_path, auth_mode="none") as (client, _):
        assert client.post(f"{API}/tokens", json=body).status_code == 422


def test_tokens_require_an_actor(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, _):
        assert client.get(f"{API}/tokens").json()["code"] == "AUTH_REQUIRED"
        assert client.post(f"{API}/tokens", json={"name": "x"}).json()["code"] == "AUTH_REQUIRED"


def test_passwords_and_tokens_never_reach_the_logs(tmp_path: Any, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    bootstrap = "bootstrap-token-0123456789"
    with auth_client(tmp_path, auth_mode="basic", api_token=bootstrap) as (client, app):
        create_admin(app)
        login(client, password="a wrong password guess")
        login(client)
        plaintext = _create(client)["token"]
        client.get(f"{API}/me", headers=_bearer(plaintext))
        client.get(f"{API}/me", headers=_bearer("ofl_not-a-real-token"))
    logged = caplog.text
    assert "login user:admin" in logged and "failed login" in logged  # the flow did log
    for secret in (PASSWORD, "a wrong password guess", plaintext, bootstrap, "ofl_not-a-real-token"):
        assert secret not in logged

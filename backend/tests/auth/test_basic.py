"""Basic mode (FR-15): argon2 login, session cookie flags, rate limit, 12 h idle expiry, secret.key."""
from __future__ import annotations

import os
import stat
from typing import Any

import pytest
from argon2 import PasswordHasher
from itsdangerous import TimestampSigner

from app.errors import ApiError
from app.main import SESSION_COOKIE, SESSION_IDLE_SECONDS
from app.services import basic_auth
from app.services.auth_policy import SlidingWindowLimiter

from .conftest import ADMIN, API, PASSWORD, auth_client, create_admin, login


def test_login_sets_a_hardened_session_cookie(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        response = login(client)
        assert response.status_code == 204
        cookie = response.headers["set-cookie"].lower()
        assert cookie.startswith(SESSION_COOKIE + "=")
        assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
        assert f"max-age={SESSION_IDLE_SECONDS}" in cookie
        assert client.get(f"{API}/me").json() == {"actor": "user:admin", "auth_mode": "basic", "method": "session"}


def test_wrong_credentials(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        assert login(client).json()["code"] == "INVALID_CREDENTIALS"  # no admin yet
        create_admin(app)
        assert login(client, password="wrong password!").status_code == 401
        assert login(client, username="root").json()["code"] == "INVALID_CREDENTIALS"
        assert client.get(f"{API}/me").json()["code"] == "AUTH_REQUIRED"


def test_lockout_on_the_sixth_attempt_in_a_minute(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        for _ in range(5):
            assert login(client, password="wrong password!").status_code == 401
        locked = login(client)  # even the right password
        assert locked.status_code == 429 and locked.json()["code"] == "RATE_LIMITED"
        assert 0 < locked.json()["detail"]["retry_after_seconds"] <= 60
        assert login(client, ip="192.0.2.99").status_code == 204  # per IP


def test_limiter_window_slides() -> None:
    limiter = SlidingWindowLimiter()
    assert all(limiter.allow("ip", t) for t in (0, 1, 2, 3, 4))
    assert not limiter.allow("ip", 59.9)
    assert limiter.allow("ip", 60.0)  # the attempt at t=0 left the window
    limiter.prune(1000.0)
    assert limiter.retry_after("ip", 1000.0) == 0.0


def _shift_clock(monkeypatch: pytest.MonkeyPatch, seconds: int) -> None:
    real = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: real(self) + seconds)


def test_idle_expiry_slides_with_activity(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        assert login(client).status_code == 204
        _shift_clock(monkeypatch, 11 * 3600)
        assert client.get(f"{API}/me").status_code == 200  # active: the cookie is re-signed
        _shift_clock(monkeypatch, 11 * 3600)  # 22 h after login, 11 h idle
        assert client.get(f"{API}/me").status_code == 200
        _shift_clock(monkeypatch, SESSION_IDLE_SECONDS + 1)  # idle past 12 h
        assert client.get(f"{API}/me").json()["code"] == "AUTH_REQUIRED"


def test_logout(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        login(client)
        assert client.post(f"{API}/auth/logout").status_code == 204
        assert client.get(f"{API}/me").status_code == 401


def test_env_credential_wins_over_setup(tmp_path: Any) -> None:
    env_hash = PasswordHasher().hash("env password 123")
    with auth_client(tmp_path, auth_mode="basic", admin_user="ops", admin_password_hash=env_hash) as (client, app):
        with pytest.raises(ApiError) as exc:
            create_admin(app)
        assert exc.value.code == "ALREADY_SET"
        assert login(client, "ops", "env password 123").status_code == 204
        assert client.get(f"{API}/me").json()["actor"] == "user:ops"


def test_create_admin_rules(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (_, app):
        with pytest.raises(ApiError) as weak:
            create_admin(app, password="short")
        assert (weak.value.code, weak.value.status) == ("WEAK_PASSWORD", 422)
        create_admin(app)
        with app.state.db.connection() as conn:
            stored = basic_auth.credential(conn, app.state.settings)
        assert stored is not None and stored.source == "setup" and stored.username == ADMIN
        assert stored.password_hash.startswith("$argon2id$") and PASSWORD not in stored.password_hash
        with pytest.raises(ApiError) as again:
            create_admin(app)
        assert again.value.code == "ALREADY_SET"


def test_login_only_in_basic_mode(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="none") as (client, _):
        assert login(client).json()["code"] == "WRONG_AUTH_MODE"


def test_secret_key_is_private_and_survives_restarts(tmp_path: Any) -> None:
    with auth_client(tmp_path, auth_mode="basic") as (client, app):
        create_admin(app)
        login(client)
        cookie = client.cookies[SESSION_COOKIE]
    key = tmp_path / "secret.key"
    assert stat.S_IMODE(os.stat(key).st_mode) == 0o600
    with auth_client(tmp_path, auth_mode="basic") as (client, _):
        client.cookies.set(SESSION_COOKIE, cookie)
        assert client.get(f"{API}/me").status_code == 200

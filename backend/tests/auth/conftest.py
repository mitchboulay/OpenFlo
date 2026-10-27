from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import basic_auth
from conftest import _with_source_ip, mark_setup_ready

API = "/api/v1"
ADMIN = "admin"
PASSWORD = "correct horse battery"
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin"}


@contextmanager
def auth_client(tmp_path: Any, **overrides: Any) -> Iterator[tuple[TestClient, FastAPI]]:
    """An https TestClient (the session cookie is ``Secure``); requests may set ``x-test-source-ip``."""
    app = mark_setup_ready(create_app(Settings(db_path=str(tmp_path / "auth.db"), **overrides)))
    with TestClient(_with_source_ip(app), base_url="https://testserver") as client:
        yield client, app


def create_admin(app: FastAPI, username: str = ADMIN, password: str = PASSWORD) -> None:
    """What first-run setup (B2.2) does."""
    with app.state.db.connection() as conn:
        basic_auth.create_admin(conn, app.state.settings, username, password, "setup")


def login(client: TestClient, username: str = ADMIN, password: str = PASSWORD, ip: str = "192.0.2.10") -> Any:
    return client.post(f"{API}/auth/login", json={"username": username, "password": password},
                       headers={"x-test-source-ip": ip})

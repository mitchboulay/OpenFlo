"""``basic`` mode credentials (FR-15): one admin, argon2 hash from env or created by first-run setup (B2.2).

Only the argon2 hash is stored (``settings.admin_user`` / ``settings.admin_password_hash``). Passwords are
never logged.
"""
from __future__ import annotations

import hmac
import logging
import sqlite3
from dataclasses import dataclass
from functools import cache
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from ..config import Settings
from ..errors import ApiError
from ..repositories import settings as settings_repo

logger = logging.getLogger(__name__)

ADMIN_USER = "admin_user"
ADMIN_PASSWORD_HASH = "admin_password_hash"
MIN_PASSWORD_LENGTH = 12
MAX_USERNAME_LENGTH = 60

_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class Credential:
    username: str
    password_hash: str
    source: Literal["env", "setup"]


def actor_name(username: str) -> str:
    return f"user:{username}"


def credential(conn: sqlite3.Connection, settings: Settings) -> Credential | None:
    """The admin credential: env (``OPENFLO_ADMIN_USER`` + hash) wins over the one created in setup."""
    if settings.admin_user and settings.admin_password_hash:
        return Credential(settings.admin_user, settings.admin_password_hash, "env")
    username = settings_repo.get_value(conn, ADMIN_USER)
    password_hash = settings_repo.get_value(conn, ADMIN_PASSWORD_HASH)
    if isinstance(username, str) and isinstance(password_hash, str):
        return Credential(username, password_hash, "setup")
    return None


def create_admin(conn: sqlite3.Connection, settings: Settings, username: str, password: str, actor: str) -> str:
    """Create the admin for first-run setup (``POST /setup/admin``, B2.2); returns its actor name.

    Raises 409 ``ALREADY_SET`` when a credential exists, 422 ``WEAK_PASSWORD`` (< 12 characters) or
    ``INVALID_USERNAME``.
    """
    if credential(conn, settings) is not None:
        raise ApiError("ALREADY_SET", "an admin account already exists", 409)
    username = username.strip()
    if not 1 <= len(username) <= MAX_USERNAME_LENGTH:
        raise ApiError("INVALID_USERNAME", f"username must be 1 to {MAX_USERNAME_LENGTH} characters", 422)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ApiError("WEAK_PASSWORD", f"password must be at least {MIN_PASSWORD_LENGTH} characters", 422)
    settings_repo.put(conn, ADMIN_USER, username, actor)
    settings_repo.put(conn, ADMIN_PASSWORD_HASH, _hasher.hash(password), actor)
    logger.info("admin account %r created by %s", username, actor)
    return actor_name(username)


def verify_login(conn: sqlite3.Connection, settings: Settings, username: str, password: str) -> str | None:
    """The actor name for a correct username and password, else None. Timing does not reveal the username."""
    found = credential(conn, settings)
    password_hash = found.password_hash if found is not None else _dummy_hash()
    password_ok = _verify(password_hash, password)
    user_ok = found is not None and hmac.compare_digest(found.username.encode(), username.strip().encode())
    return actor_name(found.username) if found is not None and user_ok and password_ok else None


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False
    except InvalidHashError:
        logger.error("the stored admin password hash is not an argon2 hash; sign-in is impossible")
        return False


@cache
def _dummy_hash() -> str:
    """Verified against when no admin exists, so a missing account costs the same time as a wrong password."""
    return _hasher.hash("openflo-no-admin-account")

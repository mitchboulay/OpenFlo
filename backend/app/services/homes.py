"""Homes (FR-1): create, rename, retime and delete, with case-insensitive unique names."""
from __future__ import annotations

import logging
import sqlite3
import zoneinfo
from functools import lru_cache

from ..errors import ApiError
from ..repositories import devices, homes, profiles
from ..repositories.homes import Home, HomeUpdate
from . import scheduling

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


def check_timezone(name: str) -> str:
    if name not in _zones():
        raise ApiError("TIMEZONE_INVALID", f"{name!r} is not an IANA timezone", 422)
    return name


def require_home(conn: sqlite3.Connection, home_id: int) -> Home:
    home = homes.get(conn, home_id)
    if home is None:
        raise ApiError("HOME_NOT_FOUND", f"home {home_id} not found", 404)
    return home


def _check_name_free(conn: sqlite3.Connection, name: str, home_id: int | None = None) -> None:
    existing = homes.get_by_name(conn, name)
    if existing is not None and existing.id != home_id:
        raise ApiError("HOME_EXISTS", f"a home named {existing.name!r} already exists", 409)


def create_home(conn: sqlite3.Connection, name: str, timezone: str, actor: str) -> Home:
    name = name.strip()
    _check_name_free(conn, name)
    home = homes.create(conn, name, check_timezone(timezone), actor)
    logger.info("home created id=%s actor=%s", home.id, actor)
    return home


def update_home(conn: sqlite3.Connection, home_id: int, changes: HomeUpdate, actor: str) -> Home:
    """Rename and/or retime. A timezone change re-expands every schedule in the home (FR-1)."""
    current = require_home(conn, home_id)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        _check_name_free(conn, changes["name"], home_id)
    if "timezone" in changes:
        check_timezone(changes["timezone"])
    home = homes.update(conn, home_id, changes)
    assert home is not None
    if home.timezone != current.timezone:
        scheduling.expand_home(conn, home_id)
    logger.info("home updated id=%s fields=%s actor=%s", home_id, sorted(changes), actor)
    return home


def delete_home(conn: sqlite3.Connection, home_id: int, actor: str) -> None:
    """Blocked while non-retired devices remain; retired devices are detached and unused custom liquids go."""
    require_home(conn, home_id)
    if homes.non_retired_device_counts(conn, [home_id])[home_id]:
        raise ApiError("HOME_HAS_DEVICES", "move or retire this home's devices first", 409)
    if profiles.home_profiles_in_use(conn, home_id):
        raise ApiError("PROFILE_IN_USE", "a liquid of this home is still referenced by device history", 409)
    devices.detach_retired(conn, home_id)
    profiles.delete_for_home(conn, home_id)
    try:
        homes.delete(conn, home_id)
    except sqlite3.IntegrityError as exc:  # e.g. provisioning sessions recorded against the home
        raise ApiError("HOME_IN_USE", "the home is still referenced by provisioning history", 409) from exc
    logger.info("home deleted id=%s actor=%s", home_id, actor)

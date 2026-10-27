"""Liquid profiles (FR-7): read-only system liquids plus per-home custom ones on the standard flow curve."""
from __future__ import annotations

import logging
import re
import sqlite3

from ..errors import ApiError
from ..repositories import profiles
from ..repositories.profiles import LiquidProfile, ProfileUpdate
from .homes import require_home

logger = logging.getLogger(__name__)


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "liquid"


def _require_custom(conn: sqlite3.Connection, profile_id: int) -> LiquidProfile:
    profile = profiles.get(conn, profile_id)
    if profile is None:
        raise ApiError("PROFILE_NOT_FOUND", f"liquid profile {profile_id} not found", 404)
    if profile.system:
        raise ApiError("SYSTEM_PROFILE", "system liquids cannot be changed", 403)
    return profile


def list_profiles(
    conn: sqlite3.Connection, home_id: int | None, limit: int, before_id: int | None
) -> list[LiquidProfile]:
    if home_id is not None:
        require_home(conn, home_id)
    return profiles.list_visible(conn, home_id, limit=limit, before_id=before_id)


def create_profile(
    conn: sqlite3.Connection, home_id: int, name: str, *, capacity_ml: float, flow_full_ml_s: float,
    default_dose_ml: float, actor: str,
) -> LiquidProfile:
    """A custom liquid; its flow curve is the standard cartridge's until it is calibrated."""
    require_home(conn, home_id)
    standard = profiles.get_system(conn, profiles.STANDARD)
    if standard is None:
        raise RuntimeError("system profile 'standard' is missing (migration 002 not applied)")
    try:
        profile = profiles.create(
            conn, home_id, _slug(name), name.strip(), flow_full_ml_s=flow_full_ml_s, curve=standard.curve,
            capacity_ml=capacity_ml, default_dose_ml=default_dose_ml, actor=actor,
        )
    except sqlite3.IntegrityError as exc:
        raise ApiError("PROFILE_EXISTS", f"this home already has a liquid named like {name!r}", 409) from exc
    logger.info("liquid profile created id=%s home=%s actor=%s", profile.id, home_id, actor)
    return profile


def update_profile(conn: sqlite3.Connection, profile_id: int, changes: ProfileUpdate, actor: str) -> LiquidProfile:
    """Partial update; the slug keeps its original name so references stay stable."""
    _require_custom(conn, profile_id)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    profile = profiles.update(conn, profile_id, changes)
    assert profile is not None
    logger.info("liquid profile updated id=%s fields=%s actor=%s", profile_id, sorted(changes), actor)
    return profile


def delete_profile(conn: sqlite3.Connection, profile_id: int, actor: str) -> None:
    _require_custom(conn, profile_id)
    if profiles.in_use(conn, profile_id):
        raise ApiError("PROFILE_IN_USE", "a device or bottle uses this liquid", 409)
    profiles.delete(conn, profile_id)
    logger.info("liquid profile deleted id=%s actor=%s", profile_id, actor)

"""Liquid profiles: system profiles (home_id NULL) plus per-home custom ones."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import TypedDict

from ..persistence.repository import utcnow
from ._rows import DEFAULT_LIMIT, columns, fetch_one, fetch_page, update_columns

STANDARD = "standard"
VINEGAR = "vinegar"


@dataclass(frozen=True, slots=True)
class LiquidProfile:
    id: int
    home_id: int | None
    slug: str
    name: str
    flow_full_ml_s: float
    curve_json: str
    capacity_ml: float
    default_dose_ml: float
    calibrated: bool
    created_at: str
    actor: str

    @property
    def system(self) -> bool:
        return self.home_id is None

    @property
    def curve(self) -> list[tuple[float, float]]:
        """(remaining fraction, flow multiplier) points, descending remaining fraction."""
        return [(float(r), float(g)) for r, g in json.loads(self.curve_json)]


class ProfileUpdate(TypedDict, total=False):
    name: str
    flow_full_ml_s: float
    curve_json: str
    capacity_ml: float
    default_dose_ml: float
    calibrated: bool


_SELECT = f"SELECT {columns(LiquidProfile)} FROM liquid_profiles"
_UPDATABLE = frozenset(ProfileUpdate.__annotations__)


def get(conn: sqlite3.Connection, profile_id: int) -> LiquidProfile | None:
    return fetch_one(conn, LiquidProfile, f"{_SELECT} WHERE id = ?", (profile_id,))


def get_system(conn: sqlite3.Connection, slug: str) -> LiquidProfile | None:
    return fetch_one(conn, LiquidProfile, f"{_SELECT} WHERE home_id IS NULL AND slug = ?", (slug,))


def create(
    conn: sqlite3.Connection,
    home_id: int,
    slug: str,
    name: str,
    *,
    flow_full_ml_s: float,
    curve: list[tuple[float, float]],
    capacity_ml: float,
    default_dose_ml: float,
    actor: str,
    at: str | None = None,
) -> LiquidProfile:
    """Insert a home profile; raises ``sqlite3.IntegrityError`` when the slug exists in that home."""
    cur = conn.execute(
        "INSERT INTO liquid_profiles (home_id, slug, name, flow_full_ml_s, curve_json, capacity_ml,"
        " default_dose_ml, calibrated, created_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (home_id, slug, name, flow_full_ml_s, json.dumps([list(p) for p in curve]), capacity_ml,
         default_dose_ml, at or utcnow(), actor),
    )
    profile = get(conn, int(cur.lastrowid))
    assert profile is not None
    return profile


def list_visible(
    conn: sqlite3.Connection,
    home_id: int | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    before_id: int | None = None,
) -> list[LiquidProfile]:
    """System profiles plus, when ``home_id`` is given, that home's profiles."""
    if home_id is None:
        return fetch_page(conn, LiquidProfile, "liquid_profiles", "home_id IS NULL", (), limit=limit, before=before_id)
    return fetch_page(
        conn, LiquidProfile, "liquid_profiles", "(home_id IS NULL OR home_id = ?)", (home_id,),
        limit=limit, before=before_id,
    )


def update(conn: sqlite3.Connection, profile_id: int, changes: ProfileUpdate) -> LiquidProfile | None:
    update_columns(conn, "liquid_profiles", "id", profile_id, changes, _UPDATABLE)
    return get(conn, profile_id)


def delete(conn: sqlite3.Connection, profile_id: int) -> bool:
    return conn.execute("DELETE FROM liquid_profiles WHERE id = ?", (profile_id,)).rowcount == 1


def in_use(conn: sqlite3.Connection, profile_id: int) -> bool:
    """Whether a device's dosing or any bottle references the profile."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM device_dosing WHERE profile_id = ?)"
        " OR EXISTS (SELECT 1 FROM bottles WHERE profile_id = ?)",
        (profile_id, profile_id),
    ).fetchone()
    return bool(row[0])


def home_profiles_in_use(conn: sqlite3.Connection, home_id: int) -> bool:
    """Whether any of the home's own profiles is referenced by a device's dosing or a bottle."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM device_dosing WHERE profile_id IN"
        " (SELECT id FROM liquid_profiles WHERE home_id = ?))"
        " OR EXISTS (SELECT 1 FROM bottles WHERE profile_id IN (SELECT id FROM liquid_profiles WHERE home_id = ?))",
        (home_id, home_id),
    ).fetchone()
    return bool(row[0])


def delete_for_home(conn: sqlite3.Connection, home_id: int) -> int:
    return conn.execute("DELETE FROM liquid_profiles WHERE home_id = ?", (home_id,)).rowcount

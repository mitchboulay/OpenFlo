"""Dosing and bottle operations over the repositories (FR-7, FR-8, AD-5).

Every function takes an open connection, so the caller owns the transaction (``with db.connection() as conn``).
Errors carry the API ``code`` B1.4 maps to an HTTP status.
"""
from __future__ import annotations

import dataclasses
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, Literal

from ..repositories import bottles, devices, dispenses, profiles
from ..repositories import dosing as dosing_repo
from ..repositories.bottles import Bottle
from ..repositories.dosing import DeviceDosing, DoseServing
from ..repositories.profiles import LiquidProfile
from . import dosing as engine

logger = logging.getLogger(__name__)

CALIBRATION_WINDOW = timedelta(hours=24)
CAPPED_WHEN_LOW: Final = "CAPPED_WHEN_LOW"


class DosingError(Exception):
    code = "DOSING_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DoseOutOfRange(DosingError):
    code = "DOSE_OUT_OF_RANGE"

    def __init__(self, min_ml: float, max_ml: float):
        super().__init__(f"dose must be between {min_ml:.0f} and {max_ml:.0f} mL at a full bottle")
        self.min_ml = min_ml
        self.max_ml = max_ml


class NoRecentDispense(DosingError):
    code = "NO_RECENT_DISPENSE"


class CalibrationImplausible(DosingError):
    code = "CALIBRATION_IMPLAUSIBLE"


class NoOpenBottle(DosingError):
    code = "NO_OPEN_BOTTLE"


class ProfileNotFound(DosingError):
    code = "PROFILE_NOT_FOUND"


class FillOutOfRange(DosingError):
    code = "FILL_OUT_OF_RANGE"


@dataclass(frozen=True, slots=True)
class BottleView:
    id: int
    capacity_ml: float
    initial_fill_ml: float | None
    started_at: str
    est_remaining_ml: float | None
    est_doses_left: int | None
    est_days_left: float | None
    guidance: engine.GuidanceState


@dataclass(frozen=True, slots=True)
class DosingView:
    profile: LiquidProfile
    dose_ml: float | None
    fixed_seconds: float | None
    computed_seconds: float
    compensation_enabled: bool
    flow_scale: float
    capped_ml_when_low: float | None
    warning: Literal["CAPPED_WHEN_LOW"] | None
    bottle: BottleView | None
    # Whole-mL dose limits at a full bottle, the calibrated full-bottle flow and the Light/Standard/Strong presets.
    min_ml: int
    max_ml: int
    flow_ml_s: float
    calibrated: bool
    presets_ml: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class DoseState:
    """Everything the open time depends on, read in one transaction."""

    dosing: DeviceDosing
    profile: LiquidProfile
    bottle: Bottle | None
    remaining_ml: float | None
    flow_ml_s: float  # physical flow at the current fill level
    tenths: int


def ensure_dosing(conn: sqlite3.Connection, device_id: str) -> DeviceDosing:
    """The device's dosing row; a device registered after 002 starts on the standard profile's default dose."""
    current = dosing_repo.get(conn, device_id)
    if current is not None:
        return current
    standard = profiles.get_system(conn, profiles.STANDARD)
    if standard is None:
        raise RuntimeError("system profile 'standard' is missing (migration 002 not applied)")
    return dosing_repo.put(conn, device_id, standard.id, dose_ml=standard.default_dose_ml, fixed_tenths=None,
                           actor="system")


def _profile(conn: sqlite3.Connection, profile_id: int) -> LiquidProfile:
    profile = profiles.get(conn, profile_id)
    if profile is None:
        raise ProfileNotFound(f"liquid profile {profile_id} not found")
    return profile


def current_profile(conn: sqlite3.Connection, device_id: str) -> LiquidProfile:
    """The liquid the device is dosing."""
    return _profile(conn, ensure_dosing(conn, device_id).profile_id)


def _bottle_remaining(conn: sqlite3.Connection, bottle: Bottle | None) -> float | None:
    if bottle is None:
        return None
    return engine.remaining_ml(
        bottle.initial_fill_ml,
        [bottles.adjustment_total_ml(conn, bottle.id)],
        [dispenses.total_ml_for_bottle(conn, bottle.device_id, bottle.id)],
    )


def dose_state(conn: sqlite3.Connection, device_id: str) -> DoseState:
    """Open time for the next dose. Unknown fill counts as full (r = 1.0)."""
    dosing = ensure_dosing(conn, device_id)
    profile = _profile(conn, dosing.profile_id)
    bottle = bottles.open_for_device(conn, device_id)
    remaining = _bottle_remaining(conn, bottle)
    r = 1.0 if bottle is None or remaining is None else remaining / bottle.capacity_ml
    flow = engine.flow_at(profile.flow_full_ml_s, profile.curve, dosing.flow_scale, r)
    # Compensation off: time the dose for a full bottle; the physical flow still drives the volume estimate.
    timing_flow = flow if dosing.compensation_enabled else engine.flow_at(
        profile.flow_full_ml_s, profile.curve, dosing.flow_scale, 1.0)
    tenths = engine.open_tenths(dosing.dose_ml, dosing.fixed_tenths, timing_flow)
    return DoseState(dosing, profile, bottle, remaining, flow, tenths)


def serve_dose(conn: sqlite3.Connection, device_id: str) -> DoseServing:
    """Compute and record the open time a ``get-bottle`` 200 serves (AD-5)."""
    state = dose_state(conn, device_id)
    return dosing_repo.record_serving(conn, device_id, state.tenths, state.flow_ml_s)


def _bottle_view(state: DoseState, doses_per_day: float | None) -> BottleView | None:
    bottle = state.bottle
    if bottle is None:
        return None
    dose_ml = engine.est_volume(state.flow_ml_s, state.tenths, 1)
    advice = engine.guidance(state.remaining_ml, dose_ml, bottle.capacity_ml, doses_per_day)
    remaining = None if state.remaining_ml is None else max(0.0, state.remaining_ml)
    return BottleView(bottle.id, bottle.capacity_ml, bottle.initial_fill_ml, bottle.started_at, remaining,
                      advice.doses_left, advice.days_left, advice.state)


def get_dosing_view(conn: sqlite3.Connection, device_id: str) -> DosingView:
    """The ``Dosing`` schema plus the open ``Bottle``. ``days_left`` waits on schedules (B3.1)."""
    state = dose_state(conn, device_id)
    dosing = state.dosing
    capped = None
    if dosing.dose_ml is not None and dosing.compensation_enabled:
        capped = engine.capped_ml_when_low(dosing.dose_ml, state.profile, dosing.flow_scale)
    fixed_seconds = None if dosing.fixed_tenths is None else dosing.fixed_tenths / 10
    profile = state.profile
    limits = engine.dose_limits_ml(profile, dosing.flow_scale)
    full_flow = engine.flow_at(profile.flow_full_ml_s, profile.curve, dosing.flow_scale, 1.0)
    # A device calibration (scale != 1) counts as calibrated even for a liquid the system never measured.
    calibrated = profile.calibrated or dosing.flow_scale != 1.0
    return DosingView(profile, dosing.dose_ml, fixed_seconds, state.tenths / 10, dosing.compensation_enabled,
                      dosing.flow_scale, capped, None, _bottle_view(state, doses_per_day=None),
                      limits[0], limits[1], round(full_flow, 2), calibrated,
                      engine.dose_presets_ml(profile.default_dose_ml, limits))


def set_dosing(
    conn: sqlite3.Connection,
    device_id: str,
    profile_id: int,
    *,
    dose_ml: float | None = None,
    fixed_seconds: float | None = None,
    compensation_enabled: bool = True,
    actor: str,
) -> DosingView:
    """Set dose by volume or fixed seconds. Raises ``DoseOutOfRange``; warns ``CAPPED_WHEN_LOW``."""
    if (dose_ml is None) == (fixed_seconds is None):
        raise ValueError("exactly one of dose_ml and fixed_seconds is required")
    profile = _profile(conn, profile_id)
    device = devices.get(conn, device_id)
    if device is None or not (profile.system or profile.home_id == device.home_id):
        raise ProfileNotFound(f"liquid profile {profile_id} is not available to device {device_id}")
    current = ensure_dosing(conn, device_id)
    # A calibration belongs to the liquid it was measured with.
    flow_scale = current.flow_scale if current.profile_id == profile_id else 1.0
    fixed_tenths = None if fixed_seconds is None else round(fixed_seconds * 10)
    if fixed_tenths is not None and not engine.MIN_TENTHS <= fixed_tenths <= engine.MAX_TENTHS:
        raise ValueError("fixed_seconds must be between 1.0 and 30.0")
    if dose_ml is not None:
        min_ml, max_ml = engine.dose_range_ml(profile, flow_scale)
        if not min_ml <= dose_ml <= max_ml:
            raise DoseOutOfRange(min_ml, max_ml)
    dosing_repo.put(conn, device_id, profile_id, dose_ml=dose_ml, fixed_tenths=fixed_tenths,
                    compensation_enabled=compensation_enabled, flow_scale=flow_scale, actor=actor)
    logger.info("dosing set device=%s profile=%s actor=%s", device_id, profile_id, actor)
    view = get_dosing_view(conn, device_id)
    return dataclasses.replace(view, warning=CAPPED_WHEN_LOW) if view.capped_ml_when_low is not None else view


def calibrate(conn: sqlite3.Connection, device_id: str, measured_ml: float, actor: str) -> DosingView:
    """Compound the flow scale against the last confirmed dispense since the last dosing change (FR-7)."""
    current = ensure_dosing(conn, device_id)
    window_start = (datetime.now(timezone.utc) - CALIBRATION_WINDOW).isoformat()
    # Only a dispense served under the current scale may calibrate it, so one cup never compounds twice.
    last = dispenses.latest_estimated_since(conn, device_id, max(window_start, current.updated_at))
    if last is None or last.est_volume_ml is None:
        raise NoRecentDispense("no confirmed dispense in the last 24 hours since the dosing last changed")
    try:
        scale = engine.calibrated_flow_scale(current.flow_scale, measured_ml, last.est_volume_ml)
    except ValueError as exc:
        raise CalibrationImplausible(f"{measured_ml} mL against an estimated {last.est_volume_ml:.0f} mL") from exc
    dosing_repo.set_flow_scale(conn, device_id, scale, actor)
    logger.info("calibrated device=%s scale=%.4f actor=%s", device_id, scale, actor)
    return get_dosing_view(conn, device_id)


def _check_fill(fill_ml: float, capacity_ml: float) -> None:
    if not 0 <= fill_ml <= capacity_ml:
        raise FillOutOfRange(f"fill must be between 0 and {capacity_ml:.0f} mL")


def _view_of_open_bottle(conn: sqlite3.Connection, device_id: str) -> BottleView:
    view = _bottle_view(dose_state(conn, device_id), doses_per_day=None)
    assert view is not None
    return view


def install_bottle(
    conn: sqlite3.Connection, device_id: str, initial_fill_ml: float | None, *, reason: str, at: str | None = None
) -> Bottle:
    """Close the open bottle (if any) and open one on the device's current profile, in the caller's transaction."""
    profile = current_profile(conn, device_id)
    bottles.close_open(conn, device_id, reason, at)
    return bottles.open_bottle(conn, device_id, profile.id, profile.capacity_ml, initial_fill_ml, at)


def new_bottle(
    conn: sqlite3.Connection, device_id: str, fill: Literal["full", "set"], fill_ml: float | None, actor: str
) -> BottleView:
    """Operator bottle change: ``full`` = the profile's capacity; ``set`` = ``fill_ml`` or unknown when None."""
    profile = current_profile(conn, device_id)
    initial = profile.capacity_ml if fill == "full" else fill_ml
    if initial is not None:
        _check_fill(initial, profile.capacity_ml)
    install_bottle(conn, device_id, initial, reason="replaced")
    logger.info("new bottle device=%s fill=%s actor=%s", device_id, initial, actor)
    return _view_of_open_bottle(conn, device_id)


def adjust_fill(conn: sqlite3.Connection, device_id: str, fill_ml: float, actor: str) -> BottleView:
    """Record the fill-level delta that makes the open bottle's remaining equal ``fill_ml``."""
    bottle = bottles.open_for_device(conn, device_id)
    if bottle is None:
        raise NoOpenBottle(f"device {device_id} has no open bottle")
    _check_fill(fill_ml, bottle.capacity_ml)
    if bottle.initial_fill_ml is None:
        bottle = bottles.set_initial_fill(conn, bottle.id, 0.0) or bottle
    current = _bottle_remaining(conn, bottle)
    assert current is not None
    bottles.add_adjustment(conn, bottle.id, fill_ml - current, "manual", actor)
    return _view_of_open_bottle(conn, device_id)

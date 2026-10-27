"""Dosing engine (AD-5): pure functions, no database and no I/O.

The valve's gravity flow falls as the bottle empties, so the open time for a dose is recomputed from the
remaining fraction ``r`` at every ``get-bottle``: ``flow = F0 x flow_scale x g(r)`` and
``tenths = clamp(round(10 x dose_ml / flow), 10, 300)`` (firmware 100 ms loop, Critical Constraint 5).

The valve's wake-time pulse only drives it closed (research R-1, ``research/valve-homing-on-wake.md``), so a
wake releases no liquid and ``remaining_ml`` has no per-wake term.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

MIN_TENTHS = 10  # 1.0 s
MAX_TENTHS = 300  # 30.0 s
# Lowest remaining fraction the CAPPED_WHEN_LOW check covers (the vendor table's last slot).
LOW_REMAINING_FRACTION = 0.17
MIN_FLOW_SCALE = 0.2
MAX_FLOW_SCALE = 5.0
REFILL_SOON_DOSES = 2
REFILL_SOON_FRACTION = 0.15

Curve = Sequence[tuple[float, float]]
GuidanceState = Literal["ok", "refill_soon", "refill_now", "unknown"]


class FlowProfile(Protocol):
    """The liquid-profile fields the engine reads (``repositories.profiles.LiquidProfile`` satisfies it)."""

    @property
    def flow_full_ml_s(self) -> float: ...

    @property
    def curve(self) -> list[tuple[float, float]]: ...


@dataclass(frozen=True, slots=True)
class Guidance:
    state: GuidanceState
    doses_left: int | None
    days_left: float | None


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def curve_factor(curve: Curve, remaining_fraction: float) -> float:
    """Piecewise-linear ``g(r)`` through the curve points, with ``r`` clamped to [0, 1]."""
    if not curve:
        raise ValueError("flow curve has no points")
    points = sorted(curve)
    r = _clamp(remaining_fraction, 0.0, 1.0)
    if r <= points[0][0]:
        return points[0][1]
    for (r0, g0), (r1, g1) in zip(points, points[1:]):
        if r <= r1:
            return g0 + (g1 - g0) * (r - r0) / (r1 - r0)
    return points[-1][1]


def flow_at(profile_flow_full: float, curve: Curve, flow_scale: float, remaining_fraction: float) -> float:
    """Flow in mL/s at remaining fraction ``r``."""
    return profile_flow_full * flow_scale * curve_factor(curve, remaining_fraction)


def open_tenths(dose_ml: float | None, fixed_tenths: int | None, flow: float) -> int:
    """Valve open time in tenths of a second, clamped to 10..300 (never 0). Fixed mode bypasses the flow."""
    if fixed_tenths is not None:
        return int(_clamp(fixed_tenths, MIN_TENTHS, MAX_TENTHS))
    if dose_ml is None:
        raise ValueError("exactly one of dose_ml and fixed_tenths is required")
    return int(_clamp(round(10 * dose_ml / flow), MIN_TENTHS, MAX_TENTHS))


def _lowest_flow(profile: FlowProfile, flow_scale: float) -> float:
    """Minimum flow over r in [LOW_REMAINING_FRACTION, 1]; piecewise-linear, so it sits at an end or a point."""
    candidates = [LOW_REMAINING_FRACTION, 1.0] + [r for r, _ in profile.curve if LOW_REMAINING_FRACTION <= r <= 1.0]
    return min(flow_at(profile.flow_full_ml_s, profile.curve, flow_scale, r) for r in candidates)


def capped_ml_when_low(dose_ml: float, profile: FlowProfile, flow_scale: float) -> float | None:
    """mL deliverable at the 30 s cap when the dose needs longer anywhere in r in [0.17, 1]; else None.

    For a monotone curve (both system profiles) the slowest point is r = 0.17.
    """
    low_flow = _lowest_flow(profile, flow_scale)
    capped = low_flow * MAX_TENTHS / 10
    return capped if dose_ml > capped else None


def dose_range_ml(profile: FlowProfile, flow_scale: float) -> tuple[float, float]:
    """(min_ml, max_ml) deliverable at a full bottle within the 1.0-30.0 s limits."""
    flow = flow_at(profile.flow_full_ml_s, profile.curve, flow_scale, 1.0)
    return flow * MIN_TENTHS / 10, flow * MAX_TENTHS / 10


# Light · Standard · Strong dose presets as multiples of the liquid's default dose (critique-v2 #9).
PRESET_FACTORS = (2 / 3, 1.0, 4 / 3)


def dose_limits_ml(profile: FlowProfile, flow_scale: float) -> tuple[int, int]:
    """``dose_range_ml`` rounded inward to whole mL, so every value in it is accepted."""
    low, high = dose_range_ml(profile, flow_scale)
    return math.ceil(low - 1e-9), math.floor(high + 1e-9)


def dose_presets_ml(default_dose_ml: float, limits: tuple[int, int]) -> tuple[int, int, int]:
    """Light, Standard and Strong doses in whole mL, kept inside ``limits``."""
    low, high = limits
    light, standard, strong = (int(_clamp(round(default_dose_ml * f), low, high)) for f in PRESET_FACTORS)
    return light, standard, strong


def est_volume(flow_ml_s: float, tenths: int, dose_count: int) -> float:
    """Estimated mL delivered by a confirmed dispense of ``dose_count`` doses."""
    return flow_ml_s * tenths / 10 * dose_count


def remaining_ml(
    initial_fill_ml: float | None, adjustments_ml: Iterable[float], dispensed_ml: Iterable[float]
) -> float | None:
    """``initial_fill + sum(adjustments) - sum(dispensed)``; None while the initial fill is unknown."""
    if initial_fill_ml is None:
        return None
    return initial_fill_ml + math.fsum(adjustments_ml) - math.fsum(dispensed_ml)


def guidance(
    remaining: float | None, dose_ml: float, capacity_ml: float, doses_per_day: float | None
) -> Guidance:
    """Refill guidance (FR-8). Advisory only: it never blocks dispensing."""
    if remaining is None:
        return Guidance("unknown", None, None)
    if dose_ml <= 0:
        raise ValueError("dose_ml must be positive")
    doses_left = max(0, math.floor(remaining / dose_ml))
    days_left = doses_left / doses_per_day if doses_per_day else None
    if remaining < dose_ml:
        state: GuidanceState = "refill_now"
    elif doses_left <= REFILL_SOON_DOSES or remaining < REFILL_SOON_FRACTION * capacity_ml:
        state = "refill_soon"
    else:
        state = "ok"
    return Guidance(state, doses_left, days_left)


def calibrated_flow_scale(old_scale: float, measured_ml: float, est_volume_ml: float) -> float:
    """Compounding calibration (FR-7): ``old x measured / est``, plausible only within 0.2-5.0."""
    if measured_ml <= 0 or est_volume_ml <= 0:
        raise ValueError("CALIBRATION_IMPLAUSIBLE")
    scale = old_scale * measured_ml / est_volume_ml
    if not MIN_FLOW_SCALE <= scale <= MAX_FLOW_SCALE:
        raise ValueError("CALIBRATION_IMPLAUSIBLE")
    return scale

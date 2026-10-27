"""Dosing engine (AD-5): pure functions, checked against the vendor table and the first measured dose."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import dosing

STANDARD_CURVE = [(1.0, 1.00), (0.83, 0.93), (0.67, 0.89), (0.50, 0.81), (0.33, 0.66), (0.17, 0.25), (0.0, 0.25)]
F0 = 27.2


@dataclass(frozen=True)
class Profile:
    flow_full_ml_s: float
    curve: list[tuple[float, float]]


STANDARD = Profile(F0, STANDARD_CURVE)


@pytest.mark.parametrize(
    ("r", "vendor_tenths"), [(1.0, 65), (0.83, 70), (0.67, 73), (0.5, 80), (0.33, 98), (0.17, 260)]
)
def test_177_ml_reproduces_vendor_table(r: float, vendor_tenths: int) -> None:
    flow = dosing.flow_at(F0, STANDARD_CURVE, 1.0, r)
    assert abs(dosing.open_tenths(177, None, flow) - vendor_tenths) <= 3


def test_curve_interpolates_and_clamps_r() -> None:
    assert dosing.curve_factor(STANDARD_CURVE, 0.915) == pytest.approx(0.965)
    assert dosing.curve_factor(STANDARD_CURVE, 1.7) == 1.0
    assert dosing.curve_factor(STANDARD_CURVE, -0.2) == 0.25
    assert dosing.flow_at(F0, STANDARD_CURVE, 2.0, 1.0) == pytest.approx(54.4)
    with pytest.raises(ValueError):
        dosing.curve_factor([], 0.5)


def test_open_time_clamps_and_fixed_mode() -> None:
    assert dosing.open_tenths(1, None, 27.2) == 10  # never 0
    assert dosing.open_tenths(5000, None, 27.2) == 300
    assert dosing.open_tenths(None, 42, 1.0) == 42  # fixed bypasses flow
    assert dosing.open_tenths(500, 42, 1.0) == 42
    with pytest.raises(ValueError):
        dosing.open_tenths(None, None, 27.2)


def test_calibration_from_first_measured_dose_and_compounding() -> None:
    est = dosing.est_volume(dosing.flow_at(F0, STANDARD_CURVE, 1.0, 1.0), 65, 1)
    scale = dosing.calibrated_flow_scale(1.0, 181, est)
    assert scale == pytest.approx(1.02, abs=0.005)
    # Next dose served at the new scale; measuring 190 mL compounds on top.
    est2 = dosing.est_volume(dosing.flow_at(F0, STANDARD_CURVE, scale, 1.0), 65, 1)
    scale2 = dosing.calibrated_flow_scale(scale, 190, est2)
    assert scale2 == pytest.approx(scale * 190 / est2)
    assert scale2 == pytest.approx(190 / (F0 * 6.5))


@pytest.mark.parametrize(("old", "measured", "est"), [(1.0, 10, 100), (1.0, 600, 100), (1.0, 0, 100), (1.0, 50, 0)])
def test_calibration_implausible(old: float, measured: float, est: float) -> None:
    with pytest.raises(ValueError, match="CALIBRATION_IMPLAUSIBLE"):
        dosing.calibrated_flow_scale(old, measured, est)


def test_capped_ml_when_low() -> None:
    assert dosing.capped_ml_when_low(177, STANDARD, 1.0) is None  # 26 s at r = 0.17
    assert dosing.capped_ml_when_low(250, STANDARD, 1.0) == pytest.approx(F0 * 0.25 * 30)
    assert dosing.capped_ml_when_low(250, STANDARD, 2.0) is None


def test_dose_range_at_full_bottle() -> None:
    assert dosing.dose_range_ml(STANDARD, 1.0) == pytest.approx((27.2, 816.0))
    assert dosing.dose_range_ml(STANDARD, 0.5) == pytest.approx((13.6, 408.0))


def test_double_dose_volume() -> None:
    assert dosing.est_volume(27.2, 65, 2) == pytest.approx(2 * dosing.est_volume(27.2, 65, 1)) == pytest.approx(353.6)


def test_remaining() -> None:
    assert dosing.remaining_ml(None, [10], [5]) is None
    assert dosing.remaining_ml(1065, [-100, 25], [177, 177.5]) == pytest.approx(635.5)
    assert dosing.remaining_ml(1065, [], []) == 1065


@pytest.mark.parametrize(
    ("remaining", "state", "doses_left"),
    [
        (None, "unknown", None),
        (1065, "ok", 6),
        (531, "refill_soon", 3),  # 3 doses but < 15 % of 4000 below
        (530, "refill_soon", 2),  # <= 2 doses
        (176, "refill_now", 0),  # < 1 dose
        (-20, "refill_now", 0),
    ],
)
def test_guidance_states(remaining: float | None, state: str, doses_left: int | None) -> None:
    capacity = 4000 if remaining == 531 else 1065
    advice = dosing.guidance(remaining, 177, capacity, None)
    assert (advice.state, advice.doses_left, advice.days_left) == (state, doses_left, None)


def test_guidance_days_left_uses_schedule_rate() -> None:
    assert dosing.guidance(1065, 177, 1065, 2).days_left == 3.0
    assert dosing.guidance(531, 177, 1065, 0.5).state == "ok"  # 3 doses, 50 %


def test_dose_limits_round_inward_and_presets_stay_inside() -> None:
    assert dosing.dose_limits_ml(STANDARD, 1.0) == (28, 816)
    assert dosing.dose_presets_ml(177, (28, 816)) == (118, 177, 236)
    assert dosing.dose_presets_ml(30, (28, 816)) == (28, 30, 40)
    assert dosing.dose_presets_ml(800, (28, 816)) == (533, 800, 816)

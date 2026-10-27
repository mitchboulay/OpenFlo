from __future__ import annotations

import pytest

from conftest import DEVICE_ID

from .conftest import Api

DOSING = f"/devices/{DEVICE_ID}/dosing"
STANDARD = 1
VINEGAR = 2


def _confirmed_dispense(api: Api) -> None:
    """Serve the current open time, then report the dispense (a calibration needs one, FR-7)."""
    api.unlock()
    assert api.device_post("get-bottle").status_code == 200
    api.device_post("send-events", {"data": [{"status": 0, "code": 1, "timestamp": 1_900_000_000}]})


def test_get_dosing(api: Api) -> None:
    body = api.get(DOSING).json()
    assert body["profile"]["slug"] == "standard" and body["profile"]["system"] is True
    assert body["dose_ml"] == 177 and body["fixed_seconds"] is None
    assert body["computed_seconds"] == 6.5 and body["warning"] is None


def test_set_dose_by_volume_and_fixed_seconds(api: Api) -> None:
    by_volume = api.put(DOSING, {"profile_id": STANDARD, "dose_ml": 136})
    assert by_volume.status_code == 200 and by_volume.json()["computed_seconds"] == 5.0
    fixed = api.put(DOSING, {"profile_id": STANDARD, "fixed_seconds": 12.34, "compensation_enabled": False}).json()
    assert (fixed["fixed_seconds"], fixed["computed_seconds"], fixed["dose_ml"]) == (12.3, 12.3, None)
    assert fixed["compensation_enabled"] is False
    # compensation_enabled omitted keeps the stored value.
    assert api.put(DOSING, {"profile_id": VINEGAR, "dose_ml": 100}).json()["compensation_enabled"] is False


@pytest.mark.parametrize("body", [
    {"profile_id": STANDARD},
    {"profile_id": STANDARD, "dose_ml": 100, "fixed_seconds": 5},
    {"profile_id": STANDARD, "fixed_seconds": 0.5},
    {"profile_id": STANDARD, "dose_ml": 100, "extra": 1},
])
def test_invalid_dosing_requests(api: Api, body: dict[str, object]) -> None:
    response = api.put(DOSING, body)
    assert response.status_code == 422 and response.json()["code"] == "INVALID_REQUEST"


def test_dose_out_of_range_reports_the_range(api: Api) -> None:
    response = api.put(DOSING, {"profile_id": STANDARD, "dose_ml": 5000})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "DOSE_OUT_OF_RANGE"
    assert body["detail"]["min_ml"] == pytest.approx(27.2) and body["detail"]["max_ml"] == pytest.approx(816)


def test_capped_when_low_saves_with_a_warning(api: Api) -> None:
    body = api.put(DOSING, {"profile_id": STANDARD, "dose_ml": 400}).json()
    assert body["dose_ml"] == 400 and body["warning"] == "CAPPED_WHEN_LOW"
    assert body["capped_ml_when_low"] == pytest.approx(27.2 * 0.25 * 30)


def test_unknown_profile(api: Api) -> None:
    response = api.put(DOSING, {"profile_id": 999, "dose_ml": 100})
    assert response.status_code == 404 and response.json()["code"] == "PROFILE_NOT_FOUND"


def test_calibration(api: Api) -> None:
    none_yet = api.post(f"{DOSING}/calibration", {"measured_ml": 180})
    assert none_yet.status_code == 409 and none_yet.json()["code"] == "NO_RECENT_DISPENSE"
    _confirmed_dispense(api)
    implausible = api.post(f"{DOSING}/calibration", {"measured_ml": 5000})
    assert implausible.status_code == 422 and implausible.json()["code"] == "CALIBRATION_IMPLAUSIBLE"
    calibrated = api.post(f"{DOSING}/calibration", {"measured_ml": 181}).json()
    assert calibrated["flow_scale"] == pytest.approx(181 / (27.2 * 6.5), rel=1e-6)
    assert api.post(f"{DOSING}/calibration", {"measured_ml": 0}).status_code == 422


def test_profiles_crud(api: Api) -> None:
    created = api.post(f"/homes/{api.home_id}/liquid-profiles", {
        "name": "Bleach 5%", "capacity_ml": 500, "flow_full_ml_s": 20, "default_dose_ml": 50,
    })
    assert created.status_code == 201
    custom = created.json()
    assert (custom["slug"], custom["system"], custom["calibrated"]) == ("bleach-5", False, False)
    duplicate = api.post(f"/homes/{api.home_id}/liquid-profiles", {
        "name": "bleach 5", "capacity_ml": 1, "flow_full_ml_s": 1, "default_dose_ml": 1,
    })
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "PROFILE_EXISTS"

    assert [p["slug"] for p in api.get("/liquid-profiles").json()] == ["vinegar", "standard"]
    in_home = api.get("/liquid-profiles", params={"home_id": api.home_id}).json()
    assert [p["slug"] for p in in_home] == ["bleach-5", "vinegar", "standard"]
    assert api.get("/liquid-profiles", params={"home_id": 999}).status_code == 404

    assert api.patch(f"/liquid-profiles/{custom['id']}", {"name": "Bleach"}).json()["name"] == "Bleach"
    system = api.patch(f"/liquid-profiles/{STANDARD}", {"name": "Mine"})
    assert system.status_code == 403 and system.json()["code"] == "SYSTEM_PROFILE"
    assert api.delete(f"/liquid-profiles/{STANDARD}").status_code == 403

    api.put(DOSING, {"profile_id": custom["id"], "dose_ml": 40})
    in_use = api.delete(f"/liquid-profiles/{custom['id']}")
    assert in_use.status_code == 409 and in_use.json()["code"] == "PROFILE_IN_USE"
    api.put(DOSING, {"profile_id": STANDARD, "dose_ml": 177})
    assert api.delete(f"/liquid-profiles/{custom['id']}").status_code == 204


def test_dosing_reports_limits_flow_and_presets(api: Api) -> None:
    body = api.get(DOSING).json()
    assert (body["min_ml"], body["max_ml"]) == (28, 816)
    assert body["flow_ml_s"] == pytest.approx(27.2) and body["calibrated"] is True
    assert body["presets"] == {"light_ml": 118, "standard_ml": 177, "strong_ml": 236}
    vinegar = api.put(DOSING, {"profile_id": VINEGAR, "dose_ml": 120}).json()
    assert vinegar["calibrated"] is False and vinegar["presets"]["standard_ml"] == 120

from __future__ import annotations

import pytest

from conftest import DEVICE_ID, update_payload

from .conftest import Api

URL = f"/devices/{DEVICE_ID}/controls"


@pytest.mark.parametrize(
    ("preset", "shift", "interval"),
    [("battery_saver", 900, 86_400), ("balanced", 900, 21_600), ("responsive", 600, 3_600), ("testing", 300, 900)],
)
def test_presets_map_per_ad7_and_reach_the_device_shift_first(api: Api, preset: str, shift: int, interval: int) -> None:
    body = api.patch(URL, {"wake_preset": preset}).json()
    assert (body["wake_preset"], body["shift_time_seconds"], body["sync_interval_seconds"]) == (preset, shift, interval)
    config = api.device_post("update-device", update_payload()).json()["data"]["config"]
    assert list(config.items()) == [("shift-time", shift), ("fast-sync-time", interval)]


def test_raw_seconds_are_custom(api: Api) -> None:
    api.patch(URL, {"wake_preset": "balanced"})
    body = api.patch(URL, {"sync_interval_seconds": 7200}).json()
    assert body["wake_preset"] is None  # Custom
    assert (body["shift_time_seconds"], body["sync_interval_seconds"]) == (900, 7200)


def test_interval_must_exceed_twice_the_shift_time(api: Api) -> None:
    too_short = api.patch(URL, {"shift_time_seconds": 600, "sync_interval_seconds": 1200})
    assert too_short.status_code == 422
    assert too_short.json()["code"] == "INTERVAL_TOO_SHORT"
    assert too_short.json()["detail"] == {"min_sync_interval_seconds": 1201, "shift_time_seconds": 600}
    assert api.patch(URL, {"shift_time_seconds": 600, "sync_interval_seconds": 1201}).status_code == 200
    # Raising the shift alone is checked against the stored interval.
    assert api.patch(URL, {"shift_time_seconds": 700}).json()["code"] == "INTERVAL_TOO_SHORT"


def test_interval_needs_an_explicit_shift_time(api: Api) -> None:
    response = api.patch(URL, {"sync_interval_seconds": 3900})
    assert response.status_code == 422 and response.json()["code"] == "INTERVAL_TOO_SHORT"


def test_preset_and_raw_seconds_together_are_rejected(api: Api) -> None:
    response = api.patch(URL, {"wake_preset": "testing", "shift_time_seconds": 60})
    assert response.status_code == 422 and response.json()["code"] == "INVALID_REQUEST"


def test_bounds_and_unknown_fields(api: Api) -> None:
    assert api.patch(URL, {"sync_interval_seconds": 600}).status_code == 422
    assert api.patch(URL, {"sync_interval_seconds": 999_999}).status_code == 422
    assert api.patch(URL, {"wake_preset": "turbo"}).status_code == 422
    assert api.patch(URL, {"dispensing_enabled": None}).status_code == 422
    assert api.patch(URL, {"remoteDispense": True}).status_code == 422
    assert api.patch("/devices/NOPE/controls", {}).status_code == 404


def test_lock_drives_the_bottle_interlock_and_cancels_a_queued_dispense(api: Api) -> None:
    assert api.device_post("get-bottle").status_code == 422
    api.unlock()
    assert api.device_post("get-bottle").status_code == 200
    api.post(f"/devices/{DEVICE_ID}/dispense")
    body = api.patch(URL, {"dispensing_enabled": False, "schedules_enabled": True}).json()
    assert body["dispensing_enabled"] is False and body["schedules_enabled"] is True
    assert api.device_post("get-bottle").json()["code"] == "BOTTLE_INSTALLED_NOT_AUTHORIZED"
    api.unlock()
    assert "remoteDispense" not in api.device_post("update-device", update_payload()).json()["data"]

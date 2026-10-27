from __future__ import annotations

import pytest

from conftest import DEVICE_ID

from .conftest import Api

BOTTLES = f"/devices/{DEVICE_ID}/bottles"


def test_new_full_bottle(api: Api) -> None:
    response = api.post(BOTTLES, {"fill": "full"})
    assert response.status_code == 201
    body = response.json()
    assert body["capacity_ml"] == 1065 and body["initial_fill_ml"] == 1065
    assert body["est_remaining_ml"] == 1065 and body["est_doses_left"] == 6 and body["guidance"] == "ok"
    assert body["est_days_left"] is None  # needs schedules (B3.1)
    assert api.get(f"/devices/{DEVICE_ID}").json()["bottle"]["id"] == body["id"]


def test_unknown_level_then_set_it(api: Api) -> None:
    unknown = api.post(BOTTLES, {"fill": "set"}).json()
    assert unknown["initial_fill_ml"] is None and unknown["guidance"] == "unknown"
    adjusted = api.post(f"{BOTTLES}/current/adjust", {"fill_ml": 300}).json()
    assert adjusted["id"] == unknown["id"]
    assert adjusted["est_remaining_ml"] == pytest.approx(300) and adjusted["guidance"] == "refill_soon"


def test_new_bottle_replaces_the_open_one(api: Api) -> None:
    first = api.post(BOTTLES, {"fill": "set", "fill_ml": 500}).json()
    second = api.post(BOTTLES, {"fill": "full"}).json()
    assert second["id"] != first["id"]
    assert api.get(f"/devices/{DEVICE_ID}").json()["bottle"]["id"] == second["id"]


def test_adjust_without_an_open_bottle(api: Api) -> None:
    response = api.post(f"{BOTTLES}/current/adjust", {"fill_ml": 100})
    assert response.status_code == 409 and response.json()["code"] == "NO_OPEN_BOTTLE"


def test_fill_out_of_range(api: Api) -> None:
    response = api.post(BOTTLES, {"fill": "set", "fill_ml": 2000})
    assert response.status_code == 422 and response.json()["code"] == "FILL_OUT_OF_RANGE"
    assert api.post(BOTTLES, {"fill": "set", "fill_ml": -1}).status_code == 422
    assert api.post(BOTTLES, {"fill": "half"}).status_code == 422
    assert api.post("/devices/NOPE/bottles", {"fill": "full"}).status_code == 404

"""Sync derivation (AD-3, FR-14) against the shape of the 2026-10-26 lab traffic, on a frozen clock."""
from __future__ import annotations

from datetime import datetime, timezone

from app.repositories import syncs
from conftest import DEVICE_ID, seed_device, update_payload

LAB_IP = "192.168.30.80"
# Bottle wake: 14 requests over ~95 s (update-device, get-bottle, then event batches). Offsets in seconds.
BOTTLE_WAKE = [
    (0, "update-device"), (3, "get-bottle"), (9, "send-events"), (16, "update-device"), (22, "send-events"),
    (30, "get-bottle"), (38, "send-events"), (47, "update-device"), (55, "send-events"), (63, "get-bottle"),
    (71, "send-events"), (79, "update-device"), (87, "send-events"), (95, "update-device"),
]
# Timer wake: update-device, then one event batch 26 s later.
TIMER_WAKE = [(0, "update-device"), (26, "send-events")]


def _replay(client, clock, wake: list[tuple[int, str]], ip: str = LAB_IP) -> None:
    start = clock.now
    for offset, endpoint in wake:
        clock.now = start + offset
        body = update_payload() if endpoint == "update-device" else {"data": []}
        response = client.post(
            f"/device-api/v2/{endpoint}", json=body, headers={"x-device-id": DEVICE_ID, "x-test-source-ip": ip}
        )
        assert response.status_code in (200, 422), response.text  # get-bottle is the lock while dispensing is off


def _syncs(app) -> list[syncs.DeviceSync]:
    with app.state.db.connection() as conn:
        return list(reversed(syncs.list_recent(conn, DEVICE_ID)))


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds")


def test_lab_wakes_become_one_sync_each(gated):
    client, app, clock = gated
    seed_device(app)
    t0 = clock.now
    _replay(client, clock, TIMER_WAKE)
    clock.now = t0 + 26 + 1800  # 30 min check-in interval
    t1 = clock.now
    _replay(client, clock, BOTTLE_WAKE)
    clock.now = t1 + 95 + 121  # just past the 120 s gap
    t2 = clock.now
    _replay(client, clock, TIMER_WAKE)

    rows = _syncs(app)
    assert [(r.started_at, r.ended_at, r.request_count, r.source_ip) for r in rows] == [
        (_iso(t0), _iso(t0 + 26), 2, LAB_IP),
        (_iso(t1), _iso(t1 + 95), 14, LAB_IP),
        (_iso(t2), _iso(t2 + 26), 2, LAB_IP),
    ]


def test_gap_of_exactly_120_seconds_extends_the_sync(gated):
    client, app, clock = gated
    seed_device(app)
    _replay(client, clock, [(0, "update-device"), (120, "update-device"), (240, "update-device")])
    clock.advance(121)
    _replay(client, clock, [(0, "update-device")])
    assert [r.request_count for r in _syncs(app)] == [3, 1]


def test_last_seen_and_last_ip_follow_requests(gated):
    client, app, clock = gated
    seed_device(app)
    _replay(client, clock, TIMER_WAKE)
    with app.state.db.connection() as conn:
        row = conn.execute("SELECT last_seen, last_ip FROM devices WHERE device_id = ?", (DEVICE_ID,)).fetchone()
    assert tuple(row) == (_iso(clock.now), LAB_IP)


def test_second_ip_in_the_same_microsecond_joins_the_open_sync(gated):
    # Regression: UNIQUE(device_id, started_at) must not turn a simultaneous second IP into a 500.
    client, app, clock = gated
    seed_device(app)
    _replay(client, clock, [(0, "update-device")])
    _replay(client, clock, [(0, "update-device")], ip="203.0.113.9")
    rows = _syncs(app)
    assert [(r.request_count, r.source_ip) for r in rows] == [(2, LAB_IP)]
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT kind FROM device_identity_flags").fetchall()[0][0] == "ip_conflict"


def test_unknown_ids_without_a_row_record_no_sync(gated):
    client, app, _ = gated
    response = client.post("/device-api/v2/healthcheck", json={"deviceId": DEVICE_ID})
    assert response.status_code == 422
    with app.state.db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM device_syncs").fetchone()[0] == 0

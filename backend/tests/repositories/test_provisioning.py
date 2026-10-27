from __future__ import annotations

import sqlite3

import pytest

from app.repositories import provisioning
from tests.repositories.conftest import assert_limit_bounds

LATER = "2999-01-01T00:00:00+00:00"
EARLIER = "2000-01-01T00:00:00+00:00"


def _session(conn: sqlite3.Connection, home_id: int, ott: str, **kwargs: str) -> provisioning.ProvisioningSession:
    return provisioning.create(conn, home_id, "new", "Kitchen", ott, actor="alice",
                               expires_at=kwargs.pop("expires_at", LATER), **kwargs)  # type: ignore[arg-type]


def test_session_create_lookup_update(conn: sqlite3.Connection, home_id: int) -> None:
    session = _session(conn, home_id, "a" * 64)
    assert session.status == "awaiting_softap"
    assert provisioning.get_by_ott(conn, "a" * 64) == session
    assert provisioning.open_for_home(conn, home_id) == session
    assert provisioning.any_awaiting_join(conn) is False
    joined = provisioning.update(conn, session.id, {"status": "awaiting_join"})
    assert joined is not None and joined.status == "awaiting_join"
    assert provisioning.any_awaiting_join(conn) is True
    done = provisioning.update(conn, session.id, {"status": "completed", "bound_device_id": "D1",
                                                  "bound_ip": "10.0.0.5", "completed_at": "t9"})
    assert done is not None and (done.bound_device_id, done.completed_at) == ("D1", "t9")
    assert provisioning.open_for_home(conn, home_id) is None
    with pytest.raises(sqlite3.IntegrityError):
        _session(conn, home_id, "a" * 64)
    with pytest.raises(ValueError):
        provisioning.update(conn, session.id, {"ott_sha256": "x"})  # type: ignore[typeddict-unknown-key]


def test_expire_due(conn: sqlite3.Connection, home_id: int) -> None:
    stale = _session(conn, home_id, "b" * 64, expires_at=EARLIER)
    fresh = _session(conn, home_id, "c" * 64)
    assert provisioning.open_for_home(conn, home_id) == fresh
    assert provisioning.expire_due(conn) == [stale.id]
    assert provisioning.get(conn, stale.id).status == "expired"  # type: ignore[union-attr]
    assert provisioning.expire_due(conn) == []


def test_session_and_event_lists_page(conn: sqlite3.Connection, home_id: int) -> None:
    ids = [_session(conn, home_id, f"{n:064d}").id for n in range(3)]
    assert [s.id for s in provisioning.list_sessions(conn, limit=2)] == [ids[2], ids[1]]
    assert [s.id for s in provisioning.list_sessions(conn, before_id=ids[1])] == [ids[0]]
    assert_limit_bounds(lambda limit: provisioning.list_sessions(conn, limit=limit))

    events = [provisioning.add_event(conn, ids[0], step, {"n": n}) for n, step in enumerate(("softap", "join", "done"))]
    assert events[0].detail == {"n": 0}
    assert provisioning.list_events(conn, ids[0], limit=2) == [events[2], events[1]]
    assert provisioning.list_events(conn, ids[0], before_id=events[1].id) == [events[0]]
    assert_limit_bounds(lambda limit: provisioning.list_events(conn, ids[0], limit=limit))


def test_sightings(conn: sqlite3.Connection) -> None:
    provisioning.record_sighting(conn, "D1", "10.0.0.5", at="2026-10-26T10:00:00+00:00")
    provisioning.record_sighting(conn, "D1", "10.0.0.5", at="2026-10-26T10:05:00+00:00")
    provisioning.record_sighting(conn, "D2", "10.0.0.5", at="2026-10-26T10:03:00+00:00")
    latest = provisioning.latest_sighting_for_ip(conn, "10.0.0.5", "2026-10-26T09:00:00+00:00")
    assert latest == provisioning.PairingSighting("D1", "10.0.0.5", "2026-10-26T10:00:00+00:00",
                                                  "2026-10-26T10:05:00+00:00")
    assert provisioning.latest_sighting_for_ip(conn, "10.0.0.5", "2026-10-26T11:00:00+00:00") is None
    assert provisioning.prune_sightings(conn, "2026-10-26T10:04:00+00:00") == 1
    remaining = provisioning.latest_sighting_for_ip(conn, "10.0.0.5", "2026-10-26T09:00:00+00:00")
    assert remaining is not None and remaining.device_id == "D1"

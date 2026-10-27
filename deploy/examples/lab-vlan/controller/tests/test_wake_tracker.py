"""Wake detection replayed against a real capture (2026-10-26 14:44-15:44 UTC).

Fixture: timestamps of frames sent by the iFLO, from
openflo_20261026T144415Z.pcap (tcpdump -tt "ether src 68:67:25:00:00:01").
That hour holds three fully captured natural wakes: provisioning, cartridge
activation, and an unattended wake.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.pop("OPENFLO_READ_ON_WAKE", None)

import app  # noqa: E402

FIXTURE = Path(__file__).parent / "device_frames_20261026T144415Z.txt"


def replay(idle_gap: float) -> list[tuple]:
    tracker = app.WakeTracker(idle_gap)
    events: list[tuple] = []
    last = 0.0
    for line in FIXTURE.read_text().split():
        last = float(line)
        events.extend(tracker.observe(last))
    tail = tracker.expire(last + idle_gap + 1)
    if tail:
        events.append(tail)
    return events


def test_capture_replay_finds_the_three_natural_wakes():
    ends = [e for e in replay(120) if e[0] == "end"]
    durations = [round(last - start) for _, start, last, _ in ends]
    frames = [n for *_, n in ends]
    assert durations == [107, 189, 175]
    assert frames == [1128, 292, 552]
    assert sum(frames) == len(FIXTURE.read_text().split())


def test_every_start_is_closed_exactly_once():
    kinds = [e[0] for e in replay(120)]
    assert kinds == ["start", "end"] * 3


def test_no_end_before_idle_gap_elapses():
    tracker = app.WakeTracker(120)
    tracker.observe(1000.0)
    assert tracker.expire(1100.0) is None
    assert tracker.expire(1121.0)[0] == "end"


def test_controller_sends_nothing_by_default():
    assert app.READ_ON_WAKE is False

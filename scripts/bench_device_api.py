"""Device API load generator for scripts/bench-device-api.sh (stdlib only; runs inside the OpenFLO image).

Each simulated device has its own source IP (X-Forwarded-For, trusted by the scratch server only) and runs the
firmware's sync cycle: healthcheck, update-device, get-schedule, get-bottle, send-events. Prints per-endpoint
and overall p50/p99; exits 1 on any 5xx or transport error, or when overall p99 exceeds --p99-max-ms.

``--seed DB`` instead seeds the scratch database (run inside the scratch server container) and exits.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UPDATE = {
    "batteryLevel": 98, "firmwareVersion": "3.0.64", "connectionLevel": 100, "localIpAddress": "192.168.30.80",
    "bottleSensorStatus": "inserted", "networkName": "OpenFLO", "extPowerState": False, "isProVersion": False,
    "ramUsed": 120000, "ramTotal": 320000, "ramUsedPercent": 37, "HeapFailureCount": 0, "deviceType": 0,
    "pingQuality": 100, "pingLatency": 22, "pingFailureCount": 0, "dnsFailureCount": 0, "noAppMode": 0,
}


def device_id(n: int) -> str:
    return f"BE7C{n:012X}"


def seed(db_path: str, devices: int) -> None:
    """Active devices with dispensing and a weekly schedule on, so get-schedule expands real rules."""
    sys.path.insert(0, "/opt/openflo/backend")
    from app.config import Settings
    from app.main import create_app
    from app.repositories import devices as devices_repo
    from app.services import schedule_rules

    app = create_app(Settings(db_path=db_path))  # migrations already applied by the server; idempotent
    for n in range(devices):
        dev = device_id(n)
        with app.state.db.connection() as conn:
            if devices_repo.get(conn, dev) is None:
                devices_repo.create(conn, dev, "active")
        app.state.repo.update_controls(dev, {"dispensing_enabled": True, "schedules_enabled": True})
        with app.state.db.connection() as conn:
            if not conn.execute("SELECT 1 FROM schedule_rules WHERE device_id = ?", (dev,)).fetchone():
                schedule_rules.create_rule(conn, dev, {"kind": "weekly", "local_time": "09:00", "days_mask": 127,
                                                       "dose_count": 1}, "bench")
    print(f"seeded {devices} devices in {Path(db_path).name}")


def cycle(base: str, n: int) -> list[tuple[str, float, int]]:
    dev = device_id(n)
    headers = {"Content-Type": "application/json", "x-device-id": dev, "X-Forwarded-For": f"10.99.{n // 250}.{n % 250 + 1}"}
    now = int(time.time())
    calls = [
        ("healthcheck", {"deviceId": dev}),
        ("update-device", UPDATE),
        ("get-schedule", {}),
        ("get-bottle", {}),
        ("send-events", {"data": [{"status": 1, "code": 1, "timestamp": now}]}),
    ]
    results = []
    for endpoint, body in calls:
        request = urllib.request.Request(f"{base}/device-api/v2/{endpoint}", json.dumps(body).encode(), headers)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        except OSError:
            status = 0
        results.append((endpoint, (time.perf_counter() - start) * 1000, status))
    return results


def pct(values: list[float], p: float) -> float:
    return statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1] if len(values) > 1 else values[0]


def run(base: str, devices: int, cycles: int, concurrency: int, p99_max_ms: float) -> int:
    jobs = [n % devices for n in range(cycles)]
    with ThreadPoolExecutor(concurrency) as pool:
        samples = [s for batch in pool.map(lambda n: cycle(base, n), jobs) for s in batch]
    by_endpoint: dict[str, list[float]] = defaultdict(list)
    statuses: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for endpoint, ms, status in samples:
        by_endpoint[endpoint].append(ms)
        statuses[endpoint][status] += 1
    print(f"{len(samples)} requests, {devices} devices, concurrency {concurrency}")
    print(f"{'endpoint':<14} {'n':>6} {'p50 ms':>8} {'p99 ms':>8}  status")
    for endpoint, values in by_endpoint.items():
        codes = " ".join(f"{code}x{count}" for code, count in sorted(statuses[endpoint].items()))
        print(f"{endpoint:<14} {len(values):>6} {pct(values, 50):>8.1f} {pct(values, 99):>8.1f}  {codes}")
    every = [ms for _, ms, _ in samples]
    p50, p99 = pct(every, 50), pct(every, 99)
    print(f"{'all':<14} {len(every):>6} {p50:>8.1f} {p99:>8.1f}")
    errors = sum(1 for _, _, status in samples if status == 0 or status >= 500)
    if errors:
        print(f"FAIL: {errors} server or transport errors", file=sys.stderr)
        return 1
    if p99 > p99_max_ms:
        print(f"FAIL: p99 {p99:.1f} ms > {p99_max_ms:.0f} ms", file=sys.stderr)
        return 1
    print(f"PASS: p50 {p50:.1f} ms, p99 {p99:.1f} ms (limit {p99_max_ms:.0f} ms)")
    return 0


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--seed", metavar="DB", help="seed this scratch database and exit")
    args.add_argument("--url", default="http://openflo-bench:8099")
    args.add_argument("--devices", type=int, default=50)
    args.add_argument("--cycles", type=int, default=400, help="sync cycles (5 requests each)")
    args.add_argument("--concurrency", type=int, default=8)
    args.add_argument("--p99-max-ms", type=float, default=500.0)
    opts = args.parse_args()
    if opts.seed:
        seed(opts.seed, opts.devices)
        return 0
    return run(opts.url.rstrip("/"), opts.devices, opts.cycles, opts.concurrency, opts.p99_max_ms)


if __name__ == "__main__":
    sys.exit(main())

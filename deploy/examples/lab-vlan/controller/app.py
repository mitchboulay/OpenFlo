"""OpenFLO local controller — wake-aware monitoring for iFLO devices.

Passive wake detection: a long-running tcpdump on the lab interface groups
frames sent by the device into wake sessions. By default the controller sends
the device nothing. Every local HTTP request reloads the firmware's sleep timer
(continuous /dev_info polling once held it awake for 108 min), so the optional
telemetry read (OPENFLO_READ_ON_WAKE=1) is limited to one request per wake.

Listens on localhost only. Access via SSH tunnel:
  ssh -L 8080:localhost:8080 root@192.168.1.2 "pct exec $CTID -- socat TCP-LISTEN:8080,bind=127.0.0.1,reuseaddr,fork TCP:127.0.0.1:8080"
Or from within the gateway container directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEVICE_IP = os.environ.get("OPENFLO_DEVICE_IP", "192.168.30.80")
DEVICE_MAC = os.environ.get("OPENFLO_DEVICE_MAC", "68:67:25:00:00:01")
DEVICE_PORT = int(os.environ.get("OPENFLO_DEVICE_PORT", "80"))
LAB_IFACE = os.environ.get("OPENFLO_LAB_IFACE", "eth1")
# Device silence that ends a wake. Natural wakes are 33-189 s of dense traffic;
# 120 s separated every session in the 2026-10-26 captures.
WAKE_IDLE_GAP = float(os.environ.get("OPENFLO_WAKE_IDLE_GAP", "120"))
READ_ON_WAKE = os.environ.get("OPENFLO_READ_ON_WAKE", "0").strip().lower() in {"1", "true", "yes", "on"}
DB_PATH = os.environ.get("OPENFLO_DB_PATH", "/var/lib/openflo/openflo.db")
LISTEN_HOST = os.environ.get("OPENFLO_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("OPENFLO_PORT", "8080"))

DEVICE_URL = f"http://{DEVICE_IP}:{DEVICE_PORT}/dev_info"
DEVICE_ID = os.environ.get("OPENFLO_DEVICE_ID", "D8256700000A0001")
BACKEND_URL = os.environ.get("OPENFLO_BACKEND_URL", "http://127.0.0.1:8099")
# The backend's bootstrap API token (EnvironmentFile /etc/openflo/backend.env, OPENFLO_API_TOKEN).
# It stays server-side: the dashboard only talks to this controller.
API_TOKEN = os.environ.get("OPENFLO_API_TOKEN", "")
DEVICE_API = f"/api/v1/devices/{DEVICE_ID}"
RECENT_LIMIT = 10

log = logging.getLogger("openflo")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS wake_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    readings_count INTEGER DEFAULT 0,
    frames INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wake_event_id INTEGER REFERENCES wake_events(id),
    captured_at TEXT NOT NULL,
    signal INTEGER,
    battery INTEGER,
    doses INTEGER,
    bottle_status TEXT,
    firmware_version TEXT,
    device_id TEXT,
    pcb_version TEXT,
    device_type INTEGER,
    device_mode TEXT,
    ext_power_state INTEGER,
    flood_now INTEGER,
    float_en INTEGER,
    wifi_ssid TEXT,
    is_pro_version INTEGER,
    demo_mode_visible INTEGER,
    nam_visible INTEGER,
    user_dispense_visible INTEGER,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_readings_captured ON readings(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_wake ON readings(wake_event_id);
CREATE INDEX IF NOT EXISTS idx_wake_started ON wake_events(started_at DESC);
"""


def get_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(wake_events)")}
    if "frames" not in columns:
        conn.execute("ALTER TABLE wake_events ADD COLUMN frames INTEGER DEFAULT 0")
    return conn


db: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global db
    if db is None:
        db = get_db()
    return db


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DevInfo(BaseModel):
    signal: int = 0
    battery: int = 0
    doses: int = 0
    bottleStatus: str = ""
    wifiSSID: str = ""
    floodNow: bool = False
    floatEn: bool = False
    firmwareVersion: str = ""
    deviceId: str = ""
    extPowerState: bool = False
    pcbVersion: str = ""
    deviceType: int = 0
    deviceMode: str = ""
    isProVersion: bool = False
    demoModeVisible: bool = False
    namVisible: bool = False
    userDispenseVisible: bool = True


# ---------------------------------------------------------------------------
# Passive wake detection
# ---------------------------------------------------------------------------


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class WakeTracker:
    """Groups device frame timestamps into wake sessions. No I/O."""

    def __init__(self, idle_gap: float) -> None:
        self.idle_gap = idle_gap
        self.start: float | None = None
        self.last: float | None = None
        self.frames = 0

    def observe(self, ts: float) -> list[tuple]:
        events: list[tuple] = []
        if self.last is not None and ts - self.last > self.idle_gap:
            events.append(self._close())
        if self.start is None:
            self.start, self.frames = ts, 0
            events.append(("start", ts))
        self.last = ts
        self.frames += 1
        return events

    def expire(self, now: float) -> tuple | None:
        if self.last is not None and now - self.last > self.idle_gap:
            return self._close()
        return None

    def _close(self) -> tuple:
        event = ("end", self.start, self.last, self.frames)
        self.start = self.last = None
        self.frames = 0
        return event


class WakeMonitor:
    """Records wake sessions from a passive tcpdump of frames sent by the device."""

    def __init__(self) -> None:
        self.tracker = WakeTracker(WAKE_IDLE_GAP)
        self.current_wake_id: int | None = None
        self.last_success: float = 0
        self.total_wakes_detected: int = 0
        self.total_polls: int = 0
        self.total_successes: int = 0
        self.total_failures: int = 0
        self.last_reading: dict[str, Any] | None = None
        self.started_at: float = time.time()

    @property
    def device_awake(self) -> bool:
        return self.tracker.start is not None

    async def run(self) -> None:
        while True:
            try:
                await self._watch()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Wake watcher failed, restarting in 5s")
            await asyncio.sleep(5)

    async def _watch(self) -> None:
        proc = await asyncio.create_subprocess_exec(
            "tcpdump", "-l", "-n", "-tt", "-q", "-i", LAB_IFACE, "ether", "src", DEVICE_MAC,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert proc.stdout is not None
        try:
            while True:
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
                except asyncio.TimeoutError:
                    ended = self.tracker.expire(time.time())
                    if ended:
                        self._on_event(ended)
                    continue
                if not line:
                    raise RuntimeError(f"tcpdump exited ({proc.returncode})")
                try:
                    ts = float(line.split(maxsplit=1)[0])
                except (ValueError, IndexError):
                    continue
                for event in self.tracker.observe(ts):
                    self._on_event(event)
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    def _on_event(self, event: tuple) -> None:
        conn = _db()
        if event[0] == "start":
            self.total_wakes_detected += 1
            cur = conn.execute(
                "INSERT INTO wake_events (started_at, readings_count, frames) VALUES (?, 0, 0)",
                (_iso(event[1]),),
            )
            conn.commit()
            self.current_wake_id = cur.lastrowid
            log.info("Wake %d started", self.current_wake_id)
            if READ_ON_WAKE:
                asyncio.get_running_loop().create_task(self._read_once(self.current_wake_id))
        else:
            _, start, last, frames = event
            conn.execute(
                "UPDATE wake_events SET ended_at = ?, frames = ? WHERE id = ?",
                (_iso(last), frames, self.current_wake_id),
            )
            conn.commit()
            log.info("Wake %s ended: %.0f s, %d frames", self.current_wake_id, last - start, frames)
            self.current_wake_id = None

    async def _read_once(self, wake_id: int) -> None:
        """One /dev_info read, never retried: each request extends the wake."""
        self.total_polls += 1
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=2.0)) as client:
                resp = await client.get(DEVICE_URL)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            self.total_failures += 1
            log.warning("Wake %d telemetry read failed: %s", wake_id, exc)
            return
        self.total_successes += 1
        self.last_success = time.time()
        self.last_reading = data
        self._record_reading(wake_id, data)

    def _record_reading(self, wake_id: int, data: dict[str, Any]) -> None:
        conn = _db()
        now_iso = datetime.now(timezone.utc).isoformat()
        info = DevInfo.model_validate(data)
        conn.execute(
            """INSERT INTO readings
               (wake_event_id, captured_at, signal, battery, doses, bottle_status,
                firmware_version, device_id, pcb_version, device_type, device_mode,
                ext_power_state, flood_now, float_en, wifi_ssid, is_pro_version,
                demo_mode_visible, nam_visible, user_dispense_visible, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                wake_id,
                now_iso,
                info.signal,
                info.battery,
                info.doses,
                info.bottleStatus,
                info.firmwareVersion,
                info.deviceId,
                info.pcbVersion,
                info.deviceType,
                info.deviceMode,
                int(info.extPowerState),
                int(info.floodNow),
                int(info.floatEn),
                info.wifiSSID,
                int(info.isProVersion),
                int(info.demoModeVisible),
                int(info.namVisible),
                int(info.userDispenseVisible),
                json.dumps(data),
            ),
        )
        conn.execute(
            "UPDATE wake_events SET readings_count = readings_count + 1 WHERE id = ?",
            (wake_id,),
        )
        conn.commit()

    def status(self) -> dict[str, Any]:
        return {
            "device_awake": self.device_awake,
            "current_wake_id": self.current_wake_id,
            "last_success_epoch": self.last_success,
            "uptime_seconds": int(time.time() - self.started_at),
            "total_wakes_detected": self.total_wakes_detected,
            "total_polls": self.total_polls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "wake_idle_gap_seconds": WAKE_IDLE_GAP,
            "read_on_wake": READ_ON_WAKE,
            "device_url": DEVICE_URL,
            "device_mac": DEVICE_MAC,
            "lab_interface": LAB_IFACE,
            "last_reading": self.last_reading,
        }


monitor = WakeMonitor()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    db = get_db()
    task = asyncio.create_task(monitor.run())
    log.info(
        "OpenFLO controller started: passive wake detection on %s for %s; "
        "telemetry read on wake: %s",
        LAB_IFACE, DEVICE_MAC, "one request" if READ_ON_WAKE else "off",
    )
    yield
    task.cancel()
    if db:
        db.close()


app = FastAPI(title="OpenFLO", lifespan=lifespan)


@app.get("/api/status")
async def api_status() -> JSONResponse:
    return JSONResponse(monitor.status())


class BackendError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


async def _backend(client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """One /api/v1 call; errors (``{code, message}``) become BackendError."""
    try:
        resp = await client.request(method, f"{BACKEND_URL}{path}", json=body,
                                    headers={"Authorization": f"Bearer {API_TOKEN}"})
    except httpx.HTTPError as exc:
        raise BackendError(502, f"backend unreachable: {exc}") from exc
    payload = resp.json() if resp.content else None
    if resp.status_code >= 400:
        message = payload.get("message", resp.text) if isinstance(payload, dict) else resp.text
        raise BackendError(resp.status_code, message)
    return payload


Step = tuple[str, str, "dict[str, Any] | None"]


async def _call(*steps: Step) -> list[Any] | JSONResponse:
    """Run /api/v1 calls concurrently; a failure is answered as ``{detail}``, the shape the dashboard reads."""
    if not API_TOKEN:
        return JSONResponse({"detail": "OPENFLO_API_TOKEN is not configured"}, status_code=503)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            return list(await asyncio.gather(*(_backend(client, *step) for step in steps)))
    except BackendError as exc:
        return JSONResponse({"detail": exc.message}, status_code=exc.status)


def _dashboard_view(detail: dict[str, Any], dispenses: dict[str, Any], events: dict[str, Any]) -> dict[str, Any]:
    """The device view the dashboard was written against, built from /api/v1."""
    recent = dispenses["items"]
    return {
        "device": {k: detail[k] for k in ("device_id", "last_seen", "firmware_version")},
        "controls": {**detail["controls"], "dose_seconds": detail["dosing"]["fixed_seconds"]},
        "latest_telemetry": None if detail["battery_level"] is None else {
            "received_at": detail["last_sync"] or detail["last_seen"],
            "batteryLevel": detail["battery_level"],
            "extPowerState": detail["ext_power"],
            "connectionLevel": detail["signal"],
            "bottleSensorStatus": None,
        },
        "dispenses": {"total": f"{len(recent)}+" if dispenses["next_before_id"] else len(recent), "recent": recent},
        "recent_events": [
            {"received_at": e["received_at"], "kind": e["kind"], "payload_json": json.dumps(e["payload"])}
            for e in events["items"]
        ],
        "remote_dispense": detail["remote_dispense"],
    }


def _respond(result: list[Any] | JSONResponse, body: Any) -> JSONResponse:
    return result if isinstance(result, JSONResponse) else JSONResponse(body(result))


@app.get("/api/device")
async def api_device() -> JSONResponse:
    result = await _call(
        ("GET", DEVICE_API, None),
        ("GET", f"{DEVICE_API}/history?kind=dispenses&limit={RECENT_LIMIT}", None),
        ("GET", f"{DEVICE_API}/history?kind=events&limit={RECENT_LIMIT}", None),
    )
    return _respond(result, lambda r: _dashboard_view(*r))


class ControlsUpdate(BaseModel):
    dispensing_enabled: bool | None = None
    sync_interval_seconds: int | None = None
    dose_seconds: float | None = None


async def _dose_step(seconds: float | None) -> Step | JSONResponse:
    """Fixed seconds, or back to the liquid's default volume dose when cleared."""
    current = await _call(("GET", f"{DEVICE_API}/dosing", None))
    if isinstance(current, JSONResponse):
        return current
    profile = current[0]["profile"]
    amount = {"fixed_seconds": seconds} if seconds is not None else {"dose_ml": profile["default_dose_ml"]}
    return ("PUT", f"{DEVICE_API}/dosing", {"profile_id": profile["id"], **amount})


@app.patch("/api/device/controls")
async def api_device_controls(update: ControlsUpdate) -> JSONResponse:
    # The backend validates ranges and rejects unknown fields; only send what was set.
    changes = update.model_dump(exclude_unset=True)
    steps: list[Step] = []
    if "dose_seconds" in changes:
        step = await _dose_step(changes.pop("dose_seconds"))
        if isinstance(step, JSONResponse):
            return step
        steps.append(step)
    if changes:
        steps.append(("PATCH", f"{DEVICE_API}/controls", changes))
    return _respond(await _call(*steps), lambda r: {"updated": len(r)})


@app.post("/api/device/dispense")
async def api_device_dispense() -> JSONResponse:
    return _respond(await _call(("POST", f"{DEVICE_API}/dispense", None)), lambda r: r[0])


@app.delete("/api/device/dispense")
async def api_device_dispense_cancel() -> JSONResponse:
    return _respond(await _call(("DELETE", f"{DEVICE_API}/dispense", None)), lambda r: r[0])


@app.get("/api/readings")
async def api_readings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    wake_event_id: int | None = Query(None),
) -> JSONResponse:
    conn = _db()
    if wake_event_id is not None:
        rows = conn.execute(
            "SELECT * FROM readings WHERE wake_event_id = ? ORDER BY captured_at DESC LIMIT ? OFFSET ?",
            (wake_event_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM readings ORDER BY captured_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/wake-events")
async def api_wake_events(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM wake_events ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/stats")
async def api_stats() -> JSONResponse:
    conn = _db()
    total_readings = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    total_wakes = conn.execute("SELECT COUNT(*) FROM wake_events").fetchone()[0]
    latest = conn.execute(
        "SELECT battery, doses, bottle_status, signal FROM readings ORDER BY captured_at DESC LIMIT 1"
    ).fetchone()

    avg_wake_duration = conn.execute(
        """SELECT AVG(
             CAST((julianday(ended_at) - julianday(started_at)) * 86400 AS REAL)
           ) FROM wake_events WHERE ended_at IS NOT NULL"""
    ).fetchone()[0]

    wake_intervals = conn.execute(
        """SELECT AVG(gap) FROM (
             SELECT (julianday(started_at) -
                     julianday(LAG(started_at) OVER (ORDER BY started_at))) * 86400 AS gap
             FROM wake_events
           ) WHERE gap IS NOT NULL AND gap > 60"""
    ).fetchone()[0]

    return JSONResponse(
        {
            "total_readings": total_readings,
            "total_wake_events": total_wakes,
            "latest_battery": dict(latest) if latest else None,
            "avg_wake_duration_seconds": round(avg_wake_duration, 1) if avg_wake_duration else None,
            "avg_wake_interval_seconds": round(wake_intervals, 1) if wake_intervals else None,
            "monitor": monitor.status(),
        }
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    if DASHBOARD_PATH.exists():
        return HTMLResponse(DASHBOARD_PATH.read_text())
    return HTMLResponse("<h1>OpenFLO</h1><p>Dashboard not found.</p>")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    import uvicorn

    uvicorn.run(app, host=LISTEN_HOST, port=LISTEN_PORT, log_level="info")

# Mission 007 — Cloud Protocol Reconstruction & Backend Emulator

Date: 2026-10-26. Status: **COMPLETE (static + mock)**. No physical-device
configuration was changed.

## 1. Executive summary

Mission 007 reconstructed the iFLO 3.0.64 device-facing cloud protocol from the
official firmware and built a safe FastAPI emulator with deterministic tests.
The central findings:

- TLS validation is **enabled** via the ESP-IDF `esp-x509-crt-bundle`.
- The API is `POST <host>/device-api/v2/<endpoint>` with JSON bodies.
- All eight known endpoints were mapped; request/response schemas were recovered
  where the firmware supports it.
- Scheduling uses a 33-entry array of `timestamp`, `doseCount`, `cmd`, persisted
  as `schedule.txt`.
- OTA and remote dispense are cloud-triggerable and are suppressed by default in
  the emulator.
- 31 automated tests pass.

## 2. Work performed

1. Re-ran REA/Ghidra against the official image with the local Xtensa workaround.
2. Decompiled the remaining endpoint, schedule, bottle, settings, event, retry
   and sleep functions.
3. Recovered the cloud and local schedule schemas.
4. Implemented `backend/` with all eight endpoint routes, SQLite persistence,
   strict validation, redacted protocol logging and safe defaults.
5. Added deployment templates (Caddy/Compose) and the migration runbook.
6. Added deterministic tests and fixtures.

## 3. Findings

### Protocol

- Base path: `/device-api/v2/`.
- Default host: `https://backend.iflo.com`; override key
  `https-host-address` (full URL, `%s%s`).
- Headers: `Accept: */*`, `Content-Type: application/json`,
  `Accept-Encoding: gzip, deflate, br`, `x-device-id`, and
  `x-device-ott` for registration.
- No Bearer token; the Basic-auth helper exists but is not configured.
- Endpoints: `register`, `update-device`, `get-fw`, `get-bottle`,
  `get-schedule`, `healthcheck`, `send-events`, `create-qc-report`.

### Synchronization

- `update-device` is the central poll; response fields control schedule sync,
  settings/float reset, remote dispense, OTA, Wi-Fi flag and external power.
- Finite waits: 5 s HTTP timeout, 15 s response wait, 15-slot busy wait.
- Malformed JSON/error responses are logged and cleaned up; retry occurs on a
  later wake (INFERRED).

### Scheduling

- Cloud item: `{"timestamp": int, "doseCount": int, "cmd": 0|1}`; max 33.
- Local `schedule.txt`: `{"type":"schedule","time":int,"data":int,"cmd":int}`.
- `cmd=0` normal window; `cmd=1` exact-time window.
- `last-dispense` prevents duplicate firing; entries are cleared after firing.
- Schedules persist in SPIFFS and run locally once time is valid.

### TLS

- CA bundle includes ISRG Root X1/X2 and many commercial roots.
- Device sends **no SNI**; deployment needs `default_sni` or a dedicated IP.
- Hostname-validation details remain UNKNOWN.

## 4. Implementation summary

`backend/`:

- FastAPI, SQLite, Pydantic models;
- strict request validation, unknown-field preservation;
- safe responses: `isUpToDate: true`, no `remoteDispense`, no `url`;
- schedule and bottle endpoints 501 unless explicitly enabled;
- redacted `x-device-ott`; no token plaintext;
- protocol logs and telemetry/history tables;
- Caddy/Compose templates.

See `backend/README.md`.

## 5. Test results

```
31 passed in 0.48s
```

Coverage: registration success/duplicate/invalid/token enforcement; telemetry
success/missing/wrong type/unknown device/unknown field; schedule disabled and
enabled; sync flag; schedule items; get-fw OTA suppression; health/events/QC;
malformed JSON; oversized body; log redaction; static-derived fixtures;
protocol fixture round-trips.
deterministic protocol replay (clean wake, schedule sync cycle, schedule with
items, firmware check, full wake with events, firmware version tracking, open
enrollment, protocol log completeness, safety invariants for dispense and OTA).

## 6. Deliverables

- `research/device-cloud-protocol.md`
- `research/device-sync-state-machine.md`
- `research/device-scheduling-protocol.md`
- `research/openflo-backend-deployment.md`
- `research/backend-migration-runbook.md`
- `research/controller-backend-integration.md`
- `research/mission-008-proposal.md`
- `backend/` source, tests, fixtures, deployment templates
- `research/mission-007.md` (this report)

## 7. Acceptance criteria

| Criterion | Status |
|---|---|
| All eight endpoints documented | PASS |
| Request/response fields with evidence | PASS (unknowns marked) |
| Sync/scheduling state machines reconstructed as far as supported | PASS (explicit gaps) |
| Unknown fields explicitly identified | PASS |
| Runnable emulator | PASS |
| Automated tests pass | PASS (31) |
| Remote dispense/OTA disabled by default | PASS |
| Private TLS deployment design | PASS (design only) |
| Migration/rollback plan | PASS (plan only) |
| Mission 008 ready for approval | PASS (proposal) |

**Full protocol compatibility is not claimed.**

## 8. Limitations / unresolved gaps

- `send-events` payload schema.
- Bottle `config` object schema.
- Exact QC/bottle enum strings.
- Exact 2.20.5 version-floor branch and `0x51402` threshold.
- Final `esp_deep_sleep_start` call site not isolated.
- Host-change handler `/config` not fully traced; factory reset is not a proven
  recovery.
- No physical-device validation.

## 9. Physical-device statement

**No physical-device configuration was changed.** No firmware was flashed or
modified; no traffic was redirected; no DNS/firewall/Caddy route was changed; no
dispense, schedule, No-App Mode or OTA was triggered; the emulator was not
deployed into the live device path.

Mission 008 requires explicit operator approval.

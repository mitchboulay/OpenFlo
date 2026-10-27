# OpenFLO device backend emulator

A standalone FastAPI service implementing the iFLO 3.0.64 device-facing API
under `/device-api/v2/`. It is designed for **mock/offline testing** and is not
connected to the physical device in Mission 007.

## Safety defaults

- **OTA is suppressed**: `/get-fw` returns `actualFirmwareVersion` and no
  `url`; `/update-device` returns `isUpToDate: true` and no `url`.
- **Remote dispense is never emitted**: no `remoteDispense` field is returned.
- **Schedules are off per device**: `/get-schedule` serves `[]` unless the operator turns on both dispensing
  and schedules for the device, and while it is flagged or retiring. Rules expand server-side into at most 33
  entries, always with `cmd: 0`.
- **Bottle responses are disabled** unless `OPENFLO_BACKEND_ENABLE_BOTTLE=true`.
- **Settings resets are not emitted**: `isSettingsSynced` is omitted.
- Unknown inbound fields are preserved in telemetry for diagnostics.
- `x-device-ott` is never logged or stored in plaintext (only SHA-256).

## Run

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
OPENFLO_BACKEND_DB="$PWD/openflo-backend.db" \
  .venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8099
```

The service is intentionally bound to localhost by default. Do not expose it
publicly.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENFLO_BACKEND_DB` | `openflo-backend.db` | SQLite path |
| `OPENFLO_FIRMWARE_VERSION` | `3.0.64` | Value returned by `/get-fw` |
| `OPENFLO_BACKEND_ENABLE_BOTTLE` | `false` | Enable experimental `/get-bottle` |
| `OPENFLO_UNCLAIMED_CAP` | `10` | Most `unclaimed` device rows that unknown device IDs may create |
| `OPENFLO_BACKEND_LOG_PAYLOADS` | `true` | Store request/response JSON in `protocol_logs` |
| `OPENFLO_BACKEND_MAX_BODY_BYTES` | `65536` | Request body limit |
| `OPENFLO_UI_DIST` | `<repo>/ui/dist` | Built UI served at `/` with SPA fallback; skipped when absent |
| `OPENFLO_BACKEND_HOST` / `PORT` | `127.0.0.1` / `8099` | `__main__` runner |

### Enrollment and trust

The firmware sends `x-device-ott` for registration and `x-device-id` for normal
calls. Those headers are **not authentication**: device IDs are enumerable and the
firmware has no secret. Which devices are served comes from `devices.status` in the
database (`active`/`provisioning` are served; `unclaimed`, `retired` and unknown IDs
get `DEVICE_NOT_REGISTERED`). `/device-api/*` applies **mitigations**, not
authentication: a per-IP token bucket (300 requests / 5 min), a 10/min per-IP limit
on unknown device IDs, the unclaimed-row cap, identity flags (`ip_conflict`,
`telemetry_implausible`) that withhold the bottle, remote dispense and schedules
until acknowledged, and no payload logging for unknown IDs. Limiter state is in
memory (one process; a restart resets it). Residual impersonation risk remains:
anyone who knows a device ID and can reach the backend can send telemetry as that
device.

## Endpoints

| Endpoint | Default behavior |
|---|---|
| `POST /register` | 200 `{}` for an `active`/`provisioning` device or while a provisioning session awaits a join (stores the OTT hash); else 422 `NOT_FOUND` |
| `POST /update-device` | 200 `{"data":{"isUpToDate":true,"isScheduleSynced":…}}`; `isScheduleSynced` is false while the schedule the device should hold differs from the one last served; stores telemetry |
| `POST /get-fw` | 200 `{"actualFirmwareVersion":"3.0.64"}`; no OTA URL |
| `POST /get-schedule` | 200 `{"data":[{"timestamp","doseCount","cmd":0}]}` (≤ 33), or `[]` when paused, retiring or flagged |
| `POST /get-bottle` | 501 `NOT_IMPLEMENTED` unless bottle enabled |
| `POST /healthcheck` | 200 `{}` |
| `POST /send-events` | 200 `{}`; stores payload |
| `POST /create-qc-report` | 200 `{}`; stores report |

Error responses use the firmware-visible form:

```json
{"fields": {}, "code": "INVALID_DEVICE_ID", "message": "..."}
```

## Tests

```bash
cd backend
.venv/bin/pytest -q
```

Tests are deterministic and use temporary SQLite databases. They do not contact
the device or the vendor cloud.

## Known gaps

- `/get-bottle` config schema is only partially recovered; disabled by default.
- `send-events` payload schema is not recovered; payloads are preserved opaquely.
- `isSettingsSynced` behavior is only partially traced (float control reset).
- Schedule `cmd=1` exact-time window and `shift-time` semantics are inferred from
  static analysis, not runtime-tested.

See `../research/device-cloud-protocol.md`, `../research/device-scheduling-protocol.md`
and `../research/device-sync-state-machine.md`.

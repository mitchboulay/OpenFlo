# Device cloud protocol — iFLO 3.0.64

Date: 2026-10-26. Method: static decompilation of the official image
(`artifacts/firmware/iflo-3.0.64.elf`) with REA 6.4.0 + Ghidra 12.2,
language `Xtensa:LE:32:default`. No device traffic was generated or redirected.

Classification:

- **CONFIRMED_STATIC** — traced to firmware instructions/data.
- **CONFIRMED_RUNTIME** — observed in authorized device behavior.
- **INFERRED** — supported indirectly; not proven.
- **UNKNOWN** — insufficient evidence.

## 1. Transport

| Property | Value | Class | Evidence |
|---|---|---|---|
| Base host | `https://backend.iflo.com` default, overridable by `https-host-address` | CONFIRMED_STATIC | `FUN_40092ec0`, string `0x3f00a114` |
| Base path | `/device-api/v2/` | CONFIRMED_STATIC | `FUN_400942c0`, string `0x3f00b340` |
| Method | `POST` (method value `1`) | CONFIRMED_STATIC | `FUN_40092f80` callers; ESP-IDF `HTTP_METHOD_POST` |
| URL construction | `host + path` via `%s%s` | CONFIRMED_STATIC | `FUN_40092f50`, format `0x3f00a1d0` |
| Request body | JSON | CONFIRMED_STATIC | `FUN_40092f80` sets `Content-Type: application/json` |
| TLS | ESP-IDF `esp-x509-crt-bundle`; certificate validation enabled | CONFIRMED_STATIC | `FUN_400abed4`, config `0x3ffc4bb8` |
| HTTP timeout | 5000 ms | CONFIRMED_STATIC | config `+0x4c = 0x1388` |
| Receive buffer | 2048 bytes | CONFIRMED_STATIC | config `+0x16c = 0x800`; `FUN_40092d10` |
| Busy wait | 15 iterations before request slot is considered busy | CONFIRMED_STATIC | `FUN_40092f80` |
| Response wait | 150 × 100 ms (15 s) | CONFIRMED_STATIC | `FUN_40094c80` |

### Request headers

| Header | Value | Class | Evidence |
|---|---|---|---|
| `Accept` | `*/*` | CONFIRMED_STATIC | `FUN_40092f80`, string `0x3f00a210` |
| `Content-Type` | `application/json` | CONFIRMED_STATIC | `FUN_40092f80` |
| `Accept-Encoding` | `gzip, deflate, br` | CONFIRMED_STATIC | `FUN_40092f80` |
| `x-device-id` | device identifier | CONFIRMED_STATIC | `FUN_400942c0` callers, `FUN_40097ee0` |
| `x-device-ott` | one-time provisioning token | CONFIRMED_STATIC | `FUN_40093f50` |

There is no Bearer token. `FUN_400ca250` is the ESP-IDF Basic-auth helper, but
the request wrapper does not set it and the HTTP config's username/password
fields are zero. Treat `x-device-id` as an identifier, not a secret.

## 2. Endpoints

| Endpoint | Handler | Request body | Success body | Class |
|---|---|---|---|---|
| `/register` | `FUN_40093f50` | `{"deviceId": string}` | `{}` (body unused) | CONFIRMED_STATIC |
| `/update-device` | `FUN_40094c80` | telemetry object | `{"data": {...}}` | CONFIRMED_STATIC |
| `/get-fw` | `FUN_40094560` | `{"firmwareVersion": string, "deviceId": string}` | `{"actualFirmwareVersion": string, "url": {...}}` | CONFIRMED_STATIC |
| `/get-bottle` | `FUN_400949bc` | empty | `{"data": {...}}` or `{"bottle": {...}}` | CONFIRMED_STATIC |
| `/get-schedule` | `FUN_40094b00` | empty | `{"data": [...]}` or `{"schedule": [...]}` | CONFIRMED_STATIC |
| `/healthcheck` | `FUN_4009446c` | `{"deviceId": string}` | ignored; 200 is success | CONFIRMED_STATIC |
| `/send-events` | `FUN_40095300` | JSON object/array (schema UNKNOWN) | ignored; 200 is success | PARTIAL |
| `/create-qc-report` | `FUN_400942e8` | QC object (below) | ignored; 200 is success | CONFIRMED_STATIC |

### 2.1 `/register`

Request:

```json
{"deviceId": "D8256700000A0001"}
```

Header: `x-device-ott: <one-time token>`.

- 200: registration accepted. The body is not parsed; `{}` is safe.
- 422: top-level `code` and `message`; `NOT_UNIQUE` and `NOT_FOUND` are
  recognized. `fields` is optional.
- Side effects: stores `registred=1`, clears `INVALID_DEVICE_ID` state, updates
  device registration state (`FUN_40093f50`).

### 2.2 `/update-device`

Request body (all keys traced to `FUN_40094c80`):

| Field | Type | Class | Notes |
|---|---|---|---|
| `batteryLevel` | number | CONFIRMED_STATIC | percentage |
| `firmwareVersion` | string | CONFIRMED_STATIC | e.g. `3.0.64` |
| `connectionLevel` | number | CONFIRMED_STATIC | Wi-Fi signal |
| `localIpAddress` | string | CONFIRMED_STATIC | device IP |
| `bottleSensorStatus` | string | CONFIRMED_STATIC key, INFERRED value format | built as `"inserted" + status*0x20`; exact enum not isolated |
| `networkName` | string | CONFIRMED_STATIC | SSID |
| `extPowerState` | boolean | CONFIRMED_STATIC | external power |
| `isProVersion` | boolean | CONFIRMED_STATIC | `pro-device` flag |
| `ramUsed` | number | CONFIRMED_STATIC | bytes |
| `ramTotal` | number | CONFIRMED_STATIC | bytes |
| `ramUsedPercent` | number | CONFIRMED_STATIC | percent |
| `HeapFailureCount` | number | CONFIRMED_STATIC | capital H is literal |
| `deviceType` | number | CONFIRMED_STATIC | 0 BASIC, 1 PRO, 2 MINI, 3 SEPTIC |
| `pingQuality` | number | CONFIRMED_STATIC | |
| `pingLatency` | number | CONFIRMED_STATIC | |
| `pingFailureCount` | number | CONFIRMED_STATIC | |
| `dnsFailureCount` | number | CONFIRMED_STATIC | |
| `noAppMode` | number | CONFIRMED_STATIC | literal `0` in this build |

Response `data` fields:

| Field | Type | Class | Effect |
|---|---|---|---|
| `extPowerState` | boolean | CONFIRMED_STATIC | updates external-power state; may emit events |
| `remoteDispense` | object | CONFIRMED_STATIC | `isActive` bool + numeric `nonce`; **motor actuation** |
| `isScheduleSynced` | boolean | CONFIRMED_STATIC | false triggers schedule refresh |
| `isSettingsSynced` | boolean | CONFIRMED_STATIC | false triggers float/settings reset |
| `isWifiUpdated` | boolean | CONFIRMED_STATIC | clears Wi-Fi-updated flag |
| `isUpToDate` | boolean | CONFIRMED_STATIC | false triggers OTA path |
| `url` | object | CONFIRMED_STATIC | `{redirectLocation: string}` |
| `code`, `message`, `fields` | mixed | CONFIRMED_STATIC | error path |

If `data` is missing, the parser logs an error and does not process fields.
Unknown fields are ignored by the parser.

### 2.3 `/get-fw`

Request: `{"firmwareVersion": string, "deviceId": string}`.

Response root (no `data` wrapper):

```json
{"actualFirmwareVersion": "3.0.64", "url": {"redirectLocation": "..."}}
```

- `actualFirmwareVersion` is read from the root.
- `url.redirectLocation` is read from the root; if absent, no OTA URL is set.
- Only HTTP 200 is treated as success; non-200 is logged as an error.
- Side effect: `FUN_40099ca0` copies the URL into the 0x200-byte OTA buffer and
  sets the OTA-pending flag via `FUN_40099c90`.

### 2.4 `/get-bottle`

Request body: empty.

Response root: `data` (normal) or `bottle` (alternate parse mode). On the cloud
path, `data` supplies `dispenseLeft` / `dispenseNumber`; `config` is a
**root-level sibling of `data`**, not a child of it.

Required fields (`FUN_40094750`):

| Field | Path | Type | Class |
|---|---|---|---|
| `dispenseLeft` | `data` | number | CONFIRMED_STATIC; `> 0` is the authorization bit |
| `dispenseNumber` | `data` | number | CONFIRMED_STATIC; total capacity, written to `max-doses` |
| `config` | **root** | array | CONFIRMED_STATIC; per-dose `{index, dispenseTime}` timings (100 ms units; index = used dose count) |
| `dispenseTime` | `data` | number | CONFIRMED_STATIC (read, value unused) |
| `bottleId` | `data` | string | CONFIRMED_STATIC (read, value unused) |
| `isNonScheduledDispense` | `data` | boolean | CONFIRMED_STATIC (device type 3 only) |

The device computes `used-dose-cnt = dispenseNumber - dispenseLeft`, writes
`max-doses = dispenseNumber`, applies the root `config` to `disp-timings`, and
only calls the validation path when `dispenseLeft != 0`. Validation sets
`bttl-vald=1` (state `OK`) when the bottle is physically inserted and
`dispenseNumber > dispenseLeft`.

Error path: root `fields`, `code`, `message`. Recognized codes:
`INVALID_DEVICE_ID` (factory reset) and `BOTTLE_INSTALLED_NOT_AUTHORIZED`
(state `UNCO`, `bttl-vald=0`).

Side effects: sets dispense counters, applies bottle `config`, updates bottle
state, may force a wake-timer change (`FUN_4008fa3c(15)`).

The local state machine, error handling and a ready-to-serve record are in
[`bottle-authorization.md`](bottle-authorization.md). The short version: the
device has no bottle tag reader; GPIO13 is a seat switch, and authorization is
the cloud's `dispenseLeft > 0` assertion.

### 2.5 `/get-schedule`

Request body: empty.

Response root: `data` (normal) or `schedule` (alternate parse mode), an array of
objects:

| Field | Type | Class | Notes |
|---|---|---|---|
| `timestamp` | number | CONFIRMED_STATIC | epoch seconds |
| `doseCount` | number | CONFIRMED_STATIC | stored as a byte; 1/2 used by action path |
| `cmd` | number | CONFIRMED_STATIC | optional; 0 normal window, 1 exact-time window |

Maximum 33 entries (0x21). Missing items are skipped. The parser clears the
in-memory schedule, stores entries via `FUN_400960b4`, writes `schedule.txt`,
and sets the schedule-loaded flag.

### 2.6 `/healthcheck`

Request: `{"deviceId": string}`. Response body is ignored; HTTP 200 is success.
Any other status is logged and returns an error to the local flow.

### 2.7 `/send-events`

Request body is a JSON value built by the event manager (exact schema
**UNKNOWN**). The firmware send path checks HTTP 200; 422 is treated as a
failure and the event state is retried later. The emulator accepts and stores
the payload opaquely.

### 2.8 `/create-qc-report`

Request:

```json
{
  "deviceId": "...",
  "sessionId": 123,
  "data": {
    "bottleSwitchPassed": "PASSED",
    "userDispenses": "PASSED",
    "firmwareVersion": "3.0.64",
    "floatTestPassed": "skipped",
    "proVersion": false,
    "deviceType": 0
  }
}
```

`bottleSwitchPassed`, `userDispenses` and `floatTestPassed` are strings; the
exact enum values are UNKNOWN. Response body is ignored; HTTP 200 is success.

## 3. Error handling and retries

- `FUN_40093048` = HTTP status code.
- `FUN_40093054` = request state: `0` complete, `-1` error.
- `FUN_40093060` = response body pointer.
- `FUN_40093074` = reset status/body/state.
- `FUN_40094c80` waits up to 150 × 100 ms for a response.
- Malformed JSON (`FUN_400a32bc` returns 0) is logged; the call returns an error
  and the state is cleaned up. Immediate tight retry was not observed; the next
  wake/sync cycle retries (INFERRED).
- HTTP 422 is a semantic failure with `code`/`message`; other non-200 statuses
  are generic failures.
- Backend unavailability does not appear to busy-loop indefinitely; the request
  task has finite waits and the device returns to its sleep/sync schedule
  (INFERRED; not runtime-tested).

## 4. Authentication and trust

- Registration uses `x-device-ott`; normal calls use `x-device-id`.
- The headers are not cryptographic proof of identity. A device ID is present in
  telemetry, local `/dev_info`, and mDNS; it must be treated as an identifier.
- Recommended emulator model: enrollment allowlist of OTT hashes, network
  isolation, and per-device registration. Residual impersonation risk remains.
- Do not invent a firmware-supported token scheme; the firmware has no such
  mechanism.

## 5. Side effects summary

| Response field | Device action |
|---|---|
| `remoteDispense.isActive` | **Dispense** (type 4 remote); nonce deduplicates |
| `isUpToDate=false` + `url.redirectLocation` | OTA download/validation |
| `isScheduleSynced=false` | Fetch `/get-schedule` |
| `isSettingsSynced=false` | Float/settings reset path |
| `isWifiUpdated=true` | Clears Wi-Fi-updated flag |
| `extPowerState` | Updates power state / events |
| `data.url.redirectLocation` | OTA URL buffer |

The emulator must omit `remoteDispense`, omit `url`, and return
`isUpToDate: true`.

## 6. Residual gaps

- `send-events` payload schema.
- ~~Bottle `config` object schema~~ — resolved: array of `{index, dispenseTime}`;
  see [`bottle-authorization.md`](bottle-authorization.md) and
  [`flow-and-dispense-calibration.md`](flow-and-dispense-calibration.md).
- Exact `bottleSensorStatus` and QC enum strings (bottle states are
  `OK`/`MISS`/`EMPT`/`UNCO`; the telemetry string construction is inferred).
- Exact vendor `dispenseTime` calibration values per liquid (the unit is
  100 ms; the values are proprietary/empirical).
- Exact 2.20.5 version-floor branch and `0x51402` device-type threshold.
- Whether the vendor backend requires fields the firmware tolerates as missing.
- Secure-boot/signature state (not in the app image).

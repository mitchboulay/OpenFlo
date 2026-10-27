# Mission 008B — Final Migration Readiness

Date: 2026-10-26 (about 20:00–20:30 UTC). Status: **COMPLETE. Mission 008C
recommended GO** under the operator's risk acceptance. No physical-device action
was taken.

## 1. Migration mechanics (`firmware-provisioning-and-responses.md`)

- **No non-destructive host change exists** [S]. `SERVER_CREDENTIALS` and `TOKEN`
  are refused when registered. Wi-Fi-edit mode changes only the SSID and password.
- **Reset modes** [S]:
  - Mode 0 wipes registration, host, Wi-Fi **and cartridge state** (`bttl_vald`,
    `max_doses`, `started_disp_cnt`, `dose_time`).
  - Mode 1 keeps the cartridge but is reachable only via a `NOT_UNIQUE`
    registration reply.
  - Triggers: `/dev_actions restoreToDefault` → 0; reset button long press → 0;
    `INVALID_DEVICE_ID` and `GET /resetdefault` → unknown mode, assume 0.
- **SoftAP** [S]: unregistered → AP at boot; SSID `iFLO device`, password
  `13106423`, WPA/WPA2; IP `192.168.4.1` [I]. The AP lifetime is unknown.
- **Provisioning** [S]: `POST /config` with `TOKEN` (≥ 4 chars) +
  `SERVER_CREDENTIALS` + `WIFI_CONFIG {ssid, pass}`. That starts `Pairing_task`:
  join Wi-Fi, loop `healthcheck` until 200, wait ≤ 30 s for token and host, then
  `register` (≤ 3 tries, `x-device-ott`, `{"deviceId"}`). Only 200 succeeds.
- **Fail-safe quirk** [S]: at boot, an unregistered device that has saved Wi-Fi
  marks itself registered. So a failed `register` still yields syncs to the
  provisioned host.
- **Response handling** [S]:
  - The HTTP status is never checked, and absent fields are no-ops.
  - `remoteDispense` *presence* dispenses; `isUpToDate` ≠ true plus a `url` → OTA.
  - Error bodies **without `fields` are ignored**.
  - Reset codes: `INVALID_DEVICE_ID`, `NOT_UNIQUE`. `NOT_FOUND` fails registration.
- **Danger** [S]: a user-button long press can reach the manual-dispense routine.

Spot-checked against the decompiler myself:
- The pairing loop calls `FUN_4009446c` (`healthcheck`, with `deviceId`) until it
  succeeds, and only then calls `FUN_40093f50` (`register`).
- `update-device` `INVALID_DEVICE_ID` → `FUN_40097e50` (restore + restart).
- `/config`'s `SERVER_CREDENTIALS` is guarded by `!Device_is_registred()`.

## 2. Emulator fixes (deployed to the gateway container)

| Fix | Why |
|---|---|
| **P0-3:** `healthcheck` returns 200 for an allowlisted device even when unregistered (403 for others) | Pairing blocks on `healthcheck` before `register`; it previously got 422 |
| Error envelopes drop `fields` everywhere | The firmware then ignores every error body (defense in depth on top of the reset-code guard) |
| DB-loss / failed-register re-adoption, **opt-in** (`OPENFLO_ADOPT_UNREGISTERED`, default off; lab unit on): an allowlisted ID from an allowed source is re-registered on first API call (`ott_sha256 = "adopted"`) | The firmware never re-registers on its own. Bypasses the token pin, so it is lab-only and not community-ready |
| (008A) Reset codes impossible to construct; device-ID + source allowlists | — |

`isScheduleSynced` is emitted only when schedules are enabled (off), so it can't
trigger schedule fetches.

**Tests: 40 passed** (locally and on the gateway container). New tests:
- the full firmware pairing sequence (healthcheck before registration → register
  → update-device);
- healthcheck rejects unknown devices;
- no `fields` in any non-200 body, across every endpoint × bad input;
- DB-loss re-adoption, and no adoption from the wrong source or without an
  allowlist;
- reset codes absent everywhere.

## 3. Controller fix (deployed, re-enabled)

- Continuous `/dev_info` polling is replaced by **passive wake detection**: one
  long-running `tcpdump` of frames from the device, grouped into wakes with a
  120 s idle gap.
- **Zero requests to the device by default.** `OPENFLO_READ_ON_WAKE=1` allows
  exactly one `/dev_info` read per wake, never retried.
- Wake rows now record `frames`; the schema migrates in place.
- **Replay test against the real capture** (`openflo_20261026T144415Z.pcap`):
  the three natural wakes are reproduced exactly (107/189/175 s;
  1128/292/552 frames). **4 tests passed.**
- Live: active and enabled, `read_on_wake: false`, 0 TCP connections to the
  device. The dashboard route on the proxy container works again.

## 4. Deliverables

`migration-runbook.md`, `mission-008c-approval-request.md`,
`firmware-provisioning-and-responses.md` (new), this report. Code:
`backend/app/{main.py,errors.py,services/registry.py,api/device_v2.py}`,
backend tests, `controller/app.py`, `controller/tests/`,
`scripts/deploy-controller.sh`.

## 5. Remaining unknowns

- How mbedTLS behaves on the real handshake (only the first contact proves it).
- The AP lifetime (`act-time-ap`); the SoftAP IP (inferred `192.168.4.1`).
- Reset mode for `/resetdefault` and `INVALID_DEVICE_ID`; the reset button's hold time.
- Whether the cartridge can be re-activated without the vendor app after the mode-0 wipe.
- The steady-state idle interval (no 24 h baseline, per the operator's decision).

## 6. Physical-device statement

Nothing was sent to the device. Captures were untouched; VLAN isolation is unchanged.

# Device enrollment readiness — Mission 008 Phase 4

Date: 2026-10-26. Static analysis only. No configuration changes sent.

## Mission 008A update — enrollment hardened

Open enrollment (§1, §3 below) has been replaced:

| Control | Setting (`openflo-backend.service`) | Tested |
|---|---|---|
| Device-ID allowlist | `OPENFLO_ALLOWED_DEVICE_IDS=D8256700000A0001` | stranger ID → 403 `DEVICE_NOT_ALLOWED` |
| Registration source | `OPENFLO_REGISTER_ALLOWED_SOURCES=192.168.30.80` | `.250` on VLAN 30 → 403; forged `X-Forwarded-For` via the proxy container LAN path → 403 |
| Proxy trust | uvicorn trusts `X-Forwarded-For` only from `127.0.0.1` (the gateway container Caddy) | registration recorded the true client IP |
| Network | nftables: only device MAC+IP reaches `192.168.30.1:443`; Caddy repeats the IP check | non-device client blocked at both layers |
| Unregistered devices | `require_registration=true` → 422 on all other endpoints | stranger `update-device` → 422 |
| OTT | Any OTT is still accepted from the allowed device and source (original OTT unknown); stored as SHA-256 only | no plaintext in DB or Caddy logs |

**Superseded by Phase 8 (`backend-recovery-readiness.md`, CONFIRMED_STATIC and
spot-checked against the decompiler output):** §2, §4, §5 and §6 below are wrong
for this device.

- The firmware does **not** re-register with a new backend on its own.
  Registration runs only inside `Pairing_task`, during provisioning of an
  *unregistered* device.
- `update-device` answered with `code: "INVALID_DEVICE_ID"` **factory-resets** the
  device. The emulator returned exactly that for unregistered devices; it now
  returns `DEVICE_NOT_REGISTERED`. `app/errors.py` refuses to construct
  `INVALID_DEVICE_ID` or `NOT_UNIQUE`, with a regression test across every
  endpoint (35 tests; deployed).
- A host-only `POST /config` on a registered device is silently ignored (200).

The real enrollment flow is: reset → SoftAP `POST /config` (`TOKEN` +
`SERVER_CREDENTIALS` + `WIFI_CONFIG`) → `Pairing_task` → `register` (allowed ID
and source) → 200 → later `update-device` → 200 `isUpToDate`.

**Residual spoofing risk:** device ID, IP and MAC are identifiers, not
authentication. A VLAN 30 host that clones the device's MAC and IP while it
sleeps could enroll and post telemetry. The impact is bounded by safe mode (no
dispense, OTA or schedule can be issued). After the first real registration,
pin the presented OTT with `OPENFLO_ENROLL_TOKEN_SHA256=<hash from the
registrations table>`.

The backend was reset to an empty DB after synthetic tests (archived in
`/root/backups/m008a-*/synthetic-test-db/` on the gateway container), so the device is
**not** pre-registered and will exercise the registration path.

## 1. Is a valid `x-device-ott` available?

**INFERRED YES — with caveats.**

The OTT (one-time token) was passed to the device during initial provisioning
via `POST /config` as `{"type": "TOKEN", "data": "<ott>"}`. The device stores
it in SPIFFS and sends it as the `x-device-ott` header on `/register`.

- The original OTT value is **UNKNOWN** — it was transmitted over the SoftAP
  hotspot during setup (plain HTTP to 192.168.4.1:80) and was not captured
  (the VPN detection blocked our capture tool).
- The vendor cloud already accepted this OTT and registered the device
  (device ID `D8256700000A0001`).
- The emulator does NOT require a specific OTT when
  `OPENFLO_ENROLL_TOKEN_SHA256` is empty (the current deployment default).
  Any OTT, including whatever the device already has stored, will be accepted.

**Risk:** If `OPENFLO_ENROLL_TOKEN_SHA256` is set, and the device's stored
OTT doesn't match, registration will fail with 403. **Mitigation:** Leave
enrollment tokens unconfigured for the initial integration test. Add
enforcement after the protocol is validated.

## 2. Does changing the backend require re-registration?

**INFERRED YES.**

The firmware's registration handler (`FUN_40093f50`) sets `registred=1` in
SPIFFS and clears the `INVALID_DEVICE_ID` state. This flag persists across
reboots but is **per-backend** — the vendor cloud's registration state is not
shared with OpenFLO.

When the device contacts a new backend:
1. The first `update-device` call sends `x-device-id: D8256700000A0001`.
2. If the backend has `require_registration=true` (our default) and doesn't
   recognize the device, it returns 422 `INVALID_DEVICE_ID`.
3. The firmware recognizes this error code and triggers the registration path,
   sending `/register` with the stored `x-device-ott`.

**This is the normal flow.** The device handles backend-unknown-device
gracefully — it re-registers. The emulator accepts this registration and
subsequent calls work normally.

**Alternative:** Set `OPENFLO_BACKEND_REQUIRE_REGISTRATION=false`. The emulator
will accept any `x-device-id` without prior registration. This is simpler
but loses the enrollment audit trail.

## 3. Can the emulator accept an already-registered device safely?

**CONFIRMED YES.**

The emulator's `register` endpoint is idempotent. Calling it multiple times
with the same device ID succeeds (200). The device row is created on first
call and touched on subsequent calls. The OTT SHA-256 is logged for each
attempt but the plaintext is never stored.

## 4. Does `POST /config` accept a host-only update?

**INFERRED YES — with encoding caveat.**

The `POST /config` endpoint accepts a JSON array in `data`:

```json
{
  "data": [
    { "type": "SERVER_CREDENTIALS", "host": "https://openflo-backend.home.example.com" }
  ]
}
```

From firmware analysis (`FUN_40092f20`): the handler parses the
`SERVER_CREDENTIALS` type and stores `host` to SPIFFS key
`https-host-address`. The WiFi and TOKEN entries are optional.

**Encoding caveat:** The JavaScript on the device's provisioning page uses a
custom encoder (`L()` function) that transforms characters with charCode > 127
using a Cyrillic-aware mapping. For ASCII-only URLs (our case), this is a
no-op. The raw JSON body should work.

**NOT TESTED.** This is the first actual device mutation and requires Phase 6
approval.

## 5. Does the host change affect WiFi configuration?

**INFERRED NO.**

The `POST /config` handler processes each `data` item by `type`:
- `WIFI_CONFIG` → updates WiFi SSID/password
- `SERVER_CREDENTIALS` → updates `https-host-address`
- `TOKEN` → updates the OTT

Each type is independent. Sending only `SERVER_CREDENTIALS` should leave
WiFi unchanged. The device will continue connecting to the `OpenFLO` SSID
on VLAN 30.

**Risk:** The firmware's config handler has not been runtime-tested with a
partial payload. If it requires all three types, the call may fail silently
or reset WiFi. **Mitigation:** Capture the response; if the device drops off
WiFi, the current credentials are known (`OpenFLO` SSID, password stored in
provisioning docs).

## 6. Can the original backend value be restored?

**INFERRED YES — through the same `POST /config` mechanism.**

Rollback is: `POST /config` with
`{"data": [{"type": "SERVER_CREDENTIALS", "host": "https://backend.iflo.com"}]}`.

This writes the original value back to SPIFFS `https-host-address`. On the
next wake, the device would resolve `backend.iflo.com` and resume vendor
cloud communication.

**Prerequisites for rollback:**
- The device must be awake and its local HTTP server (port 80) reachable.
- The wake window is brief (~52-183s observed). The operator must act within
  this window.
- The controller's passive wake detection (tcpdump on eth1 for device MAC)
  alerts when the device is available.

## 7. Is the device locally reachable after a failed host change?

**INFERRED YES.**

The local HTTP server on port 80 is independent of the cloud backend
connection. It runs on the device's WiFi interface and is available whenever
the device is awake, regardless of whether the cloud connection succeeds or
fails.

If `POST /config` sets an unreachable host:
1. The device wakes normally (timer-based).
2. It connects to WiFi (`OpenFLO` SSID).
3. It tries to reach the new host — DNS failure or TLS failure.
4. The cloud connection fails, but WiFi stays up during the wake window.
5. The local HTTP server on port 80 is reachable during this window.
6. The operator can send the rollback `POST /config` to restore the original
   host.

**Risk:** If the failed cloud connection causes the device to stay awake
longer (retry loop) or shorter (immediate sleep on failure), the rollback
window may differ from baseline. The firmware's retry behavior after a failed
connection is INFERRED to be: log, clean up, continue wake cycle, sleep
normally. But this is not runtime-confirmed.

## Rollback procedure

### Proven steps
None. No host change has been performed.

### Code-derived but untested steps (HIGH confidence)

1. Wait for device wake (controller wake detection or periodic polling of
   `GET /dev_info`).
2. Confirm device is reachable: `curl http://192.168.30.80/dev_info`.
3. Send rollback config:
   ```bash
   curl -X POST http://192.168.30.80/config \
     -H "Content-Type: application/json" \
     -d '{"data":[{"type":"SERVER_CREDENTIALS","host":"https://backend.iflo.com"}]}'
   ```
4. Verify: on next wake, device should contact `backend.iflo.com` (visible
   in gateway tcpdump as DNS query for `backend.iflo.com`).
5. Confirm restoration: `GET /dev_info` still returns normal values;
   vendor app shows device online.

### Physical recovery requiring separate approval

- **Factory reset** (`POST /dev_actions` with `{restoreToDefault: true}`)
  or `GET /resetdefault`: resets all SPIFFS config including WiFi. The device
  would return to SoftAP mode and require full re-provisioning through the
  vendor app. This is a last resort — it may reset the OTT and cartridge
  state.
- **Serial flash**: Not assessed. Requires physical access to UART pins on
  the PCB. Not a practical recovery path without separate hardware review.

## Blockers

**None identified that prevent proceeding to the approval checkpoint.**

The key risks are:
1. `POST /config` partial-payload behavior (UNTESTED).
2. Wake-window duration after a failed cloud connection (INFERRED).
3. Encoding behavior for the config payload (INFERRED safe for ASCII URLs).

All three can be observed during the controlled Phase 6 experiment with the
rollback procedure ready.

## Evidence classification

| Finding | Class |
|---|---|
| OTT not required by current emulator config | CONFIRMED |
| Device re-registers on unknown backend | INFERRED (firmware static analysis) |
| Idempotent registration | CONFIRMED (tested on deployed emulator) |
| HOST /config accepts host-only update | INFERRED (firmware + JavaScript analysis) |
| Host change does not affect WiFi | INFERRED (code separation of config types) |
| Rollback via same POST /config | INFERRED (same mechanism, reverse direction) |
| Local HTTP survives cloud failure | INFERRED (independent server, same WiFi) |
| Factory reset as last resort | CODE-DERIVED (endpoint exists, behavior untested) |

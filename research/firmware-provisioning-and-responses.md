# Firmware provisioning and response handling — iFLO 3.0.64 (Mission 008B)

Date: 2026-10-26. Static analysis only (Ghidra 12.2 headless, Xtensa, on
`artifacts/firmware/iflo-3.0.64.elf`; decompiled output in the session
scratchpad). No device contact. VAs are Ghidra addresses.

## New P0

**P0-3: the emulator's `/healthcheck` blocks pairing.** `Pairing_task`
(`0x40093300`) calls `SAPI_Server_alive` (`0x4009446c`) = `POST
/device-api/v2/healthcheck {"deviceId": …}` and loops until it gets **HTTP 200**.
After 3 failures it sets pairing status 6 and may abort. Only then does it call
`register`. The emulator's `healthcheck` route calls `registry.require()`, which
returns 422 `DEVICE_NOT_REGISTERED` for a device that is not yet registered. So
pairing never reaches `register`. Fix: healthcheck must return 200 `{}` for an
allowlisted device ID (body `deviceId` or the `x-device-id` header), whether or
not it is registered. CONFIRMED_STATIC.

## A. Reset modes

`FUN_40097e50(mode)` → `FUN_4009846c` → `FUN_400983bc(mode)` (config wipe), then
`Restart_device_task`.

| Key | mode 0 / 2 | mode 1 |
|---|---|---|
| `offline_mode`, `started_disp_cnt`, `bttl_vald`, `max_doses`, `dose_time`, `user_disp_locked`, plus `FUN_4009600c` / `FUN_40096044` (unidentified stores, likely bottle/schedule) | **wiped** | kept |
| `act-time-ap`, `registred`, `https-host-address`, `wifi-edit` (+ edit state), `float-en`, `demo_mode`, `last-dispense`, `last-connection`, `nam_mode`, `wifi-ssid` / `wifi-pass` | wiped | wiped |
| `device_type` | wiped only when type == 3 | same |

CONFIRMED_STATIC (`0x400983bc`). Mode 1 keeps cartridge validation and dose
counters (`bttl_vald`, `max_doses`, `started_disp_cnt`). Mode 0 wipes them, so
**expect cartridge re-activation** after a mode 0 reset (INFERRED: the dose count
derives from these keys).

| Trigger | Mode | Class |
|---|---|---|
| `POST /dev_actions {"restoreToDefault": true}` (`0x4009361c`) | **0** | CONFIRMED_STATIC |
| Reset button long press (`Reset_button_action_handler`, `0x4008d5cc`, event 2; ignored in test mode) | **0** | CONFIRMED_STATIC (hold duration UNKNOWN: input layer not traced) |
| Reset button short press (event 1 then release 0) | reboot only (`FUN_40097dd8(2,100)`) | CONFIRMED_STATIC |
| Pairing `register` → 422 `NOT_UNIQUE` (`0x40093300`) | **1** | CONFIRMED_STATIC |
| `update-device` error `INVALID_DEVICE_ID` (`0x40094c80`) | UNKNOWN (decompiler shows no argument; treat as 0) | CONFIRMED_STATIC that it resets |
| `GET /resetdefault` (web UI "factory settings") | UNKNOWN (handler not decompiled; INFERRED 0) | INFERRED |

Reset button guards: no reset while in test mode, during OTA (`FUN_40099cb8`), or
in wifi-edit mode with its timer busy. If wifi-edit mode is on, it is turned off
and the device reboots instead.

**User button warning:** long press (`User_button_action_handler`, `0x4008d4e0`,
event 2) on a registered or offline device can call `FUN_4008e344`, the same
function as `/dev_actions manualDispense`. **Do not use the user button during
the runbook.** Short press = display doses / go to sleep.

## B. Non-destructive host change

**None found.** `SERVER_CREDENTIALS` is applied only when not registered
(`0x40093a44`). Wifi-edit mode (entered after about 20 ticks of STA failure on a
registered device, `0x4009129c`; or via the button) changes SSID/password only,
and `TOKEN` is also rejected in that mode. The only paths that clear `registred`
are the resets in A, or a failed `register` during pairing (which already needs
an unregistered device). CONFIRMED_STATIC within the traced code.

Related (`0x40093090`, "PAIRING is not completed… RESTORING"): at boot, if
`registred == 0` but `wifi-ssid` is set, the firmware **sets `registred = 1`**.
So a pairing whose `register` failed still ends up "registered" against whatever
host was provisioned after the next reboot, and it syncs `update-device` there
without ever having registered. CONFIRMED_STATIC.

## C. After reset: SoftAP

| | Value | Class |
|---|---|---|
| Mode at boot | Wi-Fi init (`0x400910a4`): unregistered → AP (`FUN_400903ac(1)`); registered → STA; wifi-edit == 1 → AP + STA ("EDIT SSID") | CONFIRMED_STATIC |
| SSID | **`iFLO device`** | CONFIRMED_STATIC (`FUN_400900dc("iFLO device", "13106423")`) |
| Password | **`13106423`**, authmode 4 (WPA/WPA2-PSK) | CONFIRMED_STATIC |
| IP | `192.168.4.1` (ESP-IDF default; the app targets it) | INFERRED (high) |
| Handlers | Same httpd: `/config`, `/dev_info`, `/dev_actions`, `/scan_wifi`, web UI, `/ota`, `/resetdefault`, `/reboot` | INFERRED (same server) |
| AP lifetime | `ap_active_timer` countdown (`0x4009129c`) → `FUN_40090ccc(2)` at 0; length from `act-time-ap` UNKNOWN. Every local request reloads the sleep timer (Phase 8) | PARTIAL |
| Test-mode AP | `Test_wifi` / `12345678` (QC only) | CONFIRMED_STATIC |

## D. Provisioning and registration

**Payload** (the device's own provisioning page, embedded JS, CONFIRMED):

```json
{"data":[{"type":"TOKEN","data":"<ott>"},
         {"type":"SERVER_CREDENTIALS","host":"<https url>"},
         {"type":"WIFI_CONFIG","ssid":"<ssid>","pass":"<pass>"}]}
```

`POST http://192.168.4.1/config`, `Content-Type: application/json`. The page
optionally calls `POST /dev_actions {"deviceType": n}` first, only when a device
type URL parameter is present; it is not needed. Constraints: TOKEN `data`
non-empty, not `"null"`, at least 4 chars, stored in RAM only. Host `strlen ≥ 3`,
no format check. WIFI_CONFIG needs `ssid`; `pass` may be empty. Body ≤ 512 bytes.
The handler replies 200, then starts `Pairing_task` because the device is
unregistered.

**`Pairing_task` (`0x40093300`) sequence** (CONFIRMED_STATIC):

1. Start STA and stop AP (unless a flag says keep). Wait for Wi-Fi; join failure
   reasons 4–7 → pairing status 2/3/4/5.
2. **Healthcheck loop:** `POST /device-api/v2/healthcheck {"deviceId": id}`
   until **HTTP 200**. After more than 2 failures → status 6, may abort (P0-3).
3. Wait up to 30 s for OTT and a non-empty host → else status 0xc.
4. **Register** (up to 3 attempts), `0x40093f50`:
   `POST {host}/device-api/v2/register`, header **`x-device-ott: <TOKEN>`**,
   body **`{"deviceId": "<id>"}`**.
   - **200** (body ignored) → `registred = 1` persisted → wait for the flash
     write → status 0 → task ends. Normal syncs follow on the regular schedule.
   - **422** body `code`: `NOT_UNIQUE` → status 8 → **mode 1 reset** + restart.
     `NOT_FOUND` → result 5 (status 7). Missing `code`/`message` or any other
     code → result 7 (status 0xe), retry.
   - Other status → `registred = 0` persisted, result 2, retry.
   - Transport failure → `registred = 0`, result 3, retry.
   - Wi-Fi lost mid-request → result 6 → status 0xb, exit.
5. After 3 failed attempts the task exits with `registred = 0`. Per §B, the next
   boot sets `registred = 1` anyway, because Wi-Fi credentials were saved.

Clock: TLS during pairing uses the same stack as vendor pairing (which works).
The leaf `notBefore` is 2026-10-26, so a device clock running behind that would
fail (INFERRED low risk; the device NTP-syncs every wake).

## E. Response handling

All endpoints go through `FUN_400942c0`, one request each, waiting up to
150 × 100 ms (15 s).

**`update-device` (`0x40094c80`).** The HTTP status is **not** checked. The body
is parsed:

| Body | Effect | Absent |
|---|---|---|
| has `data` | always: `FUN_400984d4()`, `FUN_4009aa7c(0)` (connection bookkeeping) | — |
| `data.extPowerState` | if it differs from the device and device type == 1 → event 0x85/0x86 | nothing |
| `data.remoteDispense` with key `isActive` | **dispense** (`FUN_4008e388(nonce)`). Only the *presence* of `isActive` is checked, **not its value** | nothing |
| `data.isScheduleSynced` false | schedule-sync request flagged (`FUN_4009aef8`; get-schedule on a later sync) | nothing |
| `data.isScheduleSynced` true | conditional schedule housekeeping (`FUN_400964f4` / `FUN_4009afcc` / `FUN_4009af58`) | nothing |
| `data.isSettingsSynced` false | `FUN_400988bc` (settings/float reset) | nothing |
| `data.isUpToDate` == 1 | log only | log "NOT FOUND" only |
| `data.isUpToDate` not 1 | `FUN_40099c90`, then if `data.url.redirectLocation` → **OTA** (`FUN_40099ca0`) | — |
| no `data`, has `fields` + `code` + `message` | log; **`code == INVALID_DEVICE_ID` → reset** | if `fields` is absent, error bodies are ignored entirely |

**`register`:** see D. Only 200 succeeds. Only `NOT_UNIQUE` resets.

**`healthcheck`:** HTTP 200 → OK; anything else → failure (blocks pairing). Body
ignored.

**`get-fw` (`0x40094560`):** 200 → parse `actualFirmwareVersion` (log) and
`url.redirectLocation` → **OTA** if present. Non-200 → result 1, log only.

**`get-schedule` (`0x40094b00`):** 200 → `FUN_40097504` **writes the schedule**
(dispense later). 422 → flag handling. Other status (e.g. 501) → log only.
Requested only when the local schedule-sync flag is set (`0x40095300`).

**`get-bottle` (`0x400949bc`):** 200 → `FUN_40094750` applies the bottle config.
422 → applies body + clears flag. Other → log. Requested only when the bottle
flag is set.

**`send-events` (`0x40095300`):** 200 / 422 / other → log only.

**`create-qc-report` (`0x400942e8`):** QC/test path; response logged (not
traced further).

Error codes the firmware acts on: **`INVALID_DEVICE_ID`** (update-device → reset),
**`NOT_UNIQUE`** (register → mode 1 reset), `NOT_FOUND` (register → failure
result 5, no reset). No others found.

## Emulator requirements checklist

- [ ] **P0-3:** `healthcheck` → 200 `{}` for an allowlisted device that is not
      yet registered.
- [ ] `register` → **200** for the allowlisted ID and source (body may be `{}`);
      never 422 `NOT_UNIQUE`.
- [ ] Never emit `INVALID_DEVICE_ID` / `NOT_UNIQUE` (done in 008A). Optional
      defense in depth: omit `fields` from error envelopes, which makes the
      firmware ignore every error body.
- [ ] `update-device` → `{"data":{"isUpToDate":true}}` only. **Never** include
      `remoteDispense` (presence of `isActive` dispenses), `url`,
      `isSettingsSynced:false` or `isScheduleSynced:false`. Absent fields are no-ops.
- [ ] `get-fw` → never include `url`.
- [ ] `get-schedule` / `get-bottle` → stay non-200 (501). A 200 writes a
      schedule or bottle config.
- [ ] Device registered on the device but unknown to the DB (DB loss, or the §B
      boot "restore"): `update-device` should adopt the allowlisted ID (record
      it) or return a non-resetting error. It currently returns
      `DEVICE_NOT_REGISTERED`, which is harmless (logged), but telemetry is lost
      until it is fixed.
- [ ] Allow the device's source IP: after provisioning to the `OpenFLO` SSID the
      device should get its old lease `192.168.30.80` (same MAC; INFERRED). If
      the IP changes, nftables and the source allowlist fail closed.

## Runbook inputs

| Item | Value |
|---|---|
| Reset | `POST http://192.168.30.80/dev_actions` `{"restoreToDefault": true}` during a wake (mode 0: wipes cartridge state). Alternative: reset button long press (mode 0). There is no mode 1 path that an operator can trigger |
| SoftAP | SSID `iFLO device`, password `13106423` |
| Device IP in AP | `192.168.4.1` |
| Provision | see below |
| Expected after 200 | Device leaves AP, joins `OpenFLO` → `healthcheck` → `register` (with `x-device-ott: openflo-r1`) → done; later syncs: `update-device` |
| Do not touch | user button (long press can dispense) |

```bash
curl -sS -m 10 -X POST http://192.168.4.1/config \
  -H 'Content-Type: application/json' \
  -d '{"data":[{"type":"TOKEN","data":"openflo-r1"},{"type":"SERVER_CREDENTIALS","host":"https://openflo-backend.home.example.com"},{"type":"WIFI_CONFIG","ssid":"OpenFLO","pass":"<OpenFLO SSID password>"}]}'
```

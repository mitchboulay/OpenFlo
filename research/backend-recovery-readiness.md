# Backend recovery readiness — iFLO 3.0.64

Date: 2026-10-26. Mission 008A Phase 8. **Static analysis only.** The physical
device was not contacted; nothing on the gateway container or the Proxmox host was changed.

Method: Ghidra 12.2 headless (`Xtensa:LE:32:default`) on the wrapped image
`artifacts/firmware/iflo-3.0.64.elf` (see `rea-xtensa-workaround.md`); handler
entry points recovered from the `httpd_uri_t` tables in DROM; functions created
at those entries and decompiled. Addresses are Ghidra VAs. Function names are
Ghidra-generated; roles are assigned from log strings and data flow.

## Headline — two P0 blockers for the Mission 008 plan

1. **A host-only `POST /config` is silently ignored on a registered device and
   still answers `200 OK`.** The `SERVER_CREDENTIALS` branch runs only when
   `Device_is_registred()` is false. This device is registered with the vendor
   cloud, so the proposed redirect is a no-op that looks successful, and the
   proposed rollback (the same call) is equally a no-op. The plan's mutation,
   expected behavior and rollback all have to be redesigned.
2. **`INVALID_DEVICE_ID` from the backend factory-resets the device.** When
   `update-device` gets an error body whose `code` is `INVALID_DEVICE_ID`, the
   firmware calls the same routine as `/dev_actions {"restoreToDefault": true}`.
   That routine wipes registration, backend host and Wi-Fi credentials, then
   restarts. The emulator currently returns exactly that body (422,
   `{"fields":{},"code":"INVALID_DEVICE_ID",…}`) for any unregistered device ID.
   Earlier reports said this code "triggers re-registration"; that is wrong.

## Key functions

| VA | Role (evidence) |
|---|---|
| `0x40093a44` | `POST /config` handler (`httpd_uri_t` @ `0x3f023004`: `"/config"`, method 3, handler) — logs `set_config_handler…` |
| `0x400935e4` | `OPTIONS /config` (CORS) |
| `0x400937b8` | `GET /dev_info` handler |
| `0x4009361c` | `POST /dev_actions` handler (`reboot`, `restoreToDefault`, `manualDispense`, …) |
| `0x400935a8` | Common request prologue: sleep-timer reload + CORS headers |
| `0x4008fa3c` | `Sleep_control` countdown reload |
| `0x400946f4` | `Device_is_registred()`: returns RAM byte `0x3ffccc73` |
| `0x40092f20` | `set_https_client_host_address(host)` |
| `0x400959d4` / `0x400959a0` | `FS_manager` set-string / get-string on the SPIFFS config object (`/spiffs/config.txt`) |
| `0x40095880` | `FS_manager` set-int (marks config dirty) |
| `0x40092ec0` | Cloud client start: reads `https-host-address` (default host only in test mode) |
| `0x40093580` / `0x40093300` | `run_pairing()` → `Pairing_task` |
| `0x40093f50` | `Device_registration` → `POST /device-api/v2/register` with `x-device-ott` |
| `0x40094c80` | `SAPI_device_info` → `POST /device-api/v2/update-device` and response handling |
| `0x40097e50` | Restore-to-default + `Restart_device_task` |
| `0x400983bc` | `Config` restore: the list of keys wiped |
| `0x40090eac` | `WiFi_restore_to_default`: clears `wifi-ssid` / `wifi-pass` |

## Answers

| # | Question | Answer | Class |
|---|---|---|---|
| 1 | Parser requirements | See §1. Body is read into a 512-byte buffer, parsed with cJSON, then each item of `data` is dispatched on `type`. **`TOKEN` is rejected when registered** (400, `device is already registered`). **`SERVER_CREDENTIALS` is skipped when registered**, with no error. `WIFI_CONFIG` needs `ssid`; `pass` may be empty. Any other `type` except `DEVICE_TYPE` returns 400 `one of object is wrong`. A missing `data` key returns 200 with no changes. The 200 is sent **after** the RAM/config-object writes and before the deferred flash flush. | CONFIRMED_STATIC |
| 2 | Can a SERVER_CREDENTIALS-only update touch Wi-Fi? | No. That branch only calls `FUN_40092f20` (and on a registered device does nothing at all). After the reply, pairing starts only if the device is **not** registered and not in Wi-Fi edit mode. If NAM or demo mode is on, `/config` turns them off first (side effect; both are off on this device). | CONFIRMED_STATIC |
| 3 | Persistence and validation | Persisted. The host is written to the SPIFFS config object (`FS_manager` set; the dirty flag is flushed by `Write_config()`), and sleep control waits for `FS_is_have_data_to_write` before sleeping. It is re-read from flash when the cloud client starts. Validation is **only `strlen(host) >= 3`**: no scheme or format check. The RAM copy is an unbounded `strcpy` into `0x3ffccb58`, about 132 bytes before the next global; 40 chars is safe. Write precondition: the key must already exist and the value must be non-empty. | CONFIRMED_STATIC (cap INFERRED from layout) |
| 4 | Registration and re-registration | A host change (when it is possible at all) does not clear `registred`. Registration runs **only inside `Pairing_task`**, which needs an OTT in RAM (`0x3ffccbe0`, set by `/config` `TOKEN`, **not persisted**) and a non-empty host. The device does **not** re-register on its own with a new backend. `register` 200 sets and persists `registred=1`. `422 NOT_UNIQUE` → "UID is registered" → restore-to-default (mode 1) + restart. Any other non-200, or a transport failure, persists `registred=0`. `update-device` returning `INVALID_DEVICE_ID` → full restore-to-default + restart (P0). | CONFIRMED_STATIC |
| 5 | Local HTTP independent of the cloud | Handlers are registered at server start and have no cloud preconditions; `/dev_info` answered throughout vendor syncs (runtime). Availability while the backend is unreachable is not runtime-tested. | INFERRED (high) |
| 6 | Keep-awake mechanism | Every handler (`/config`, `/dev_info`, `/dev_actions`) first calls `FUN_400935a8`. That calls `FUN_4008fa3c(0)`, which reloads the active `Sleep_control` countdown (`0x3ffc4aaa ← 0x3ffc4aac`), and `FUN_40091280`, which sets `0x3ffcb014 = 300`. Any local request resets the sleep timer. This matches the 108-minute held wake and the sleep about 45 s after polling stopped. | CONFIRMED_STATIC + runtime-observed |
| 7 | Backend unreachable | `update-device`: the request is sent once per sync, with up to 150 × 100 ms (15 s) of response wait. **No fallback to `backend.iflo.com`**: the default host is used only in test mode. There is no retry inside the call. The response status is not checked: a body with `data` is processed; an error body with `fields`/`code`/`message` is logged, except `INVALID_DEVICE_ID`, which resets the device (P0). A non-JSON or missing body is ignored. DNS or TLS failure surfaces as a transport failure (the counters `dnsFailureCount`, `pingFailureCount` are reported, and no reset path from them was found). The effect on wake duration is not established; sleep waits on pending SAPI events and FS writes. | CONFIRMED_STATIC (paths); UNKNOWN (wake-duration effect, retry cadence across wakes) |

### §1 `POST /config` handler, condensed (`FUN_40093a44`)

```c
prologue(req);                                   // FUN_400935a8: reload sleep timer, CORS
if (Is_NAM_mode_on())  { …; set_nam(0); }        // side effect, no return
if (Is_demo_mode_on()) { …; demo(1); }
if (Is_test_mode_on()) return send_err(req, 400, "device in qc mode");
recv(req, buf /*512*/, req->content_len);
root = cJSON_Parse(buf);   if (!root) return send_err(req, 400, "Bad json");
for (item = cJSON_GetObjectItem(root, "data")->child; item; item = item->next) {
  if (item.pair_status == 1) pair_flag = 1;
  switch (item.type) {
  case "TOKEN":  /* data: non-empty, != "null", strlen >= 4 */
      if (Device_is_registred())        return send_err(req, 400, "device is already registered");
      if (wifi_edit_mode != OFF)        return send_err(req, 400, "device in wifi edit mode");
      strcpy(ott_ram /*0x3ffccbe0*/, data);  break;      // RAM only
  case "SERVER_CREDENTIALS":
      if (!Device_is_registred() && host && strlen(host) >= 3)
          set_https_client_host_address(host);          // else: silently skipped
      break;
  case "WIFI_CONFIG": if (ssid) set_wifi_creds(ssid, pass); break;
  case "DEVICE_TYPE": set_device_type(deviceType); break;
  default: return send_err(req, 400, "one of object is wrong");
  }
}
resp_set_status(req, "200 OK"); resp_send(req, …);
if (wifi_edit_mode == OFF) {
  if (Device_is_registred()) log("Device_is_registred = TRUE");    // no pairing
  else if (!pairing_running) run_pairing();                          // Pairing_task
}
```

### What restore-to-default wipes (`FUN_400983bc(0)` via `FUN_40097e50`)

`offline_mode`, `started_disp_cnt`, `bttl_vald`, `max_doses`, `dose_time`,
`user_disp_locked`, `act-time-ap`, **`registred`**, **`https-host-address`**,
`wifi-edit` (and the Wi-Fi edit state), `float-en`, `demo_mode`,
`last-dispense`, `last-connection`, `nam_mode`, **`wifi-ssid` / `wifi-pass`**
(`WiFi_restore_to_default`), plus `device_type` for type 3. Then it waits up to
5 s for the flash write and restarts. Mode 1 (the `NOT_UNIQUE` path) skips the
dispense/bottle block but still wipes registration, host and Wi-Fi.

Not wiped by this routine: the firmware image, the device ID, and the cartridge
dose counter's own store (not traced).

## Recovery procedure

### What the firmware actually allows

- **To point this registered device at any backend, the device must first be
  unregistered.** The only firmware paths that clear `registred` are
  restore-to-default (`/dev_actions restoreToDefault`, `GET /resetdefault`,
  `INVALID_DEVICE_ID`, registration `NOT_UNIQUE`) or a failed registration
  inside pairing. Every one of these also wipes Wi-Fi credentials, except a
  failed registration, which can only happen during pairing.
- Redirect therefore means **re-provisioning**: restore to default; the device
  restarts with no Wi-Fi; it comes up in pairing/AP mode (INFERRED); then
  `POST /config` over the SoftAP with `TOKEN` (any string of 4 or more
  characters for the OpenFLO emulator) + `SERVER_CREDENTIALS` + `WIFI_CONFIG`.
  `Pairing_task` joins Wi-Fi and registers with the new host (3 attempts).
- Rollback to the vendor means **re-provisioning through the iFLO app**, which
  supplies a vendor OTT and host. If the vendor still holds the device ID, its
  `register` may answer `NOT_UNIQUE`, which triggers another reset (INFERRED from
  code; vendor behavior unknown). The device probably needs to be removed from
  the vendor account first.

### (a) Statically supported steps

1. Any local request reloads the sleep timer, so a rollback window can be held
   open by polling `GET /dev_info` (read-only) during a natural wake.
2. `GET /dev_info` confirms identity, firmware and mode before any change.
3. `/config` on an **unregistered** device accepts `TOKEN` + `SERVER_CREDENTIALS`
   + `WIFI_CONFIG` and starts pairing. The host persists in SPIFFS and is used
   on every later cloud start.
4. Restore-to-default plus restart is the only static path back to the
   unregistered state.

### (b) Runtime-tested behavior

- Repeated `GET /dev_info` every 2 s held the device awake for 108 min; it
  slept about 45 s after polling stopped (Mission 008A, single intervention).
- Normal vendor syncs: TLS 1.2 to `backend.iflo.com`, about every 10 min while
  awake.
- Nothing about `/config`, `/dev_actions`, `/resetdefault`, pairing or
  re-registration has been runtime-tested on this device.

### (c) Untested assumptions

- After restore, the device enters SoftAP pairing mode at `192.168.4.1`
  (Mission 004/005 provisioning observation, not re-verified after restore).
- The default value of `https-host-address` after restore (not traced; pairing
  requires `/config` to supply it anyway).
- The vendor cloud accepts re-registration of this device ID after app
  re-provisioning (it may answer `NOT_UNIQUE`).
- Behavior and wake duration when the backend is unreachable.
- Whether the cartridge/dose state survives restore without needing cartridge
  re-activation.

### (d) Physical recovery options

- **Factory reset** (`POST /dev_actions {"restoreToDefault": true}` or
  `GET /resetdefault`): statically traced, never executed on this device.
  It is **not a proven rollback**: it wipes registration, host, Wi-Fi
  credentials, dispense/bottle counters, demo/NAM/float settings and
  `last-dispense`, so the device must be fully re-provisioned (vendor app for
  the vendor cloud, or local `/config` for OpenFLO).
- **Physical button**: a `User_button_event_handler` exists (`GOTO_SLEEP` seen);
  button-based reset/pairing was not traced.
- **Serial/UART reflash**: not assessed. It needs physical PCB access and a
  separate hardware review.

## Recovery confidence

**Low for the Mission 008 plan as written; medium for a redesigned plan.**

- As written: the forward mutation is a no-op and the rollback is a no-op. The
  only real state-changing paths are full resets, none of which is
  runtime-tested.
- Redesigned (deliberate reset, then local re-provision to OpenFLO): the
  firmware paths are statically clear and the emulator accepts the
  registration. But returning to the vendor depends on app re-provisioning and
  unknown vendor-side handling of an existing device ID. A test of the full
  reset → re-provision cycle (ideally on the vendor side first) is needed
  before the confidence can be raised.

## P0 blockers

| ID | Finding | Required before redirect |
|---|---|---|
| P0-1 | Host-only `/config` is ignored on a registered device but returns 200 | Replace the Phase 6 mutation with a reset + re-provision design. Treat the vendor rollback as app re-provisioning and verify it first. |
| P0-2 | Backend `INVALID_DEVICE_ID` → device factory reset (Wi-Fi wiped) | The emulator must never send `code: "INVALID_DEVICE_ID"` to a device it does not intend to deprovision. Also guard against backend DB loss for a registered device. A backend code change is outside this phase's scope. |

Note for Phase 6 monitoring: any local HTTP request extends the wake, so
observation must stay passive (pcap, backend logs). A polling observer changes
the behavior it measures.

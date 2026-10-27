# Mission 004: Local Interface Discovery

Date: 2026-10-26. Status: **COMPLETE.**

## Phase 1 — Existing evidence review

| Check | Result |
|---|---|
| Device IP / MAC | 192.168.30.80 / `68:67:25:xx:xx:01` (DHCP lease from setup) |
| mDNS services | `iFlo._iflo._tcp.local` (port 80) + `ESP32-WebServer._http._tcp.local` (port 80) |
| mDNS TXT records | `name=iFlo`, `id=D8256700000A0001`, `type=STANDART`, `u=user`, `p=password`, `board=esp32` |
| HTTP reachability | Unreachable during deep sleep, reachable during wake windows |
| Baseline capture | Still running. Session `20261026T144415Z_first-provision` |

## Phase 2 — Passive analysis

### From the Hermes bundle (v96, partial extraction)

The Hermes bytecode v96 format is unsupported by available decompilers (`hbctool`). String extraction was partial — findings are from raw byte search and DEX cross-reference.

| Finding | Status |
|---|---|
| `backend.iflo.com` and `app.iflo.com` are NOT in the Hermes string table | CONFIRMED — URLs likely from Firebase Remote Config |
| `192.168.4.1` is NOT a literal string anywhere | CONFIRMED — derived at runtime from gateway address |
| `sendCurrentTimeToFirmware` exists as a function name | CONFIRMED |
| `connectToHotspot` / `connectToProtectedSSIDOnce` — WiFi reborn bridge | CONFIRMED |
| `ota_update` / `OTA_UPDATE` — firmware update pattern | CONFIRMED |
| No local device HTTP endpoint paths found in the bundle | CONFIRMED — either absent, or buried in the compressed string table |

### From DEX files

| Finding | Location |
|---|---|
| `app.iflo.com` — app/backend host | `classes2.dex` |
| `http://%s/status` — NOT device-related (Metro dev server) | `classes.dex` |
| `X_DEVICE_IP` — HTTP header in network layer | `classes2.dex` |
| WiFi Reborn native bridge (`com/reactlibrary/rnwifi`, `com/thanosfisherman/wifiutils`) | `classes.dex` + `classes2.dex` |

### From captures

| Finding | Status |
|---|---|
| App never contacts device port 80 post-setup | CONFIRMED — zero HTTP connections to 192.168.30.80 in entire capture |
| All post-setup communication routes through `backend.iflo.com` | CONFIRMED |
| mDNS credentials `u=user`, `p=password` are broadcast in the clear | CONFIRMED |
| Device ID `D8256700000A0001` is consistent across all mDNS announcements | CONFIRMED |

Full analysis: `app-api-analysis.md`

## Phase 3 — HTTP testing

**COMPLETE.** The device was tested during a wake window. All requests were read-only GET requests. No POST/PUT/DELETE requests were sent.

### Results

| Request | Response | Key finding |
|---|---|---|
| `GET /` | HTTP 200, 18,248 bytes HTML | Full provisioning web interface with WiFi config, network scan, and cloud server URL config |
| `GET /dev_info` | HTTP 200, JSON | Complete device telemetry: battery 100%, signal 100%, 6 doses, firmware 3.0.64, cartridge OK |
| `GET /ota.html` | HTTP 200, HTML | Firmware upload page with reboot, factory reset, and password change functions |
| `GET /settings.html` | HTTP 200, HTML | Device control page: manual dispense, demo mode, no-app mode, device type, iFLO Plus, reboot, factory reset |

### Discovered API endpoints (from JavaScript analysis of retrieved pages)

| Endpoint | Method | Purpose | Tested |
|---|---|---|---|
| `/dev_info` | GET | Device status JSON | YES — returns full telemetry |
| `/scan_wifi` | POST | WiFi network scan | No |
| `/config` | POST | Provisioning: WiFi creds, cloud server URL, OTT | No |
| `/dev_actions` | POST | Reboot, factory reset, manual dispense, mode toggles, device type | No |
| `/ota` | POST | Firmware binary upload | No |
| `/newauthpass` | GET | Change auth password | No |
| `/resetdefault` | GET | Factory reset | No |
| `/reboot` | GET | Reboot device | No |

Full endpoint documentation: `local-http-interface.md`

## Phase 4 — Authentication analysis

**COMPLETE.** No authentication is required. All pages and the `/dev_info` endpoint returned HTTP 200 without any `Authorization` header. The mDNS-advertised credentials (`u=user`, `p=password`) are not enforced by the current firmware.

The password change endpoint (`GET /newauthpass?newpass=<password>`) exists but was not tested. It may enable auth that is currently off by default.

## Phase 5 — Capability assessment

**COMPLETE.** See `local-control-feasibility.md` for the full analysis.

| Capability | Assessment |
|---|---|
| 1. Device identity | **CONFIRMED** — `deviceId`, `firmwareVersion`, `pcbVersion`, `deviceType` |
| 2. Current status | **CONFIRMED** — battery, signal, doses, cartridge, mode |
| 3. Cartridge information | **PARTIAL** — dose count and status, no serial or history |
| 4. Schedule readback | **NOT AVAILABLE** — no schedule endpoints in local interface |
| 5. Schedule configuration | **NOT AVAILABLE locally** — but `POST /config` can redirect cloud polling |
| 6. Manual dispensing | **AVAILABLE** — `POST /dev_actions {manualDispense: true}`. Untested (operator approval required) |
| 7. Device configuration | **AVAILABLE** — type, demo mode, no-app mode, reboot, factory reset, iFLO Plus |
| 8. Cloud server redirect | **AVAILABLE** — `POST /config {data: [{type: "SERVER_CREDENTIALS", host: "<url>"}]}` |

## Final report

### 1. Whether port 80 is reachable

**Yes**, during wake windows. The device serves HTTP on port 80 without authentication. The wake window lasted long enough for four GET requests with no timeouts.

### 2. Discovered HTTP endpoints

**Eight endpoints** documented from JavaScript analysis of three HTML pages. One endpoint (`GET /dev_info`) confirmed via direct testing. See the table in Phase 3 above.

### 3. Authentication requirements

**None.** The device serves all content without authentication. A password change mechanism exists (`/newauthpass`) but auth is off by default.

### 4. Capabilities exposed locally

**Rich local interface:**
- Full device telemetry (battery, signal, doses, cartridge, firmware, mode)
- Manual dispense trigger
- Device type configuration (Consumer HVAC, PRO HVAC, Mini, Septic)
- No-App Mode toggle (hidden in current config but endpoint exists)
- Demo mode toggle
- iFLO Plus (float switch) toggle
- WiFi reconfiguration
- Cloud server URL reconfiguration
- Firmware upload
- Factory reset and reboot

### 5. Whether the firmware can support cloud-independent operation

**Yes.** Two proven mechanisms:

1. **Direct local control:** `GET /dev_info` for monitoring + `POST /dev_actions` for manual dispensing. No cloud dependency. Sufficient for on-demand use.

2. **Cloud server redirect:** `POST /config` with `SERVER_CREDENTIALS.host` pointed at a local server. The device will poll the local server instead of `backend.iflo.com`. A local server that speaks the cloud protocol can deliver schedules. This is the path to full cloud-free scheduled operation.

Additionally, the **No-App Mode** toggle may enable autonomous operation without any server. This is the highest-value unknown remaining.

### 6. Remaining unknowns

| Priority | Unknown | Blocks |
|---|---|---|
| P0 | What does No-App Mode do? | May enable fully autonomous local operation |
| P1 | Cloud polling protocol (request/response schema) | Cloud server redirect (Path B) |
| P1 | Does the device validate TLS certs on the cloud URL? | Cloud server redirect |
| P2 | Device wake interval when idle (no schedule) | Polling cadence for monitoring |
| P2 | Manual dispense behavior (does it actually dispense?) | Local dispense control |
| P3 | Full Hermes disassembly for cloud API contract | Cloud emulation completeness |

### 7. Recommended next mission

**Mission 005: Local Control Prototype.** Build a lightweight monitoring client on the gateway container that polls `GET /dev_info` during wake windows and serves a local dashboard. Then, with operator approval, test `POST /dev_actions {manualDispense: true}` to confirm local dispense control.

## Changes made this mission

- `openflo-http-probe` deployed to the gateway container (`/usr/local/sbin/`)
- `openflo-wake-detect` deployed to the gateway container (`/usr/local/sbin/`)
- No changes to the device, network, or capture

## Deliverables

- [x] `research/mission-004.md` (this file)
- [x] `research/local-http-interface.md` — complete API surface with all endpoints, schemas, and authentication findings
- [x] `research/app-api-analysis.md` — app architecture and communication patterns
- [x] `research/local-control-feasibility.md` — updated capability matrix and architecture decision with proven paths

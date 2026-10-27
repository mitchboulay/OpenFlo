# Mission 005: Prior Art Review and Architecture Decision

Date: 2026-10-26. Status: **COMPLETE.**

## Executive summary

A third-party ESPHome replacement firmware for the iFLO exists and works. It fully maps the hardware (ESP32-S2 SOLO, GPIO pinout, motor drivers, sensors, LEDs) and demonstrates complete local control including scheduling and Home Assistant integration. However, it kills battery life (2 days vs 12+ months) because it lacks deep sleep.

The original firmware's local HTTP interface — discovered in Mission 004 — is more capable than expected. It provides full telemetry, manual dispense, device configuration, and critically, the ability to redirect the cloud backend URL to a local server. Combined with the upstream hardware documentation, this validates that cloud-independent operation is achievable through multiple paths.

**Recommended architecture:** Preserve the original firmware. Use its local HTTP API for monitoring and manual control (Option A, ready now). Pursue cloud server redirect (Option B) for scheduled dispensing if No-App Mode doesn't resolve it. Fall back to ESPHome replacement (Option C) only if Options A and B prove insufficient.

## Phase 1 — Consolidated research

### Verified capability matrix

| Capability | Status | Evidence |
|---|---|---|
| Device identity | CONFIRMED | `GET /dev_info` tested: deviceId, firmwareVersion, pcbVersion, deviceType |
| Battery monitoring | CONFIRMED | `GET /dev_info` tested: battery=100 |
| WiFi signal | CONFIRMED | `GET /dev_info` tested: signal=100 |
| Cartridge status | CONFIRMED | `GET /dev_info` tested: doses=6, bottleStatus=OK |
| Device mode | CONFIRMED | `GET /dev_info` tested: deviceMode=Normal |
| External power detection | CONFIRMED | `GET /dev_info` tested: extPowerState=false |
| Float switch status | CONFIRMED | `GET /dev_info` tested: floodNow=false, floatEn=false |
| Manual dispense | CODE-DERIVED | `POST /dev_actions {manualDispense:true}` in settings.html JS, userDispenseVisible=true |
| Device type config | CODE-DERIVED | `POST /dev_actions {deviceType:N}` in settings.html JS |
| No-App Mode toggle | CODE-DERIVED | `POST /dev_actions {noAppMode:bool}` in settings.html JS, namVisible=false |
| Demo mode toggle | CODE-DERIVED | `POST /dev_actions {demoMode:bool}` in settings.html JS |
| iFLO Plus toggle | CODE-DERIVED | `POST /dev_actions {floatEn:bool}` in settings.html JS |
| Reboot | CODE-DERIVED | `POST /dev_actions {reboot:true}` and `GET /reboot` |
| Factory reset | CODE-DERIVED | `POST /dev_actions {restoreToDefault:true}` and `GET /resetdefault` |
| Cloud URL redirect | CODE-DERIVED | `POST /config` with SERVER_CREDENTIALS.host |
| WiFi reconfiguration | CODE-DERIVED | `POST /config` with WIFI_CONFIG |
| Firmware upload | CODE-DERIVED | `POST /ota` accepts .bin files up to 2MB |
| Schedule read/write | NOT AVAILABLE | No schedule endpoints exist in the local HTTP interface |
| Dispense history | NOT AVAILABLE | Only current dose count, no history |
| Cloud polling protocol | PARTIALLY KNOWN | TLS 1.2 to backend.iflo.com, short REST-style exchanges, payload encrypted |

### What has been directly tested vs inferred

**Directly tested (HTTP request sent, response received):**
- `GET /` — HTTP 200, 18,248 bytes HTML (WiFi provisioning page)
- `GET /dev_info` — HTTP 200, JSON with 17 fields
- `GET /ota.html` — HTTP 200, HTML (firmware page)
- `GET /settings.html` — HTTP 200, HTML (settings page)
- Authentication: none required (all pages returned 200 without auth)

**Code-derived (JavaScript analysis of retrieved pages, not tested via HTTP):**
- All POST endpoints (`/config`, `/dev_actions`, `/scan_wifi`, `/ota`)
- All action payloads (manual dispense, mode toggles, provisioning)
- URL parameter handling (ott, apiUrl, mode, deviceType)

**Inferred (from captures, not directly observed):**
- Cloud polling protocol structure (REST-style, short connections)
- Device wakes on internal timer
- Commands ride on poll responses

## Phase 2 — Upstream ESPHome review

See `upstream-esphome-review.md` for the complete 12-item analysis.

### Key discoveries

1. **MCU: ESP32-S2 SOLO, 4MB flash.** The mDNS `board=esp32` is a generic label. GPIO 39-42 used as outputs confirms S2 variant (plain ESP32 has those as input-only).

2. **Complete GPIO pinout** — motor control (GPIO 9/10), front button (GPIO 6), bottle switch (GPIO 13), battery ADC (GPIO 8), four status LEDs (GPIO 39-42), bootloader pads (GPIO 0), UART (GPIO 36/37).

3. **Motor driver: Mixic MX08H H-bridge.** Two drivers — U1 for dispense motor, U3 for side interface jack. Dispense sequence: forward 250ms → run N seconds (1s/oz) → reverse brake 500ms.

4. **Scheduling: local cron at noon daily.** Options: off, every 7/14/30 days, 1st of month, 1st+15th.

5. **No license file.** The repository has no LICENSE, COPYING, or similar file. All code must be treated as reference material only.

6. **Single commit, 2026-10-17.** Nine days old. One contributor. Two devices flashed successfully per the README.

## Phase 3 — Firmware security audit

See `firmware-security-audit.md` for the complete audit with 12 findings.

### Critical issues

1. **No deep sleep (Critical).** `power_save_mode: HIGH` is WiFi modem sleep only (~12 mA), not ESP32 deep sleep (~22 uA). Batteries last 2 days. The author hard-wired his devices to wall power.

2. **Hardcoded ESPHome API encryption key (Critical).** `key: "7As1Bj…(redacted; full key is public in demitryk1/SmartHome)"` is published in the public YAML. Anyone with the key can control any device running this firmware.

### High issues

3. **No motor timeout/watchdog.** If the dispense script hangs, the motor runs indefinitely.
4. **Script restart safety.** `mode: restart` on dispense_sequence could interrupt a running motor mid-cycle.
5. **OTA encryption placeholder.** `ota: encryption:` with no value may default to unauthenticated.
6. **WiFi fallback AP.** Creates an access point with known credentials when WiFi fails.

### Assessment

The upstream firmware is a working proof-of-concept, not production-ready software. It demonstrates that the hardware supports full local control but should not be flashed without addressing the identified issues — especially deep sleep and the hardcoded API key.

## Phase 4 — Original firmware cloud replacement feasibility

See `original-firmware-feasibility.md` for the complete analysis.

### Local HTTP API (Path A)

Full device telemetry is available via `GET /dev_info` during wake windows. Manual dispense is available via `POST /dev_actions`. No authentication required. No schedule endpoints exist.

**Verdict: Sufficient for monitoring and manual control. Insufficient for scheduled dispensing.**

### Cloud backend redirect (Path B)

`POST /config` accepts `SERVER_CREDENTIALS.host` — the standard provisioning mechanism for telling the device where to poll. A local HTTPS server at that URL could deliver schedule commands via the cloud polling protocol.

**Key unknowns:**
- TLS certificate validation behavior (blocks or permits self-signed certs)
- Cloud polling protocol (request/response format)
- Whether partial `POST /config` payloads work (just SERVER_CREDENTIALS without WIFI_CONFIG)

**Verdict: The mechanism is proven. The protocol is the unknown.**

### No-App Mode (Path A+)

The `noAppMode` toggle exists in the firmware but is hidden (`namVisible: false`) for our device (Consumer HVAC, type 0). It may enable autonomous operation without cloud dependency. Testing it is a low-risk, high-value experiment.

**Verdict: Highest-priority unknown. If it enables local scheduling, it may eliminate the need for Path B.**

## Phase 5 — Battery and power analysis

See `power-management-analysis.md` for the complete analysis.

| Architecture | Estimated battery life | Basis |
|---|---|---|
| Option A (stock firmware) | 12+ months | Vendor claim, consistent with deep sleep power budget |
| Option B (stock firmware + redirect) | 12+ months | Same firmware, same sleep behavior |
| Option C (ESPHome, no deep sleep) | ~2 days | Measured by upstream author |
| Option C (ESPHome, with deep sleep) | Weeks to months | Theoretical, requires engineering |

Battery life is the strongest argument for preserving the original firmware.

## Phase 6 — Architecture comparison

See `architecture-decision.md` for the complete scoring matrix and rationale.

| | Option A | Option B | Option C |
|---|---|---|---|
| **Score** | **43/55** | **39/55** | **30/55** |
| Strengths | Zero risk, zero effort, immediate value | Full independence, stock battery life | Complete control, HA native |
| Weaknesses | No scheduling | Protocol unknown, server dependency | Battery, hardware risk, maintenance |

**Primary: Option A now, Option B next.**
**Fallback: Option C if B is infeasible.**

## Phase 7 — Next experiments

See `mission-006-proposal.md` for six detailed experiment specifications.

Priority order:
1. Wake interval measurement (passive, no risk)
2. No-App Mode toggle (low risk, potentially eliminates need for cloud replacement)
3. Manual dispense test (confirms local control, requires operator)
4. TLS certificate validation (determines Path B viability)
5. Cloud protocol capture (extends TLS test if successful)
6. POST /config format testing (determines re-provisioning requirements)

## Top five unanswered questions

1. **What does No-App Mode do?** — If it enables local scheduling, it's the cleanest solution. If it's cosmetic, it changes nothing.

2. **Does the device validate TLS certificates?** — Determines whether a local cloud server can be trusted by the device without cert manipulation.

3. **What is the cloud polling protocol?** — The request/response format between the device and `backend.iflo.com`. Required for any cloud replacement.

4. **What is the idle wake interval?** — How often the device wakes when no schedule is configured. Determines monitoring polling cadence.

5. **Is our PCB (6.3.0) pin-compatible with the upstream mapping?** — Only matters for Option C, but critical if we go there.

## Deliverables

- [x] `research/mission-005.md` (this file)
- [x] `research/upstream-esphome-review.md`
- [x] `research/firmware-security-audit.md`
- [x] `research/hardware-compatibility.md`
- [x] `research/power-management-analysis.md`
- [x] `research/original-firmware-feasibility.md`
- [x] `research/architecture-decision.md`
- [x] `research/mission-006-proposal.md`

## Changes made this mission

- No changes to the device, network, or capture
- No firmware was flashed
- No configuration was modified
- Upstream repository cloned to scratchpad for analysis (not committed to the project)

# Architecture decision

Comparison of three candidate architectures for cloud-independent iFLO operation.

## Option A — Original firmware + local HTTP controller

Preserve the stock firmware (v3.0.64). Use the device's existing HTTP interface (`GET /dev_info`, `POST /dev_actions`) for monitoring and manual control. Accept that scheduling remains cloud-dependent unless No-App Mode resolves it.

**What it delivers:**
- Real-time device telemetry during wake windows
- Manual dispense trigger (untested but code-derived)
- Device configuration (type, modes, reboot, factory reset)
- Battery status, cartridge monitoring, connectivity

**What it does not deliver:**
- Schedule read/write
- Dispense history
- Time synchronization
- Cloud-independent scheduled dispensing (unless No-App Mode provides it)

## Option B — Original firmware + OpenFLO cloud replacement

Preserve the stock firmware. Use `POST /config` with `SERVER_CREDENTIALS.host` to redirect the device's cloud polling to a self-hosted HTTPS endpoint that emulates the necessary parts of `backend.iflo.com`.

**What it delivers:**
- Everything in Option A
- Scheduled dispensing via the device's own scheduler (fed by the local server)
- Cloud-independent operation
- Preserves the original firmware's power management

**What it does not deliver:**
- Cartridge QR validation (vendor database)
- Firmware updates (unless the local server serves them)

**What it requires:**
- Reverse-engineering the cloud polling protocol
- A TLS-terminating local HTTPS endpoint the device trusts
- Understanding the schedule delivery format

## Option C — Replacement firmware (ESPHome or custom ESP-IDF)

Replace the stock firmware with a community or custom build. The upstream demitryk1/SmartHome ESPHome YAML exists as a reference implementation.

**What it delivers:**
- Full local control (status, dispense, schedule, all configuration)
- Home Assistant integration via ESPHome native API
- No cloud dependency whatsoever
- Complete transparency (open source firmware)

**What it does not deliver:**
- Vendor warranty preservation
- Stock battery life (2 days vs 12+ months without deep sleep work)
- Guaranteed hardware compatibility (PCB revision risk)
- Cartridge QR validation

**What it requires:**
- Physical device disassembly
- USB-serial hardware and flashing
- Hardware pin verification for our PCB revision (6.3.0)
- Deep sleep implementation for battery viability
- Accepting the risk of bricking

## Scoring matrix

Scale: 1 (worst) to 5 (best). Evidence quality noted.

| Criterion | A | B | C | Notes |
|---|---|---|---|---|
| Cloud independence | 3 | 5 | 5 | A: monitoring only, no scheduling. B+C: full independence |
| Battery life | 5 | 5 | 1 | A+B: unchanged stock firmware. C: 2 days without deep sleep (measured by upstream author) |
| Installation difficulty | 5 | 3 | 1 | A: zero changes. B: re-provision + local server. C: disassembly + flashing |
| Risk of bricking | 5 | 4 | 2 | A: impossible. B: factory reset restores. C: flash failure risk |
| Hardware compatibility | 5 | 5 | 2 | A+B: stock firmware. C: GPIO mapping unverified for PCB 6.3.0 |
| Scheduling capabilities | 1 | 4 | 5 | A: none. B: via cloud protocol (unverified). C: full local scheduling |
| Reliability | 5 | 3 | 3 | A: stock firmware, proven. B: depends on local server uptime. C: unproven firmware |
| Security | 3 | 3 | 2 | A: no auth on local API. B: same + local server attack surface. C: hardcoded API key, fallback AP |
| Maintenance burden | 5 | 3 | 3 | A: nothing to maintain. B: local server + protocol tracking. C: firmware updates, HA integration |
| Home Assistant integration | 2 | 2 | 5 | A+B: custom integration needed (polling /dev_info). C: native ESPHome API |
| Nontechnical user suitability | 4 | 2 | 1 | A: web dashboard. B: requires server. C: requires hardware work + HA |
| **Total** | **43** | **39** | **30** | |

### Evidence quality notes

| Criterion | A | B | C |
|---|---|---|---|
| Cloud independence | Tested | Code-derived | Tested by upstream author |
| Battery life | Tested (stock behavior) | Inferred (same firmware) | Measured by upstream author |
| Scheduling | Tested (no endpoints exist) | Code-derived (mechanism exists, protocol unknown) | Tested by upstream author |
| Hardware compatibility | N/A (stock) | N/A (stock) | Upstream author's PCB only; our PCB 6.3.0 unverified |

Several Option B scores are provisional: if TLS validation blocks the cloud redirect, scheduling drops from 4 to 1. If the cloud protocol is too complex to emulate, reliability drops from 3 to 1. These unknowns are resolved by Mission 006 experiments.

## Recommended primary architecture

**Option A (original firmware + local HTTP controller) as the immediate foundation.**

Rationale:
- Zero risk, zero device modification
- Delivers useful monitoring immediately
- Manual dispense provides on-demand control
- Preserves all future options (B and C remain available as upgrades)

**Option B (cloud replacement) as the scheduled upgrade path.**

Rationale:
- Preserves stock battery life — the single most important operational characteristic
- Preserves stock firmware reliability
- The `POST /config` mechanism is the standard provisioning path, not a hack
- The cloud protocol is the only significant unknown, and it's discoverable

## Recommended fallback architecture

**Option C (ESPHome replacement) if Option B proves infeasible.**

Specifically, if:
- The device validates TLS certificates and won't trust a local server, AND
- No-App Mode doesn't provide local scheduling, AND
- The cloud protocol is too complex to emulate

Then ESPHome replacement is the proven fallback. The upstream implementation works. The battery life problem is solvable with deep sleep engineering. The hardware compatibility risk is mitigable by verifying our pinout before flashing.

## Architecture roadmap

```
Phase 1 (NOW)     Option A — local monitoring + manual dispense
                   Build controller on the gateway container, dashboard, wake detection
                   ↓
Phase 2 (NEXT)    Investigate No-App Mode + cloud redirect feasibility
                   Test noAppMode toggle, test TLS validation, capture protocol
                   ↓
Phase 3a (IF B)   Option B — local cloud replacement
                   Build minimal cloud emulator, re-provision device
                   ↓
Phase 3b (IF C)   Option C — ESPHome replacement
                   Verify hardware, implement deep sleep, flash
```

## Decision record

- Date: 2026-10-26
- Decision: Option A as primary, Option B as upgrade, Option C as fallback
- Rationale: Least-invasive path that preserves battery life and firmware reliability
- Revisit trigger: Mission 006 experiments resolve TLS and No-App Mode unknowns

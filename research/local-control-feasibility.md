# Local control feasibility

Based on Mission 003 captures, Mission 004 static analysis, and **direct HTTP testing** of the device's local interface on 2026-10-26.

## Capability matrix

| Capability | Assessment | Basis |
|---|---|---|
| 1. Device identity | **CONFIRMED** | `GET /dev_info` returns `deviceId`, `firmwareVersion`, `pcbVersion`, `deviceType` |
| 2. Current status | **CONFIRMED** | `GET /dev_info` returns `battery`, `signal`, `doses`, `bottleStatus`, `deviceMode`, `extPowerState` |
| 3. Cartridge information | **PARTIAL** | `doses` (remaining count) and `bottleStatus` (`OK`/`EMPTY`/`MISSING`/`UNCONFIRMED`) are in `/dev_info`. No dispensing history or cartridge serial |
| 4. Schedule readback | **NOT AVAILABLE** | No schedule endpoint exists in the local interface. Schedules are cloud-only |
| 5. Schedule configuration | **NOT AVAILABLE locally, but re-provisioning is possible** | `POST /config` accepts `SERVER_CREDENTIALS.host` — the device can be pointed at a local server that responds to its cloud polling with schedule commands |
| 6. Manual dispensing | **AVAILABLE** | `POST /dev_actions` with `{manualDispense: true}`. The `userDispenseVisible` field in `/dev_info` is `true`. **Operator approval required before testing** |
| 7. Device configuration | **AVAILABLE** | Device type, demo mode, no-app mode, iFLO Plus toggle, reboot, factory reset — all via `POST /dev_actions` |
| 8. Firmware update | **AVAILABLE** | `POST /ota` accepts `.bin` files up to 2 MB. **Do not use — firmware modification is out of scope** |
| 9. WiFi configuration | **AVAILABLE** | `POST /config` with `WIFI_CONFIG` changes the device's WiFi network |
| 10. Cloud server redirect | **AVAILABLE** | `POST /config` with `SERVER_CREDENTIALS.host` changes where the device polls |

## Architecture decision

### Path A: Local HTTP — status + manual dispense (READY NOW)

The local interface provides:
- Full device telemetry via `GET /dev_info` (battery, signal, doses, cartridge, firmware, mode)
- Manual dispense via `POST /dev_actions`
- Device configuration (type, modes, reboot)

What it cannot do:
- Read or set schedules
- View dispense history
- Sync time

**This is sufficient for a useful local monitoring dashboard and on-demand dispensing.** A lightweight polling client on the gateway container can track device status during wake windows and trigger manual dispenses.

### Path A+: No-App Mode (INVESTIGATE)

The `noAppMode` toggle in `/dev_actions` is the most intriguing unknown. The `namVisible` field is currently `false` for this device, meaning the UI hides it. Possible explanations:
- It's gated by device type (only certain models expose it)
- It's gated by firmware version
- It requires a specific provisioning state

If No-App Mode enables local scheduling, it may be the cleanest path to fully cloud-free operation. **This warrants a targeted investigation.**

### Path B: Cloud server redirect (PROVEN MECHANISM)

The `POST /config` endpoint accepts `SERVER_CREDENTIALS.host`, which is how the device learns where to poll. Re-provisioning with a local server URL would redirect the device's TLS polling from `backend.iflo.com` to a local endpoint.

Requirements for this path:
1. A local HTTPS server that speaks the device's polling protocol (reverse-engineered from captures)
2. A valid TLS certificate the device will trust (unknown — the device's cert validation behavior is untested)
3. The cloud API contract for schedule delivery and status reporting

Complexity: MEDIUM. The mechanism is proven (the device accepts it during normal provisioning), but the cloud protocol is partially unknown.

### Path C: DNS redirect (SUPERSEDED)

`POST /config` with `SERVER_CREDENTIALS.host` is strictly better than DNS redirect. The device can be told where to poll directly — no DNS manipulation needed.

### Path D: Firmware modification (OUT OF SCOPE)

Not pursued.

## Recommended path

**Phase 1: Path A — local monitoring + manual dispense.** Build a lightweight client that polls `GET /dev_info` during wake windows and exposes the data via a local dashboard. Add a manual dispense button (with operator confirmation).

**Phase 2: Path A+ investigation.** Determine what No-App Mode does. Try enabling it via `POST /dev_actions {noAppMode: true}` (even though `namVisible` is `false`, the endpoint may still accept it).

**Phase 3: Path B — local cloud replacement.** If schedules are needed and No-App Mode doesn't provide them, build a minimal cloud emulator and re-provision the device to poll it. Start by capturing and replaying the polling protocol.

## Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Re-provisioning bricks the device | LOW | `POST /config` is the normal provisioning path used by the app. Factory reset via `/resetdefault` or `POST /dev_actions` restores defaults |
| Device rejects local HTTPS cert | MEDIUM | Unknown cert validation behavior. Test with a self-signed cert first; if rejected, use a real cert from Let's Encrypt |
| No-App Mode does nothing useful | LOW | It exists in the firmware with a dedicated toggle — unlikely to be a no-op. But it may only disable cloud dependency without adding local scheduling |
| Device stops waking after re-provisioning | LOW | The device wakes on its internal schedule timer, independent of cloud reachability. It will poll even if the server is down |
| Manual dispense wastes a dose | NONE | Testing requires operator approval. A single test dose confirms the mechanism |

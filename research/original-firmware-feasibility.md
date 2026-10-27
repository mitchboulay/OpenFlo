# Original firmware cloud-replacement feasibility

Assessment of whether the stock iFLO firmware (v3.0.64) can support cloud-independent operation without firmware modification.

> **Status update (2026-10-26):** the stock v3.0.64 image has been acquired and
> verified (`artifacts/firmware/iflo-3.0.64.bin`, SHA-256 `3b1df98a…a40f2`).
> The TLS-validation and cloud-protocol unknowns below can now be resolved
> statically; see `research/firmware-3.0.64-acquisition.md`.

## A. Local HTTP API

### Available telemetry (TESTED)

`GET /dev_info` returns comprehensive device state:

| Field | Type | Example | Status |
|---|---|---|---|
| battery | int % | 100 | Tested |
| signal | int % | 100 | Tested |
| doses | int | 6 | Tested |
| bottleStatus | string | OK | Tested |
| firmwareVersion | string | 3.0.64 | Tested |
| deviceId | string | D8256700000A0001 | Tested |
| pcbVersion | string | 6.3.0 | Tested |
| deviceType | int | 0 | Tested |
| deviceMode | string | Normal | Tested |
| extPowerState | bool | false | Tested |
| floodNow | bool | false | Tested |
| floatEn | bool | false | Tested |
| wifiSSID | string | OpenFLO | Tested |
| isProVersion | bool | false | Tested |
| demoModeVisible | bool | false | Tested |
| namVisible | bool | false | Tested |
| userDispenseVisible | bool | true | Tested |

This provides monitoring for battery, connectivity, cartridge status, remaining doses, firmware version, and device configuration. It covers all status information a daily operator needs.

### Device wake-window constraints

The device sleeps with WiFi completely off between wakes. Observed wake behavior:

| Window | Duration | Trigger |
|---|---|---|
| 14:57:29–14:58:21 | ~52s | Post-firmware-update cloud poll |
| 15:01:42–15:04:45 | ~183s | Post-cartridge-activation cloud poll |

Between wakes: zero frames on the wire (no ARP, no DHCP renew). The device is unreachable. A local controller cannot communicate with the device on demand — it can only read status during the device's own wake windows.

The idle wake interval (no schedule configured) is unknown. With a schedule configured, the device presumably wakes at least once per scheduled interval.

**Implication:** A polling controller must either detect wakes passively (ARP/DHCP/mDNS monitoring) or accept that status updates arrive only when the device decides to wake.

### Manual dispense capability (CODE-DERIVED, NOT TESTED)

`POST /dev_actions` with `{manualDispense: true, reboot: false, restoreToDefault: false}` is defined in the settings.html JavaScript. The `userDispenseVisible` field in `/dev_info` is `true`, indicating the device supports this action.

**Not tested.** Triggering a dispense requires operator approval. The endpoint's behavior (error handling, response format, whether it dispenses immediately or on next wake) is unknown.

### Authentication behavior (TESTED)

No authentication is required. `GET /` and `GET /dev_info` both returned HTTP 200 without any `Authorization` header. The mDNS-advertised credentials (`u=user`, `p=password`) are not enforced.

A password change endpoint exists (`GET /newauthpass?newpass=<password>`) but was not tested.

### Missing scheduling functionality

**The local HTTP interface exposes no schedule endpoints.** There is no way to read or write the device's dispense schedule through the local API. Schedules are managed exclusively through the cloud:

- App sends schedule changes to `backend.iflo.com`
- Device polls `backend.iflo.com` and receives schedule updates
- Device stores the schedule locally and executes it independently

This is the primary gap that prevents Path A alone from achieving full cloud independence with scheduling.

### Polling reliability for sleeping devices

A local controller can reliably communicate with the device only during wake windows. Strategies:

1. **Passive wake detection.** Monitor the gateway for DHCP/ARP from the device's MAC. When detected, immediately poll `/dev_info`. Latency: 1–2 seconds from detection to response.

2. **Opportunistic polling.** Periodically attempt `GET /dev_info` with a short timeout (2s). Most attempts will fail (device sleeping). Inefficient but simple.

3. **mDNS monitoring.** The device announces its services on wake. An mDNS listener on the gateway can trigger API calls.

Strategy 1 (passive wake detection) is the most reliable and resource-efficient.

## B. Configurable cloud backend

### How the device stores the backend URL

The `POST /config` endpoint on the device's local HTTP server accepts a provisioning payload:

```json
{
  "data": [
    {"type": "TOKEN", "data": "<one-time-token>"},
    {"type": "SERVER_CREDENTIALS", "host": "<cloud-api-url>"},
    {"type": "WIFI_CONFIG", "ssid": "<ssid>", "pass": "<password>"}
  ]
}
```

The `SERVER_CREDENTIALS.host` field is how the device learns where to poll. During normal provisioning, the mobile app passes `apiUrl` (sourced from Firebase Remote Config, typically `https://backend.iflo.com`) as a query parameter to the provisioning web page, which then sends it via `POST /config`.

**Confirmed (static):** the value is used as a full base URL (`%s%s` in
`FUN_40092f50`) and the client validates the server with the ESP-IDF CA bundle.
A self-signed local server will fail; use a public CA-trusted host.

This mechanism is the **standard provisioning path** — not a debug feature, not a hidden API. Every iFLO device receives its cloud URL this way.

### Can the URL include a custom hostname, port, or scheme?

**Unknown.** The JavaScript sends the `apiUrl` string directly as the `host` value. Whether the firmware parses and validates it (scheme, hostname, port) or uses it as-is is untested. The field name is `host`, not `url`, which could mean:
- Just the hostname (`backend.iflo.com`)
- A full URL (`https://backend.iflo.com`)
- A host:port combination

The original provisioning flow passes whatever `apiUrl` the app provides. Testing what formats the firmware accepts would require sending a `POST /config`, which is restricted in this mission.

### Can it be changed without factory reset?

**Likely yes.** The provisioning page has a `mode` parameter with at least one known value: `change_creds` (for WiFi credential changes). The `POST /config` endpoint appears to be idempotent — it overwrites the stored configuration. A factory reset (`GET /resetdefault` or `POST /dev_actions {restoreToDefault: true}`) should restore the original defaults, but what the "original" cloud URL default is (hardcoded or from initial provisioning) is unknown.

### How to restore the original backend

Two known mechanisms:
1. `POST /config` with `SERVER_CREDENTIALS.host` set back to `https://backend.iflo.com` (or whatever the original URL was)
2. `GET /resetdefault` or `POST /dev_actions {restoreToDefault: true}` for a full factory reset

The factory reset path is the safer option — it's a known-working restoration mechanism.

### TLS certificate validation

**Unknown.** This is the highest-impact unknown for cloud replacement.

Evidence for and against validation:

| Factor | Suggests |
|---|---|
| No SNI in TLS ClientHello | Unusual — may indicate a simplified TLS stack that skips validation |
| TLS 1.2 with ~55 cipher suites | A full-featured TLS stack, possibly with validation enabled |
| ESP32 Arduino/IDF default | Depends on build configuration. Many ESP32 deployments skip validation for simplicity |
| The app has no cert pinning | Irrelevant — the device has its own TLS stack |

**Status update — CONFIRMED:** the stock image uses the ESP-IDF
`esp-x509-crt-bundle` CA bundle as `crt_bundle_attach` (`FUN_400abed4`), so
server-certificate validation is **enabled**. A self-signed local server will
fail; a CA-trusted host is required. See
`research/rea-firmware-analysis.md`.

The older black-box options below are retained for context:
- Point `SERVER_CREDENTIALS.host` at a local HTTPS server with a self-signed cert
- Observe whether the device completes the TLS handshake or aborts
- This is a reversible experiment (factory reset restores the original backend)

### Cloud polling protocol

**Partially known from captures:**

| Observation | Value |
|---|---|
| Protocol | HTTPS over TLS 1.2 |
| Server | 34.120.139.126 (`backend.iflo.com`) |
| Pattern | Short-lived connections, one TLS handshake each |
| Request size | ~1.3–1.7 KB per request |
| Response size | ~5.7–6.5 KB per response (excluding firmware download) |
| Connection lifetime | ~1s, no keep-alive |
| Direction | Device initiates all connections |
| Likely structure | REST-style HTTP/1.1 request-response |

**Unknown:**
- HTTP method (GET vs POST)
- URL paths
- Authentication tokens (device → server)
- Request/response JSON schemas
- How schedule commands are delivered (in poll response body)
- How firmware update availability is signaled

**Status update:** the stock image is now available. URL paths, HTTP methods and
JSON keys can be extracted from rodata and Xtensa disassembly, replacing the
TLS-metadata-only view below.

A local cloud replacement must understand and replicate this protocol. The protocol can be discovered by:
1. Decrypting a captured session (requires TLS MITM)
2. Hermes bundle disassembly (partially blocked by v96 format)
3. Setting up a local server and observing what the device sends

### Sleep behavior preservation

**The original firmware's sleep behavior is independent of the cloud endpoint.** The device wakes on its internal timer, polls whatever URL is configured, processes the response, and goes back to sleep. Changing the cloud URL should not affect sleep behavior — the firmware's power management is built into the firmware itself, not driven by the cloud server.

The risk is: if the local server responds incorrectly (e.g., returns an error that causes the device to retry immediately), wake duration could increase, wasting battery. A well-behaved local server that returns valid responses should preserve normal sleep behavior.

## C. No-App Mode

### Available evidence

The `/dev_info` response includes two fields related to No-App Mode:

```json
{
  "namVisible": false,
  "userDispenseVisible": true
}
```

The `settings.html` JavaScript contains:

```javascript
// No-App Mode toggle (hidden by default)
<div class="device_info_wrapper hidden" id="no-app-mode-control">
  <p class="mb-0 mr-2">No-App Mode</p>
  <label class="switch">
    <input type="checkbox" id="no_app_mode">
  </label>
</div>

// Show if namVisible is true
if (t) {  // t = namVisible from dev_info
  var y = document.getElementById("no-app-mode-control");
  y && y.classList.remove("hidden");
  e.noAppMode && (document.getElementById("no_app_mode").checked = true);
}
```

The toggle calls `POST /dev_actions` with `{noAppMode: <bool>}`.

### What the flag likely controls

The name "No-App Mode" suggests the device can operate without the mobile app. This could mean:
- The device uses a local schedule instead of cloud-delivered schedule
- The device uses a fixed default schedule
- The device dispenses on a timer without cloud confirmation
- The device ignores cloud connectivity failures

It does NOT necessarily mean:
- The device stops polling the cloud
- The device enables local scheduling via HTTP
- The device becomes fully autonomous

### Whether it affects scheduling

**Unknown.** If No-App Mode enables a fixed schedule (e.g., "dispense every 30 days"), it would partially solve the scheduling gap in Path A. If it merely suppresses "app not connected" warnings, it adds no value.

### Why the UI hides it for our device

`namVisible: false` for our device. Possible reasons:
- Device type gating: Consumer HVAC (type 0) may not support it; PRO HVAC (type 1) or other types may
- Firmware version gating: v3.0.64 may have the feature disabled
- Cloud configuration: the flag may be set server-side during provisioning
- Account tier: certain account features may be cloud-controlled

### What would be required to test it safely

1. Send `POST /dev_actions {noAppMode: true}` and observe the response
2. Read `GET /dev_info` to see if `noAppMode` appears in the response and what changes
3. Observe whether the device's behavior changes (wake pattern, cloud polling)
4. Revert with `POST /dev_actions {noAppMode: false}`

**Risk: Low.** The toggle is part of the production firmware UI. It's designed to be toggled by users through the settings page. The risk is that it changes cloud connectivity behavior in a way that's difficult to observe or revert — but factory reset always restores defaults.

**This test requires operator approval** because it modifies device configuration.

## Feasibility verdict

| Path | Feasibility | Evidence quality |
|---|---|---|
| A — Local HTTP monitoring + manual dispense | **Ready now** | Directly tested (GET /dev_info) + code-derived (POST /dev_actions) |
| A — Local HTTP scheduling | **Not possible** | No schedule endpoints exist in the local API |
| B — Cloud redirect for scheduling | **Mechanism proven; protocol recovered; TLS gate confirmed** | POST /config with SERVER_CREDENTIALS.host is confirmed to be a full base URL. The device API is `/device-api/v2/`; TLS validation uses the ESP-IDF CA bundle, so a CA-trusted host is required. See `research/rea-firmware-analysis.md`. |
| No-App Mode for autonomous operation | **Promising but unverified** | Code exists in the firmware, UI is hidden for our device |

**The original firmware can support partial cloud independence (monitoring + manual dispense) immediately. Full cloud independence (including scheduling) requires either cloud replacement (Path B) or No-App Mode investigation.**

# Cloud-replacement feasibility

Assessment based on evidence from Mission 003 (2026-10-26). No cloud emulation, firmware modification, DNS redirection, or certificate manipulation was performed. This document evaluates observed facts against four replacement paths.

## Summary

| Path | Viability | Complexity | Key unknown |
|---|---|---|---|
| A — Local HTTP API (port 80) | Most promising | Low | What endpoints exist and what they accept |
| B — DNS redirect to local server | Plausible | Medium | Whether the device validates the server certificate |
| C — Full cloud emulation | Possible but heavy | High | Complete API contract (request/response schemas) |
| D — Firmware modification | Last resort | Very high | Flash layout, OTA mechanism, code signing |

**Recommendation:** Path A first (zero risk, read-only exploration of the device's own local server), then Path B if A is insufficient.

## Path A — Local HTTP API (device port 80)

The device advertises two mDNS services after setup:

- `iFlo._iflo._tcp.local` on port 80
- `ESP32-WebServer._http._tcp.local` on port 80, TXT `board=esp32`

The TXT record also contains `u=` and `p=` keys (values redacted in our notes), which suggest built-in credentials for local access.

**What the evidence says:**
- The local server is real: mDNS announces it on every wake (CONFIRMED).
- The app never contacts it post-setup (CONFIRMED for this session) — all post-setup interaction routes through the cloud. But the server exists and listens.
- The ESP32 ecosystem commonly exposes a REST or simple HTTP control interface on port 80 for local configuration and triggering.
- The `_iflo._tcp` service type is vendor-specific and likely purpose-built for the iFLO's own control surface.

**What's unknown:**
- The endpoints, methods, and payload formats the local server accepts.
- Whether it can trigger a dispense, read schedule state, or accept configuration changes.
- Whether the `u=/p=` TXT values are functional credentials or metadata.
- Whether the local server is active only while the device is awake (Wi-Fi off between wakes suggests yes).

**Complexity:** Low. A GET to `http://192.168.30.80/` while the device is awake would reveal the server's interface with zero risk to the device or cloud relationship. No DNS, TLS, or firmware changes required. The device is on our lab network and we control routing.

**Risks:** Essentially none for read-only exploration. The device already exposes this server to any host on the same network. Sending unexpected POST/PUT payloads without understanding the API could trigger unintended behavior (e.g., a dispense), so write operations need operator approval.

## Path B — DNS redirect to local cloud server

The device resolves `backend.iflo.com` via the gateway's DNS and connects to 34.120.139.126:443. The gateway container controls DNS responses for the lab network.

**What the evidence says:**
- The device uses our gateway as its DNS resolver (CONFIRMED — dnsmasq logs show every query).
- The device does NOT send SNI in its TLS ClientHello (CONFIRMED). It connects by IP after resolution.
- The server certificate is `CN=backend.iflo.com`, issued by Google Trust Services (CONFIRMED).
- TLS 1.2 with `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` (CONFIRMED).
- The device's TLS client hello offers ~55 cipher suites including several families (CONFIRMED).

**What's unknown (critical):**
- **Whether the device validates the server certificate at all.** Many ESP32 deployments ship with certificate validation disabled or pinned to a specific CA. If validation is off, a self-signed cert on a local server would work. If it validates against a standard CA bundle, we'd need a trusted cert for `backend.iflo.com` (not obtainable without domain control). If it pins the server certificate or public key, this path is blocked entirely.
- The request and response format of the cloud API. Even with DNS redirect, we'd need to understand and replicate the API contract.

**Complexity:** Medium. The DNS redirect itself is trivial (one dnsmasq override). The TLS termination needs a certificate the device will accept (unknown difficulty). The API emulation needs the full request/response contract (obtainable from the Hermes bundle analysis and/or traffic observation once TLS is terminated).

**Risks:** If the device fails to connect to a redirected server, it simply retries on its next wake cycle. Restoring the original DNS response restores normal operation. No permanent change to the device. However, if the vendor's cloud expects regular check-ins, prolonged redirection could cause the account to show the device as offline.

## Path C — Full cloud emulation

Replace the vendor cloud entirely: DNS redirect + TLS termination + a server that speaks the full API contract, handling setup, firmware updates, scheduling, cartridge management, and dispense commands.

**What the evidence says:**
- The cloud serves at least: device registration, firmware distribution (1.39 MB OTA), schedule/cartridge state, and poll-response commands.
- The app also uses the cloud (`app.iflo.com` / `backend.iflo.com`) for user auth (Firebase), cartridge QR validation, and schedule configuration.
- The device polls; commands ride on poll responses (LIKELY).

**What's unknown:**
- The complete API surface (endpoints, auth tokens, payload schemas).
- How firmware versioning works and whether the device will accept a "no update available" response.
- The cartridge validation protocol (QR codes may encode vendor-specific data).
- Session/auth token lifecycle between the device and cloud.

**Complexity:** High. This is a full reimplementation of the vendor backend. The API contract can be partially recovered from the Hermes bundle (React Native app code) and from decrypted traffic (requires Path B to work first). Cartridge validation may be server-side and opaque.

**Risks:** A buggy emulation could leave the device in an inconsistent state (e.g., believing a firmware update is in progress). Cartridge tracking may be tied to the vendor's database, so locally-managed devices may lose cartridge-level features. This path makes sense only if Path A is too limited AND long-term cloud independence is the goal.

## Path D — Firmware modification

Replace or patch the ESP32 firmware to remove cloud dependency, add local control, or change behavior.

**What the evidence says:**
- The device is an ESP32 (CONFIRMED).
- A firmware image (~1.39 MB) was delivered over HTTPS during setup (LIKELY OTA).
- After the update the device rejoined with a new hostname (`iFlo` vs `espressif`) and a different TLS fingerprint, confirming the firmware was replaced (CONFIRMED behavioral change).
- No FCC ID was visible on the label, so regulatory filings (which sometimes contain internal photos and block diagrams) may not be publicly available.

**What's unknown:**
- The flash partition layout.
- Whether OTA images are signed (if signed, custom firmware won't be accepted via the normal OTA path).
- Whether the UART/JTAG debug interface is accessible or disabled.
- The complete firmware functionality (what the device does locally vs. what it delegates to the cloud).

**Complexity:** Very high. Requires physical access (likely UART), flash dumping, reverse engineering the binary, and building a replacement or patch. If OTA is unsigned, a modified image could potentially be delivered via Path B's DNS redirect, but this is speculative.

**Risks:** Bricking the device is possible if the flash is written incorrectly or a signed-image check fails partway through. This is irreversible without a working UART recovery path. Battery-powered operation means the device could lose power mid-flash. This path should only be considered after A and B are fully explored.

## Decision framework

```
START
  │
  ▼
  Probe local HTTP server (Path A)
  GET http://192.168.30.80/ while device is awake
  │
  ├─ Server responds with usable API ──► LOCAL CONTROL ACHIEVED
  │   (schedule, dispense, status)        No cloud needed for daily use
  │
  ├─ Server responds but limited ──► Combine A + B
  │   (status only, no commands)      Local status via A, commands via cloud redirect
  │
  └─ Server does not respond / ──► Test certificate validation (Path B prerequisite)
      insufficient for any use        Point DNS to a self-signed local server,
                                      observe whether device connects
                                      │
                                      ├─ Connects ──► Path B viable
                                      │               Build local cloud server
                                      │
                                      ├─ Rejects (cert error) ──► Path C/D territory
                                      │                           Evaluate effort vs value
                                      │
                                      └─ No connection attempt ──► Investigate further
                                          (device may check DNS    (firmware analysis
                                           or IP, not just cert)    needed)
```

## What Mission 004 should answer first

1. **What does the local HTTP server expose?** A single GET request while the device is awake. This is the highest-value, lowest-risk next step.
2. **Does the device validate TLS certificates?** Present a self-signed cert for `backend.iflo.com` via DNS override. Observation only: does the device complete the handshake or abort?
3. **What API paths does the app use?** Static analysis of the Hermes bundle to extract endpoint URLs, request builders, and response parsers.

These three questions determine which path is viable before any implementation begins.

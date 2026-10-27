# Mission 008C — First physical integration

Date: 2026-10-26, 20:04–20:46 UTC (active). Device `D8256700000A0001`, stock
firmware 3.0.64.

## 1. Outcome: **SUCCESS** (primary and secondary)

- **Primary: met.** The physical iFLO, on stock firmware, registered with
  OpenFLO using the pinned enrollment token and exchanged real telemetry and
  sync requests over TLS 1.2 without SNI.
- **Milestone 2 (battery-safe cycle):**
  - ✅ Returned to deep sleep: wake ended 20:41:41 after 310 s; zero device frames since.
  - ⏳ Natural wake + re-sync: **not yet observed.** Passive watch continues.

## 2. Timeline (UTC)

| Time | Action / observation |
|---|---|
| 20:04 | Preflight: all services active, safe mode, allowlists, `lab_device_tls` 0, passive controller running |
| 20:05 | DHCP reservation `68:67:25:00:00:01 → .80` added; pairing token generated (24 hex) and only its SHA-256 pinned (`d26b1c91…`); reset watcher armed |
| 20:11:13 | Operator battery power-cycle. Wake detected, DHCP `.80` |
| 20:11:16 | One `/dev_info` read: ID, firmware 3.0.64, mode Normal, battery 93, doses 5. `restoreToDefault` → **HTTP 200** |
| 20:11:21 | Device leaves VLAN 30 (wiped Wi-Fi) |
| 20:12–20:19 | **Mac CLI join failed:** `networksetup` reports success but doesn't switch (macOS 27) |
| 20:2x | Operator joins `iFLO device` manually: **5 joins fall back to home Wi-Fi within 2–4 s** (cause unknown; a clean profile didn't help) |
| 20:27 | Operator hears a prime-like motor sound at power-on. **Stop condition → paused.** Operator accepts boot prime (option 1), with the motor stop condition kept for after provisioning |
| ~20:35 | **Phone path:** phone joins `iFLO device`, opens the device's own `index.html?ott=<token>&apiUrl=https://openflo-backend.home.example.com&deviceType=0` (QR from the Mac), selects `OpenFLO`, enters the PSK. Page: "successful" |
| 20:36:31 | Device joins `OpenFLO`, DHCP `.80` |
| 20:36:33 | `healthcheck` → **200** |
| 20:36:34 | `register` (`x-device-ott`) → **200**, token hash matches the pin, source `.80` |
| 20:36:39 | `update-device` → **200** `{"data":{"isUpToDate":true}}`, full telemetry |
| 20:36:44/50 | `send-events` ×2 → 200 |
| 20:36:52–20:41:41 | `get-bottle` → 501, repeated every 4 s (6× per `update-device`, every ~28 s) |
| 20:41:41 | Device sleeps on its own (wake 310 s, 1,058 frames) |
| 20:42 | Backend fix deployed: `get-bottle` → 422 (see §5) |

## 3. Protocol evidence

- **DHCP / DNS:**
  - `DHCPACK 192.168.30.80` (reserved).
  - `query[A] openflo-backend.home.example.com → config … 192.168.30.1`.
  - Vendor host not queried after provisioning.
- **TLS:**
  - `lab_device_tls` counter went from 0 to 7+ (device MAC+IP → `192.168.30.1:443`).
  - Caddy served every request; no handshake errors in `caddy.log`.
  - The device's mbedTLS accepted the RSA-2048 leaf → YR1 → Root YR (X1 cross-signed) chain, without SNI. **This is the one thing that couldn't be pre-verified, and it is now runtime-verified.**
- **healthcheck → register → update-device:** as in the timeline. The register row has source `192.168.30.80`, `ott_sha256` prefix `d26b1c91…` (= pinned), `status accepted`. It is not `adopted`, so this was a clean token enrollment.
- **Telemetry (first `update-device`):**
  - `batteryLevel 88`, `firmwareVersion 3.0.64`, `connectionLevel 91`, `networkName OpenFLO`, `localIpAddress 192.168.30.80`.
  - `isWifiUpdated true`, `noAppMode 0`, `dnsFailureCount 0`, `pingFailureCount 0`, `deviceType 0`, RAM 27–37 %.
  - `bottleSensorStatus` redacted by the backend's sanitizer.
- **Events:**
  - Codes `9` (status 0), `5` (status 1) and `4` (status 0), device-timestamped 20:11:35–37, i.e. at the reset/boot, before any OpenFLO contact.
  - Meaning UNKNOWN. No evidence they are dispenses, but not proven.
- **Responses sent:** only `{"data":{"isUpToDate":true}}`, `{}` and error envelopes without `fields`. No `remoteDispense`, `url`, schedule or bottle config (verified in the protocol log).

Evidence: the gateway container `/root/backups/m008c/` (DB snapshot, Caddy access log, device
dnsmasq log, reset log) and pcaps `openflo_20261026T194514Z.pcap` /
`…T204536Z.pcap`. The Caddy log contains no `X-Device-Ott` (filtered); the DB
stores only the token hash.

## 4. Device state

| | Value | Class |
|---|---|---|
| Registration | Registered to OpenFLO (`registred=1` persisted per firmware, `register` 200) | CONFIRMED (backend) / STATIC (device) |
| Backend host | `https://openflo-backend.home.example.com` | CONFIRMED by traffic |
| Firmware | 3.0.64 (unchanged) | CONFIRMED |
| Battery | 93 % before reset (20:11, `/dev_info`) → **88 %** reported at 20:36:39 | CONFIRMED |
| Cartridge | Pre-reset: 5 doses, bottle OK. Post-reset: wiped (mode 0) [S]; the device requests bottle config; doses UNKNOWN (not read, to avoid extending wakes) | PARTIAL |
| Sleep | 310 s wake, then deep sleep from 20:41:41 | CONFIRMED |

## 5. Changes during execution

| Change | Why | Verified |
|---|---|---|
| `dhcp-host=68:67:25:00:00:01,192.168.30.80` (repo + the gateway container) | Firewall and allowlists key on `.80` | Device got `.80` |
| Enrollment token pin (`enroll-token.conf` drop-in on the gateway container; not in repo) | Only our token can enroll | register row hash = pin |
| **`get-bottle` safe mode: 501 → 422 `BOTTLE_NOT_AVAILABLE`** (no `data` / `fields`) | `FUN_400949bc`: 501 neither applies nor clears the bottle-sync flag, so the device re-requested every 4 s for ~5 min. 422 → `FUN_40094750` finds no `data` / `fields` and applies **nothing**, then `FUN_40091d6c` clears the RAM sync flag. No bottle config is sent | Decompiled; tests; **not yet seen on device** (the device slept before the deploy) |
| Mac provisioning abandoned for phone + device web UI | macOS 27 CLI can't switch Wi-Fi; manual joins bounce | Phone path worked first try |

## 6. Tests

Backend **40 passed**, locally and on the gateway container (the deploy script runs the suite
on target). Controller 4 passed (unchanged).

## 7. Outstanding issues

**Verified**
- Stock-firmware TLS against OpenFLO works without SNI.
- Pairing healthcheck → register → sync works.
- Token pin works.
- Safe-mode responses held.
- The device sleeps after its first OpenFLO session.

**Stop conditions tripped (documented; no rollback exists or was required)**
- **Battery 88 %** (< 90 %, −5 points). Likely contributors: three boot primes and
  repeated Wi-Fi sessions. A voltage dip from motor load can't be told apart
  without later readings [I]. Watch the next `update-device` value.
- **Retry pattern** (> 10 requests in one wake): `get-bottle` on 501. It was
  bounded (wake ended at 310 s, under the 10-min limit). Fixed server-side;
  awaiting confirmation.

**Unknowns**
- Milestone 2 items 2–3: natural wake interval and re-sync. Not yet observed.
- Whether the 422 fully stops `get-bottle` requests on the next wake, and whether the device then reaches "bottle valid" without the vendor (it may keep asking every sync).
- Event codes 9 / 5 / 4.
- Why macOS bounced off the SoftAP (the phone joined fine).
- Post-reset dose count and cartridge status.
- Prime-on-boot after a mode-0 reset is consistent with the cartridge wipe, but the trigger was not traced.

## 8. Next mission

1. **Passive watch (no polling):** next natural wake → `update-device` 200 and
   sleep ≤ 10 min (Milestone 2). Confirm `get-bottle` gets 422 once, then stops.
   Record battery.
2. **Bottle / cartridge model — RESOLVED STATIC (2026-10-26):** see
   [`bottle-authorization.md`](bottle-authorization.md). The device has no tag
   reader; GPIO13 is a seat switch. Authorization is the cloud's
   `dispenseLeft > 0` assertion. Decide whether OpenFLO should serve a real
   bottle record; this is the gate to feature parity (dose tracking, cartridge
   state).
3. **Event codes:** map `send-events` codes from the firmware (`FUN_` at the event
   builder) so the dashboard can show reset, boot, prime and dispense events.
4. **Schedule contract:** the get-schedule 200 schema is known [S]. Design an
   explicit, opt-in schedule feature with the same safety review.
5. **Controller dashboard:** show OpenFLO telemetry from the backend DB, not
   `/dev_info`.
6. **Runbook:** use phone provisioning via `index.html?ott=&apiUrl=&deviceType=`
   (QR), not Mac CLI.

## Addendum: secondary criterion and controls (2026-10-26, 21:00–22:47 UTC)

**Natural wake: SUCCESS.** The `fast-sync-time` 3900 s sent earlier was silently
rejected (no wake at ~21:57). The firmware substitutes its 48 h default when
`fast-sync-time` ≤ 2 × `shift-time`, so this unit's factory `shift-time` is
≥ 1950 s. OpenFLO then sent `shift-time: 60` before `fast-sync-time: 900` (same
`data.config`, delivered on a bottle-twist wake that ended 22:31:39). The device
woke on its own at **22:46:45** (+906 s) with no wake-cause events (bottle and
power wakes always open with SE 13/9) and re-synced: `update-device` → 200 twice.

**Also verified on hardware tonight:**
- Bottle authorization from OpenFLO (`get-bottle` 200, `bottleSensorStatus`
  `insertedUnauthorized` → `inserted`). Each re-seat logs eject + new bottle and
  is re-authorized. There is no bottle identity, so any seated container works.
- Remote dispense from the dashboard: queued, delivered once with a fresh nonce,
  executed, reported as `SE_REMOTE_DISPENSE_OK` (code 8), counted. Liquid out:
  **181 mL at 6.5 s ≈ 27.8 mL/s** (valve unit, vendor fluid).
- Actuator: valve (type 3, PCB 6.3.0, strap pins GPIO18/19/20 via `FUN_40097fdc`).
- Event names decoded from the firmware's SE_/EE_ tables.

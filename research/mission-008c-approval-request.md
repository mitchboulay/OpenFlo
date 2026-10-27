# Mission 008C — approval request: first physical integration

Date: 2026-10-26. Prepared by Mission 008B.

## Recommendation: **GO** (under the operator's stated risk acceptance)

Under the operator's decisions (the device is expendable; no guaranteed rollback;
factory reset is acceptable), there is no open P0 on the OpenFLO side. Every
firmware-side requirement found so far is met by the deployed backend and
infrastructure, and each one is covered by an automated test or a live check.

## Method

**Reset (`/dev_actions restoreToDefault`, mode 0) → SoftAP `iFLO device` →
`POST /config` (TOKEN + SERVER_CREDENTIALS + WIFI_CONFIG) → firmware pairing
registers with OpenFLO.** No non-destructive alternative exists [S]. Exact
steps: `migration-runbook.md`.

## Readiness

| Requirement (firmware, static) | State |
|---|---|
| TLS without SNI, TLS 1.2, `ECDHE-RSA-AES128-GCM-SHA256`, chain trusted by the extracted CA bundle | ✅ verified (008A) |
| VLAN 30 DNS → `192.168.30.1`; device-only firewall path | ✅ verified (008A) |
| Pairing calls `healthcheck` until 200 **before** `register` (P0-3) | ✅ fixed: 200 for the allowlisted device even when unregistered |
| `register` → 200 (body ignored), never `NOT_UNIQUE` | ✅ tested (full pairing sequence) |
| Never emit `INVALID_DEVICE_ID` / `NOT_UNIQUE` (factory reset) | ✅ impossible to construct; tested across every endpoint |
| Error bodies carry no `fields` (the firmware ignores them) | ✅ every envelope; tested |
| `update-device` → only `isUpToDate: true`. No `remoteDispense` (its presence dispenses), no `url`, no `isSettingsSynced` / `isScheduleSynced` | ✅ |
| `get-fw` without `url`; `get-schedule` / `get-bottle` stay 501 | ✅ |
| Backend DB loss / failed `register` (the device then self-marks registered and syncs anyway) | ✅ opt-in re-adoption (`OPENFLO_ADOPT_UNREGISTERED`, **off by default**, on in the lab unit only); bypasses the token pin, audited as `adopted`; tested on and off |
| Observer must not hold the device awake | ✅ controller is passive; zero device requests by default; replay-tested on the real capture |
| Enrollment pinned to an operator-chosen token | Ready (runbook step 1c) |

Tests: backend **40 passed**; controller **4 passed**. Both suites ran on
The gateway container as part of deployment (backend), or locally (controller).

## Success criteria

- **Milestone 1:** enrolled with the pinned token (not `adopted`) and at least one
  `update-device` 200 with telemetry.
- **Milestone 2:** returns to deep sleep (≤ 10 min wake, zero frames after it),
  then wakes **on its own** and re-syncs (`update-device` 200) and sleeps again.

The migration is complete only at Milestone 2. Milestone 1 alone is a partial
result. If no natural wake occurs within 4 h, Milestone 2 stays pending and the
passive watch continues (no polling, no power-cycle).

## Known limitation (not community-ready)

Re-adoption of an unregistered device is a single-device lab recovery aid. It
trusts identifiers (device ID + source IP), not the enrollment token. A
multi-device or community release needs a token-based recovery path, or none,
before this can ship. It is off by default in code; only the lab unit enables it.

## Authorization requested

Execute `migration-runbook.md` on device `D8256700000A0001`, specifically:

1. Add a DHCP reservation `68:67:25:00:00:01 → 192.168.30.80` and pin a
   pairing-token hash in the backend (the gateway container).
2. Power-cycle the device (batteries) to wake it.
3. Send `POST /dev_actions {"restoreToDefault": true}` (**factory reset**: wipes
   vendor registration, Wi-Fi and cartridge state; this is an irreversible
   separation from the vendor cloud).
4. Join the `iFLO device` SoftAP from the Mac and send the provisioning
   `POST /config` to OpenFLO.
5. Observe passively for up to 4 h, or 3 natural wakes, and continue the passive
   watch past 4 h if Milestone 2 is still pending.
6. Re-provision or re-reset as troubleshooting requires, within the runbook's
   stop conditions.

Not requested: firmware flashing, OTA, dispensing, schedules, bottle config, or
pressing the user button.

## Risks accepted by the operator

- Permanent loss of vendor registration and app control.
- Cartridge must be re-activated, or the dose state is lost (mode 0) [S].
- The AP-mode timeout is unknown [S partial]; a battery power-cycle should
  re-enter AP while unregistered [I].

## Residual technical risks

| Risk | Class | Mitigation |
|---|---|---|
| The device's mbedTLS rejects something OpenSSL accepted (only provable on the first real handshake) | UNKNOWN | Caddy logs the handshake error; the chain verifier is ready; re-provisioning stays possible only while unregistered, so diagnose before rebooting |
| SoftAP IP is not `192.168.4.1` | INFERRED (high) | Read the gateway address from the Mac's Wi-Fi details |
| `act-time-ap` expires before `/config` is sent | UNKNOWN | Have the payload ready; power-cycle to re-enter AP |
| The reset button's hold time is unknown (fallback only) | UNKNOWN | Prefer the `/dev_actions` reset |
| Identifiers (MAC / IP / ID) are not cryptographic | Accepted | Token pin, safe-mode responses |

**Awaiting explicit authorization to run Mission 008C.**

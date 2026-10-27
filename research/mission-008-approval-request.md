# Mission 008 Phase 6 — revised operator approval request (after Mission 008A)

Date: 2026-10-26, 20:00 UTC. Supersedes the Mission 008 request of the same date.

## Recommendation: **NO-GO** for the Phase 6 plan as written

The infrastructure is ready. The **device mutation is not.** Firmware analysis
(Phase 8, spot-checked against the decompiler output) shows that the proposed
host-only `POST /config` is silently ignored on a registered device. It returns
`200 OK` and changes nothing, and so does the proposed rollback, which is the
same call. There is no non-destructive way to point this device at OpenFLO. The
only path is a factory reset followed by re-provisioning, which is a different
experiment with different risks and needs its own approval.

A second P0 (the emulator could factory-reset the device) was found and **fixed**
in this mission.

## 1. Device

| | |
|---|---|
| Identity | `D8256700000A0001`, MAC `68:67:25:00:00:01`, `192.168.30.80`, PCB 6.3.0 |
| Firmware | 3.0.64, stock, unmodified |
| Current backend | `https://backend.iflo.com` (registered with the vendor) |
| Battery | **94 %** at 19:16:28 UTC (controller `GET /dev_info`; the last reading before the controller was stopped) |
| Cartridge | 5 doses, bottle OK |
| State at 19:30 | Asleep since 19:17:37 (pcap) |

## 2. Infrastructure (Mission 008A, done and verified)

| Item | Result |
|---|---|
| Dedicated TLS listener | Caddy on the gateway container, `192.168.30.1:443` only, RSA-2048 Let's Encrypt cert, chain to ISRG Root X1, `default_sni` |
| No-SNI TLS 1.2 | ✅ Using the device's own cipher order, the server negotiates `ECDHE-RSA-AES128-GCM-SHA256` (the suite the device uses with the vendor) |
| Firmware trust | ✅ Served chain is TRUSTED by the 148-root `esp_crt_bundle` extracted from the image (positive and negative controls pass) |
| DNS | ✅ VLAN 30 resolves `openflo-backend.home.example.com` → `192.168.30.1`; vendor, NTP and other names unchanged |
| Firewall | ✅ One INPUT rule: device MAC+IP → `192.168.30.1:443`. Every other lab → gateway / private / management path is still blocked (tested) |
| Enrollment | ✅ Device-ID allowlist + registration source allowlist + Caddy IP guard; each layer proven independently |
| Safe mode | ✅ `update-device` → `{"data":{"isUpToDate":true}}` only; `get-fw` has no URL; schedule/bottle 501 |
| Reset-code guard (P0-2 fix) | ✅ Backend can no longer emit `INVALID_DEVICE_ID` / `NOT_UNIQUE` (35 tests, deployed) |
| Backend DB | Fresh (synthetic test DB archived); device not pre-registered |

Diffs and test output: `emulator-infrastructure-remediation.md`,
`tls-compatibility-results.md`.

## 3. Baseline (reconciled)

- Natural wakes: **33–189 s** (n = 5). Gaps between them: 3–80 min. The
  steady-state idle interval is **unknown** (the device was provisioned today).
- The 87+-minute "extended wake" was **caused by our controller**, which polled
  `/dev_info` every 2 s (any local request reloads the firmware sleep timer;
  CONFIRMED statically and by intervention). The controller is now stopped and
  disabled. Battery went from 100 % to 94 % during that held wake.
- A capture coverage gap (15:53–16:44) is documented; the capture itself was not touched.

Details: `device-baseline.md`.

## 4. Why the planned mutation fails (P0-1)

`POST /config` handler `FUN_40093a44`:

```c
case "SERVER_CREDENTIALS":
    if (!Device_is_registred() && strlen(host) >= 3) set_https_client_host_address(host);
    break;            // registered: skipped, no error
...
resp_set_status(req, "200 OK");
```

On this registered device, the proposed redirect and the proposed rollback both
do nothing and report success. `TOKEN` returns 400 when the device is registered.
The firmware never re-registers on its own. Registration happens only in
`Pairing_task`, during provisioning of an unregistered device.

## 5. P0-2 (fixed)

`update-device` error body with `code == "INVALID_DEVICE_ID"` → `FUN_40097e50` →
restore-to-default (wipes `registred`, host, Wi-Fi credentials and
dispense/bottle state) → restart. The firmware reads error bodies regardless of
HTTP status. The emulator used to send exactly this for unregistered devices; it
now sends `DEVICE_NOT_REGISTERED`, and `ApiError` refuses to construct either
reset code.

## 6. What a redirect would actually require (for a future decision)

1. **Reset the device** (`/dev_actions restoreToDefault` or `GET /resetdefault`).
   This wipes Wi-Fi, registration and host, and may wipe cartridge validation and
   dose state (`bttl_vald`, `max_doses`, `started_disp_cnt`, `last-dispense`).
   Never executed on this device.
2. **Re-provision over the device's SoftAP**, from a laptop joined to the iFLO
   hotspot: `POST /config` with `TOKEN` + `SERVER_CREDENTIALS`
   (`https://openflo-backend.home.example.com`) + `WIFI_CONFIG` (`OpenFLO`).
   `Pairing_task` then joins Wi-Fi and calls `register` on OpenFLO.
3. **Rollback = vendor re-provisioning through the iFLO app.** Untested. The
   vendor may answer `NOT_UNIQUE` for an already-known device ID, which triggers
   another reset, so the device probably has to be removed from the vendor
   account first. This makes a return to the vendor cloud uncertain.

Recovery confidence: **low** for the plan as written; **medium** for the
redesigned plan, and only after the gaps below are closed.

## 7. Open items before any redirect can be proposed

| # | Item | Owner | Type |
|---|---|---|---|
| 1 | Decide whether leaving the vendor cloud is acceptable, possibly permanently (the vendor app stops working; return path uncertain) | **Operator** | Business decision |
| 2 | Trace which reset path is least destructive (the `NOT_UNIQUE` path uses mode 1, which keeps dispense/bottle state; check `GET /resetdefault` and `restoreToDefault`'s modes) and whether the cartridge needs re-activation afterwards | Static analysis | P0 for the redesign |
| 3 | Trace post-reset SoftAP behavior and the exact pairing `register` request, so the emulator answers it correctly (200; never `NOT_UNIQUE`) | Static analysis | P0 for the redesign |
| 4 | 24 h passive baseline (controller off) to get a steady-state idle interval | Passive | P1 |
| 5 | Make the controller read once per wake instead of polling continuously (it currently drains the battery) | Code | P1 |
| 6 | After registration, pin the presented OTT (`OPENFLO_ENROLL_TOKEN_SHA256`) | Config | P2 |
| 7 | After each cert renewal, re-run `tools/dump_crt_bundle.py verify` | Ops | P2 |

## 8. Stop conditions (for any future device experiment)

Defined in `device-baseline.md` §5: a wake longer than 10 min; 2 consecutive
wakes without a successful sync; more than 5 TLS handshakes or 10 API requests in
one wake; battery below 90 % or down 3 points or more; any dose decrease or
dispense event (immediate); firmware change (immediate stop); mode, NAM or Pro
flag change. Observation stays passive (no local polling).

## 9. Requested decision

**Not requested: approval to redirect.** Requested instead:

- Acknowledge the **NO-GO** for the host-only plan.
- Decide item 1: is a reset + re-provision experiment that may permanently
  remove the device from the vendor cloud acceptable in principle?
- If yes, authorize **Mission 008B (static analysis only):** close items 2–3,
  run the 24 h passive baseline, fix the controller, and produce a reset +
  re-provision runbook with its own GO/NO-GO.

No configuration or action request has been sent to the device. The only traffic
to it was the pre-existing Mission 006 controller's read-only `GET /dev_info`
polling, which Mission 008A stopped at 19:16:52 UTC.

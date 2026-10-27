# Mission 008A — Infrastructure Remediation & Integration Readiness

Date: 2026-10-26 (19:03–20:00 UTC). Status: **COMPLETE. Recommendation: NO-GO**
for the Phase 6 host-only redirect.

## 1. Executive summary

All three Mission 008 blockers are fixed without weakening VLAN isolation:

- A dedicated Caddy on the gateway container serves a cert the firmware trusts, without SNI, over TLS 1.2.
- VLAN 30 DNS resolves the backend hostname.
- One device-only firewall rule opens the path.

Enrollment is restricted to the test device and safe mode holds. Every claim was
tested from a synthetic VLAN 30 client.

Two P0s and one operational finding changed the outcome:

1. **P0-1 (open):** the firmware ignores a host-only `POST /config` on a
   registered device and still answers 200, so the planned redirect and
   rollback are both no-ops. Redirecting requires a factory reset plus SoftAP
   re-provisioning. That is a different, destructive experiment, and the return
   to the vendor cloud is uncertain.
2. **P0-2 (fixed):** an `update-device` error with `code: INVALID_DEVICE_ID`
   factory-resets the device, and the emulator sent exactly that for unknown
   devices. The code was renamed, made impossible to construct, regression-tested
   and deployed.
3. **Observer effect (fixed):** the Mission 006 controller's 2-second
   `/dev_info` polling held the device awake for 108 min (battery 100 → 94 %).
   The controller was stopped, and the device slept 45 s later.

## 2. Infrastructure changes (the gateway container only)

| Change | Rollback |
|---|---|
| Caddy v2.11.7 (the proxy container's build, sha256-verified) on `192.168.30.1:443`; unit, env (`0640 root:caddy`), logs | `systemctl disable --now caddy` |
| dnsmasq: `address=/openflo-backend.home.example.com/192.168.30.1` | restore `/root/backups/m008a-20261026T190314Z/openflo.conf`, restart dnsmasq |
| nftables: device MAC+IP → `:443` INPUT rule; repo file canonical again (`flush ruleset`) | `nft -f` the backup |
| Backend: device-ID and source allowlists, proxy-header trust from 127.0.0.1 only, reset-code guard; fresh DB | `backend-src.tgz` + DB in the backup dir |
| Controller (`openflo.service`) stopped and disabled | `systemctl enable --now openflo` (not advised until it reads once per wake) |

The proxy container was untouched. Its `:8080` dashboard route now returns 502 because the
controller is stopped. Full diffs: `emulator-infrastructure-remediation.md`.

## 3. Validation results

| Area | Result |
|---|---|
| DNS from VLAN 30 | OpenFLO → `192.168.30.1`; vendor, NTP, google unchanged; AAAA not forwarded |
| TLS, no SNI, TLS 1.2 | ✅ correct cert; with the device's cipher order → `ECDHE-RSA-AES128-GCM-SHA256`; TLS 1.1 refused |
| Firmware trust | ✅ served chain TRUSTED by the extracted 148-root `esp_crt_bundle` (ISRG Root X1); vendor chain TRUSTED; self-signed UNTRUSTED |
| HTTP path | ✅ healthz, register, update-device, get-fw, get-schedule, healthcheck through TLS → FastAPI → SQLite |
| Safe mode | ✅ only `isUpToDate: true`; no `remoteDispense`, no OTA URL |
| Isolation | ✅ non-device lab host blocked from `:443`, `:8099`, `:8080`, `:2019`, `:22`, the proxy container, Proxmox, UDM, Pi-hole, `192.168.1.30:8099` |
| Layered enforcement | ✅ nftables, Caddy guard and backend allowlists each block on their own |
| Secrets | ✅ OTT absent from DB and Caddy logs; Cloudflare token never printed or committed |

## 4. Security controls verified

MAC+IP firewall match; Caddy `remote_ip` guard; device-ID allowlist;
registration source allowlist with trusted-proxy attribution (forged XFF from the
LAN path rejected); `require_registration`; OTT stored as SHA-256 only; access-log
header filter; listener bound to the lab interface only, no `:80`, no HTTP/3;
admin API on localhost; no public ingress. Residual: identifiers are not
credentials. MAC/IP cloning on VLAN 30 is possible, but its impact is bounded by
safe mode.

## 5. Baseline corrections

- Battery: **94 % @ 19:16:28 UTC** (controller `/dev_info`). "100 % at last
  observation" was stale; 96 % (18:55) was correct when written. No lifetime
  extrapolated.
- Wake: natural 33–189 s. The 87+-min wake was induced by the controller. The
  10-minute stop threshold and the observed behavior are now consistent.
- Idle interval: unknown (gaps 3–80 min since provisioning). **Baseline
  insufficient** for an idle pattern.
- A capture gap (15:53:40–16:44:16) was found; the dnsmasq log covers it.
- Stop thresholds: one consistent, absolute set in `device-baseline.md` §5.

## 6. Recovery readiness

`backend-recovery-readiness.md`. The `/config` parser, persistence (SPIFFS
`config.txt`), keep-awake mechanism (every local handler reloads `Sleep_control`)
and failure paths were traced statically. There is no fallback to the vendor host
and no automatic re-registration. Factory reset is the only way back to the
unregistered state, and it wipes Wi-Fi and possibly cartridge state. It is not a
proven rollback. Confidence: **low** (plan as written), **medium** (redesign,
after the open items).

## 7. Remaining blockers

| ID | Blocker | Status |
|---|---|---|
| P0-1 | No non-destructive redirect; rollback to vendor uncertain | **Open**: needs an operator decision and a redesign |
| P0 (redesign) | Least-destructive reset path and cartridge-state survival not traced | Open (static analysis) |
| P0 (redesign) | Post-reset SoftAP + pairing `register` request not traced | Open (static analysis) |
| P1 | Steady-state idle baseline missing | Open (24 h passive) |
| P1 | Controller must stop polling continuously before re-enabling | Open (code) |
| P0-2 | Emulator could factory-reset the device | **Fixed** |

## 8. GO / NO-GO

**NO-GO** for the host-only redirect: it cannot work on this firmware. **NO-GO**
for any redirect until P0-1 has an approved redesign.

## 9. Next action requiring operator approval

Decide whether a **factory reset + local re-provision** experiment, which may
permanently remove the device from the vendor cloud, is acceptable in principle.
If yes, authorize **Mission 008B**: static analysis of the reset modes and
pairing flow, a 24 h passive baseline, a controller fix, and a reset/re-provision
runbook with its own GO/NO-GO. No device mutation until then.

## 10. Physical-device statement

No configuration, action, reset or provisioning request was sent to the device.
Firmware unmodified. No traffic was redirected. No dispense, schedule, OTA or
No-App Mode change was made. The baseline capture was never stopped or modified.
The only device-facing change was **stopping** the existing controller's
read-only polling, which reduced interaction with the device.

## 11. Deliverables

`mission-008a.md`, `emulator-infrastructure-remediation.md`,
`tls-compatibility-results.md`, `device-baseline.md`,
`device-enrollment-readiness.md`, `backend-recovery-readiness.md`,
`mission-008-approval-request.md`; code: `gateway/rootfs/etc/{caddy,systemd,…}`,
`scripts/gateway-apply.sh`, `scripts/deploy-backend.sh`,
`tools/dump_crt_bundle.py`, backend allowlists + reset-code guard (35 tests).

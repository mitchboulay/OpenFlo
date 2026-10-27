# Mission 008 — Physical Device Integration & Cloud Independence Validation

Date: 2026-10-26. Status: **PHASE 5 — AWAITING OPERATOR APPROVAL.**

## 1. Executive summary

Mission 008 validated that the iFLO device (firmware 3.0.64) can be redirected
to the self-hosted OpenFLO backend — but the current deployment architecture
has three network/TLS blockers that must be resolved first. A recommended fix
(dedicated Caddy on the gateway container) is designed and ready to implement pending approval.

**No device configuration was changed. No physical device mutations performed.**

## 2. Phase results

### Phase 1 — Emulator deployment validation: PASS

All eight `/device-api/v2/` endpoints tested on the deployed gateway container instance.
Safe-mode invariants confirmed: no `remoteDispense`, no OTA URL, `isUpToDate`
always true. 31 tests pass. Protocol logging active with credential redaction.
Network isolation verified — no public ingress, firewall limits access to
Caddy (192.168.1.10) only.

Deliverable: `research/emulator-deployment-validation.md`

### Phase 2 — TLS compatibility: BLOCKERS FOUND

**Certificate chain is compatible.** ISRG Root X2 → Let's Encrypt YE1 chain
should validate against the firmware's ESP-IDF v5.3.2 CA bundle (INFERRED,
high confidence from Mozilla NSS inclusion dates).

**Three blockers prevent the current Caddy-fronted deployment:**

1. **No-SNI TLS failure.** Device sends no SNI (CONFIRMED from pcap). Caddy on
   The proxy container cannot select a cert without SNI — handshake fails with `tlsv1 alert
   internal error`.

2. **DNS NXDOMAIN from VLAN 30.** The gateway container's dnsmasq forwards to public
   resolvers. `openflo-backend.home.example.com` is private (Pi-hole wildcard
   only). Device cannot resolve it.

3. **Firewall blocks device → Caddy.** nftables `lab_to_private_blocked` drops
   all VLAN 30 → private range traffic. Device cannot reach Caddy on
   192.168.1.10.

**Recommended fix:** Dedicated Caddy instance on the gateway container terminating TLS on
eth1 (192.168.30.1:443). Single vhost, no-SNI works naturally. dnsmasq
override for resolution. One firewall rule for eth1 → 443.

Deliverable: `research/tls-compatibility-results.md`

### Phase 3 — Device baseline behavior: PASS with caveats

Passive observation over ~4 hours post-provisioning:

- Battery: 96% (4% drop over 87 min continuous wake)
- Cloud poll interval: ~10 minutes during extended wake
- WiFi completely off during deep sleep (zero frames, CONFIRMED)
- TLS 1.2, no SNI, ECDHE-RSA-AES128-GCM-SHA256 (CONFIRMED)
- No dispense observed during monitoring window

**Caveat:** Device was provisioned today. True idle wake interval is UNKNOWN.
An 87+ minute extended wake (session 6) is likely post-provisioning behavior,
not steady-state. Stop thresholds calibrated against observed data.

Deliverable: `research/device-baseline.md`

### Phase 4 — Enrollment readiness: PASS

- Emulator accepts any OTT (enrollment tokens not configured).
- Re-registration on unknown backend handled by firmware automatically.
- `POST /config` with `SERVER_CREDENTIALS.host` changes backend URL (INFERRED).
- WiFi unaffected by host-only config change (INFERRED).
- Rollback: same `POST /config` with vendor URL.
- Local HTTP server (port 80) available during wake regardless of cloud status.

Deliverable: `research/device-enrollment-readiness.md`

### Phase 5 — Approval checkpoint: THIS DOCUMENT

Deliverable: `research/mission-008-approval-request.md`

## 3. Infrastructure changes needed

Before any device mutation, these gateway-container-only changes are required:

1. Install Caddy on the gateway container with Cloudflare DNS-01 cert issuance
2. Caddyfile: single vhost on `192.168.30.1:443` → `localhost:8099`
3. dnsmasq: `address=/openflo-backend.home.example.com/192.168.30.1`
4. nftables: allow eth1 → TCP 443 on 192.168.30.1
5. Verify: no-SNI TLS handshake from VLAN 30 succeeds end-to-end

## 4. Evidence classification

| Finding | Class |
|---|---|
| Emulator safe-mode invariants | CONFIRMED (tested) |
| Let's Encrypt cert chain | CONFIRMED (observed) |
| Firmware CA bundle includes ISRG Root X2 | INFERRED (high confidence) |
| No-SNI blocker on main Caddy | CONFIRMED (tested) |
| DNS blocker from VLAN 30 | CONFIRMED (tested) |
| Firewall blocker | CONFIRMED (tested) |
| Option A resolves all blockers | INFERRED (design) |
| POST /config accepts host-only payload | INFERRED (static analysis) |
| Rollback via POST /config | INFERRED (same mechanism) |
| Device re-registers automatically | INFERRED (static analysis) |
| Battery drain rate ~0.46%/10min active | CONFIRMED (observed) |
| Cloud poll interval ~10 min | CONFIRMED (observed) |
| WiFi off during deep sleep | CONFIRMED (pcap) |
| Idle wake interval | UNKNOWN |

## 5. Physical-device statement

**No physical-device configuration was changed during Phases 1-5.** No
firmware was flashed or modified; no traffic was redirected; no DNS or firewall
rules affecting the device were changed; no dispense, schedule, No-App Mode,
or OTA was triggered; the emulator was not deployed into the live device path.

## 6. What Phase 6 requires

Explicit operator approval to:

1. Install and configure Caddy on the gateway container (infrastructure change)
2. Add dnsmasq override on the gateway container (DNS change affecting VLAN 30)
3. Add nftables rule on the gateway container (firewall change)
4. Send `POST /config` to the physical device (device mutation)
5. Observe device behavior for up to 4 hours
6. Execute rollback if stop conditions are met

**Approval to deploy the emulator was NOT approval to redirect the device.**

See `research/mission-008-approval-request.md` for the full approval request.

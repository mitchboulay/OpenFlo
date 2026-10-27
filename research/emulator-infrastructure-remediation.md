# Emulator infrastructure remediation — Mission 008A Phases 1–6

Date: 2026-10-26 (19:03–19:26 UTC). Scope: the gateway container (`openflo-gw`) only, plus a
temporary test namespace on the Proxmox host. The shared Caddy on the proxy container was not
modified. The physical device received no traffic from this work.

## 1. Pre-change audit (Phase 1)

| Check | Result |
|---|---|
| OS / disk | Debian 12, 5.9 GB free of 8 GB |
| Services | `openflo-backend`, `openflo` (controller), `openflo-capture`, `dnsmasq`, `nftables`: all active |
| Capture | `20261026T144415Z_first-provision`, writing `openflo_20261026T184419Z.pcap` |
| Port 443 on 192.168.30.1 | Free (no Caddy installed) |
| Device lease | `68:67:25:00:00:01` → `192.168.30.80`, dynamic, unchanged since provisioning |
| Backups | `/root/backups/m008a-20261026T190314Z/` on the gateway container: nftables (file + live ruleset), dnsmasq conf, backend unit, backend DB + SQL dump, backend source tarball, `SHA256SUMS` |

Conflicts found: none for routing, DNS, DHCP or capture. Two pre-existing defects
were found and fixed in scope:

1. **nftables persistence drift.** `/etc/nftables.conf` was a raw `nft list
   ruleset` dump (written when the 8099 rule was persisted in Mission 008). It had
   no `flush ruleset`, no defines, no comments, and the repo source lacked the
   8099 rule. Now the repo file is canonical and live again.
2. **Unreproducible backend deploy.** The backend unit and code were deployed ad
   hoc (macOS `._*` files and xattrs were left on the gateway container). Now
   `scripts/deploy-backend.sh` and `gateway/rootfs/etc/systemd/system/openflo-backend.service`
   reproduce it.

`scripts/gateway-apply.sh` was **not** run wholesale: it overwrote
`/usr/local/sbin/openflo-capture` in place, which can corrupt the running bash
capture. It now installs that script by atomic rename. Changes were applied file by
file.

## 2. Dedicated TLS termination (Phase 2)

| Item | Value |
|---|---|
| Binary | Caddy v2.11.7, the same build as the proxy container's (sha256 `1cbede7f…dfa2d4`), copied, not rebuilt |
| Modules verified before start | `dns.providers.cloudflare`, `tls.issuance.acme`, `http.handlers.reverse_proxy`, `http.matchers.remote_ip`, `caddy.logging.encoders.filter.delete` |
| Config | `gateway/rootfs/etc/caddy/Caddyfile` (validated with `caddy validate` as the `caddy` user before start) |
| Bind | `192.168.30.1:443/tcp` only. No `:80`, no UDP/HTTP3 (`protocols h1`). Admin API on `127.0.0.1:2019` |
| Cert | RSA-2048, `CN=SAN=openflo-backend.home.example.com`, valid 2026-10-26 → 2027-01-24, DNS-01 via Cloudflare, auto-renew |
| Chain | leaf → `YR1` → `Root YR` (cross-signed by **ISRG Root X1**), pinned via `preferred_chains root_common_name "ISRG Root X1"` |
| No-SNI | `default_sni openflo-backend.home.example.com` |
| Device guard | `@not_device not remote_ip 192.168.30.80` → 403 |
| Logs | `/var/log/caddy/caddy.log` (JSON), `/var/log/caddy/openflo-access.log` (JSON, 50 MiB × 20 rolled, `X-Device-Ott` header deleted) |
| Secret | `/etc/caddy/.env`, `0640 root:caddy`, sourced from the Proxmox host's `/root/secrets/cloudflare_api_token`; never printed or committed |
| Unit | `gateway/rootfs/etc/systemd/system/caddy.service` (`User=caddy`, `ProtectSystem=full`, `CAP_NET_BIND_SERVICE`) |

**Why RSA, not Caddy's default ECDSA:** the device's observed suite
`TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` requires an RSA leaf. The RSA chain to
ISRG Root X1 also mirrors the RSA path the device already uses with the vendor
(GTS / GlobalSign).

## 3. VLAN 30 DNS (Phase 3)

```diff
-# No manufacturer-domain overrides here yet (Mission 003+).
+# No manufacturer-domain overrides: vendor names always resolve upstream.
@@
+# OpenFLO backend: the gateway container Caddy on this VLAN (Mission 008A). Device sends A queries only.
+address=/openflo-backend.home.example.com/192.168.30.1
```

`dnsmasq --test` passed before the restart (sub-second, during a quiet window
between device polls). DHCP config, upstreams (1.1.1.1 / 9.9.9.9) and logging
are unchanged.

## 4. Firewall (Phase 4)

Effective ruleset diff (handles and counters stripped), applied atomically with
`nft -f` after `nft -c -f`:

```diff
+	counter lab_device_tls {
+	}
-		iifname "eth0" ip saddr 192.168.1.10 tcp dport 8099 accept
-		iifname "eth0" ip saddr 192.168.1.10 tcp dport 8080 accept
+		iifname "eth1" ether saddr 68:67:25:00:00:01 ip saddr 192.168.30.80 ip daddr 192.168.30.1 tcp dport 443 counter name "lab_device_tls" accept
+		iifname "eth0" ip saddr 192.168.1.10 tcp dport { 8080, 8099 } accept
```

- INPUT chain only. FORWARD chain, NAT and `NO_GO` set unchanged.
- Placed before `lab_to_gw_blocked`. Every other eth1 → gateway packet is still dropped.
- Matched on MAC **and** IP. A lease change fails closed (the device can't
  connect, which is visible in the `lab_device_tls` counter).
- Persisted: `/etc/nftables.conf` is the repo file (`flush ruleset` header);
  `nftables.service` is enabled.
- Rollback: `nft -f` the backup file under `/root/backups/m008a-*/` (`flush ruleset` first).

## 5. Enrollment hardening (Phase 5)

| Control | Implementation |
|---|---|
| Device-ID allowlist | `OPENFLO_ALLOWED_DEVICE_IDS=D8256700000A0001` → others get 403 `DEVICE_NOT_ALLOWED` |
| Registration source allowlist | `OPENFLO_REGISTER_ALLOWED_SOURCES=192.168.30.80` → others get 403 `SOURCE_NOT_ALLOWED` |
| Source attribution | uvicorn `--proxy-headers --forwarded-allow-ips 127.0.0.1`: only the gateway container Caddy's `X-Forwarded-For` is trusted. Caddy discards client-supplied XFF |
| Unregistered devices | Unchanged: `require_registration=true` → 422 `INVALID_DEVICE_ID` on every other endpoint |
| Idempotency | Repeated `register` → 200, one device row |
| OTT handling | Unchanged: SHA-256 only, header excluded from protocol logs, deleted from Caddy access logs |
| Tests | 35 pass (new: device and source allowlist tests; reset-code guard tests after Phase 8), locally and on the gateway container |

Residual risk: device ID and source IP/MAC are identifiers, not credentials. A
host on VLAN 30 that clones the device's MAC and IP while the device sleeps could
enroll and post telemetry. The impact is bounded by safe mode: no response can
dispense, run OTA or change schedules. VLAN 30 has no other trusted hosts (a
Pixel 4a used for provisioning holds a lease). The original OTT is unknown, so
token enforcement is not possible yet. Once the device registers with OpenFLO,
`OPENFLO_ENROLL_TOKEN_SHA256` can pin the OTT hash it presented.

## 6. End-to-end validation (Phase 6)

Synthetic client: network namespace `ofl008a` on the Proxmox host, veth into
`vmbr0v30` (the Proxmox bridge for VLAN 30), `192.168.30.250/24` (outside the
DHCP pool), MAC `02:0f:10:08:0a:fa`. It went through the real eth1 firewall
path, and was removed afterwards (`vmbr0v30` is back to `veth145i1` + `eno1.30`).

### DNS (from VLAN 30)

| Query | Answer |
|---|---|
| `openflo-backend.home.example.com` A | `192.168.30.1` ✅ |
| `openflo-backend.home.example.com` AAAA | NOERROR / no data (not forwarded) ✅ |
| `backend.iflo.com` | `34.120.139.126` ✅ (unchanged) |
| `pool.ntp.org`, `google.com` | resolve upstream ✅ |
| other `*.home.example.com` | not overridden ✅ |

### Isolation (non-device client, final rules)

| Target | Result |
|---|---|
| gw `:443`, `:8099`, `:8080`, `:2019`, `:22` | BLOCKED ✅ |
| `192.168.1.30:8099`, the proxy container `:443`, Proxmox `:8006`, UDM `:443`, Pi-hole `:53` | BLOCKED ✅ |
| gw ping, DNS | allowed (unchanged policy) |
| Internet `1.1.1.1:443` | allowed (unchanged lab policy) |

### TLS (test client temporarily admitted; firmware-faithful handshake)

| Test | Result |
|---|---|
| No SNI, TLS 1.2, `ECDHE-RSA-AES128-GCM-SHA256` only | ✅ correct cert, verify 0, Extended Master Secret |
| No SNI, TLS 1.2, **device's 20 suites in device order** + device groups/sigalgs | ✅ server picks `ECDHE-RSA-AES128-GCM-SHA256`, X25519, RSA signature |
| With SNI | ✅ same cert |
| SAN | `DNS:openflo-backend.home.example.com` ✅ |
| TLS 1.1 | refused (alert 70) ✅ |
| Redirects | none. `GET /healthz` without SNI → `HTTP/1.1 200` JSON ✅ |
| **Served chain vs extracted firmware `esp_crt_bundle`** | ✅ TRUSTED: every link verified, top cert signed by bundle anchor ISRG Root X1 |

The firmware-trust check is `tools/dump_crt_bundle.py verify`. It decodes the
148-root bundle from the image (VA `0x3f039e20`) and replays the
`esp_crt_bundle` rule: the topmost served cert's issuer DER must equal a bundle
subject DER, and the signature must verify with that bundle key. Controls: the
vendor chain (fetched without SNI) is TRUSTED via GlobalSign Root CA; a
self-signed cert is UNTRUSTED.

### HTTP / backend (staged)

| Stage | Request | Result |
|---|---|---|
| A (backend final) | `register` from `.250` | 403 `SOURCE_NOT_ALLOWED` ✅ |
| A | `register` via the proxy container LAN path with forged `X-Forwarded-For: 192.168.30.80` | 403 `SOURCE_NOT_ALLOWED` ✅ |
| B (source temporarily allowed) | `register` stranger ID | 403 `DEVICE_NOT_ALLOWED` ✅ |
| B | `register` device ID ×2 | 200, 200, one device row ✅ |
| B | `update-device` stranger | 422 `INVALID_DEVICE_ID` ✅ |
| B | `update-device` device | 200 `{"data":{"isUpToDate":true}}`, nothing else ✅ |
| B | `get-fw` | 200 `{"actualFirmwareVersion":"3.0.64"}`, no `url` ✅ |
| B | `get-schedule` | 501 (disabled) ✅ |
| B | `healthcheck` | 200 `{}` ✅ |
| B | SQLite | device, registration (source `192.168.30.250`), telemetry, 40 protocol-log rows ✅ |
| B | OTT plaintext in DB / Caddy logs | absent ✅ |
| C (Caddy guard final, nft still admitting `.250`) | `GET /healthz` | **403 from Caddy** ✅ |
| D (nft final) | TCP `.250` → `:443` | **BLOCKED** ✅ |

Each layer was shown to block on its own. Temporary artifacts (nft rule
`m008a-temp-test-client`, Caddy `.250` entry, backend drop-in, netns/veth) were
all removed. The synthetic-test DB was moved to
`/root/backups/m008a-*/synthetic-test-db/`, and the backend now runs on a fresh,
empty DB, so Phase 6 evidence will contain only the device.

The capture recorded the synthetic traffic from `192.168.30.250` between
19:11:30 and 19:15:00 UTC. Filter it with `not host 192.168.30.250`.

## 7. Post-change state

| Service | State |
|---|---|
| `caddy` | active, enabled |
| `openflo-backend` | active (fresh DB, allowlists set) |
| `dnsmasq`, `nftables`, `openflo-capture` | active |
| `openflo` (controller) | **stopped + disabled** (see `device-baseline.md`: its polling held the device awake) |

The proxy container dashboard route to `:8080` now returns 502. Re-enable with
`systemctl enable --now openflo` only after the controller stops polling continuously.

## 8. Repo artifacts

| Path | Change |
|---|---|
| `gateway/rootfs/etc/caddy/Caddyfile` | new |
| `gateway/rootfs/etc/systemd/system/caddy.service` | new |
| `gateway/rootfs/etc/systemd/system/openflo-backend.service` | new (was untracked on the gateway container) |
| `gateway/rootfs/etc/nftables.conf` | device TLS rule, 8099 rule, defines |
| `gateway/rootfs/etc/dnsmasq.d/openflo.conf` | OpenFLO override |
| `scripts/gateway-apply.sh` | Caddy install/env/validate/enable; atomic capture-script install |
| `scripts/deploy-backend.sh` | new: test-on-target, swap, health-check |
| `tools/dump_crt_bundle.py` | new: list / verify against the firmware CA bundle |
| `backend/app/config.py`, `backend/app/services/registry.py`, `backend/tests/test_registration.py` | enrollment allowlists |
| `backend/deploy/`, `backend/Dockerfile` | removed (never deployed; stock Caddy image lacked DNS-01) |

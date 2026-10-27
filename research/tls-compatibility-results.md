# TLS compatibility results — iFLO 3.0.64 vs OpenFLO backend

Mission 008 (2026-10-26) found three blockers. Mission 008A (same day) resolved
them with a dedicated Caddy on the gateway container. Evidence: `emulator-infrastructure-remediation.md`.

## 1. Status

| Blocker (Mission 008) | Status (Mission 008A) |
|---|---|
| No-SNI handshake fails on the shared Caddy (the proxy container) | **RESOLVED.** Dedicated listener `192.168.30.1:443` with `default_sni`; no-SNI TLS 1.2 handshake succeeds (tested) |
| VLAN 30 cannot resolve the hostname | **RESOLVED.** dnsmasq `address=` override → `192.168.30.1` (tested from VLAN 30) |
| VLAN 30 cannot reach the proxy container | **RESOLVED without weakening isolation.** The device path stays on VLAN 30; one INPUT rule (device MAC+IP → `192.168.30.1:443`). The proxy container stays unreachable from the lab (tested) |

## 2. The device's TLS client (CONFIRMED from capture)

ClientHello from `192.168.30.80` to the vendor (`openflo_20261026T174419Z.pcap`):

| Property | Value |
|---|---|
| Version | TLS 1.2 (record and client version `0x0303`; no `supported_versions`) |
| SNI | **absent** (no extension 0) |
| ALPN | absent |
| Cipher suites | 59 offered, ECDHE-ECDSA first. Includes `0xc02f` ECDHE-RSA-AES128-GCM-SHA256 |
| Groups | x25519, secp256r1, secp384r1, secp521r1, brainpool |
| Signature algorithms | ECDSA and RSA PKCS#1 with SHA-512/384/256 (**no RSA-PSS**) |
| Other extensions | ec_point_formats, encrypt_then_mac, extended_master_secret, session_ticket |
| Vendor-negotiated suite | `0xc02f` (RSA leaf, Google Trust Services chain) |

## 3. Firmware trust anchors (CONFIRMED, upgraded from INFERRED)

`tools/dump_crt_bundle.py list artifacts/firmware/iflo-3.0.64.bin` decodes the
`esp_crt_bundle` at VA `0x3f039e20` (file offset `0x39e20`, 67,806 bytes):
**148 roots**, including:

| Root | Key |
|---|---|
| ISRG Root X1 | RSA-4096 |
| ISRG Root X2 | ECDSA P-384 |
| GTS Root R1–R4, GlobalSign Root CA / R3 / R6 / R46 / E46, ECC R4 / R5 | — |

`verify` mode replays the firmware rule: the topmost served certificate's issuer
DER must equal a bundle subject DER, and its signature must verify with that
bundle key. Controls: vendor chain → TRUSTED (via GlobalSign Root CA); self-signed
→ UNTRUSTED.

## 4. Served certificate (the gateway container listener)

| Property | Value |
|---|---|
| Leaf | `CN=openflo-backend.home.example.com`, SAN same, **RSA-2048** |
| Validity | 2026-10-26 → 2027-01-24 (Let's Encrypt, auto-renew via DNS-01) |
| Chain served (no SNI) | leaf → `Let's Encrypt YR1` → `ISRG Root YR` (cross-signed by ISRG Root X1): 3 certs |
| Firmware-bundle verification | **TRUSTED**: all links verified; top cert signed by bundle anchor ISRG Root X1 |

Why RSA: `0xc02f` (the observed suite) needs an RSA leaf. Caddy's default ECDSA
key would have produced the `YE1 → Root YE → ISRG Root X2` chain seen on the proxy container.
X2 is also in the bundle, but that path would only negotiate ECDSA suites the
device has never used with a server in our observations.

## 5. Handshake tests from VLAN 30 (synthetic client)

| Test | Result |
|---|---|
| No SNI, TLS 1.2, `0xc02f` only | ✅ handshake, correct cert, EMS yes |
| No SNI, TLS 1.2, device suite order + groups + sigalgs | ✅ server selects `ECDHE-RSA-AES128-GCM-SHA256`, X25519 |
| With SNI | ✅ same cert |
| TLS 1.1 | refused |
| HTTP over no-SNI TLS (`GET /healthz`, firmware headers) | `HTTP/1.1 200`, no redirect |

## 6. Remaining risks

| Risk | Class | Mitigation |
|---|---|---|
| mbedTLS on the device rejects something an OpenSSL client accepts (e.g., chain length, RSA-4096 verification of the cross-sign) | UNKNOWN until the first real handshake | The vendor chain is also 3 certs with an RSA-4096 cross-sign path; the first device handshake is the test. Stop condition: TLS failure → rollback |
| Renewal (~2026-12-25) gets a chain not ending at X1 (Let's Encrypt drops the X1 cross-sign or changes the default) | INFERRED low before 2027 | `preferred_chains` pins X1 while it's offered. Re-run `dump_crt_bundle.py verify` after each renewal |
| Let's Encrypt shortens lifetimes (45-day certs planned) | KNOWN | Caddy renews automatically; same check |
| Device clock invalid → cert "not yet valid" | INFERRED low | Device syncs `pool.ntp.org` every wake; cross-sign valid from 2026-05-13 |

## 7. Firmware hostname validation

Whether mbedTLS checks the hostname is still UNKNOWN (`esp_tls` normally sets the
hostname from the URL). It doesn't matter here: the cert's CN/SAN exactly match
the configured host.

# OpenFLO backend deployment design

Date: 2026-10-26. Status: **design only**. No DNS, firewall, certificate,
reverse-proxy, or production configuration was changed.

## 1. Firmware TLS constraints

| Constraint | Finding | Evidence |
|---|---|---|
| TLS stack | ESP-IDF mbedTLS, `esp-tls` | `0x3f0207e0`, `FUN_400c9674` |
| CA validation | enabled via `esp-x509-crt-bundle` | `FUN_400abed4` |
| CA bundle | 67,806 bytes at `0x3f039e20`; SHA-256 `1e22f155…3ccaee` | static extraction |
| Bundle roots | ISRG Root X1/X2, DigiCert, Amazon, GTS, GlobalSign, Sectigo, Entrust, etc. | bundle strings |
| TLS version | TLS 1.2 in captures; stack supports 1.2 | `research/cloud-endpoints.md` |
| SNI | **device sends no SNI** in captured ClientHello | `research/cloud-endpoints.md` |
| Hostname validation | exact `esp_tls` common-name / `skip_cert_common_name_check` config not fully mapped | UNKNOWN |
| HTTP timeout | 5000 ms | config `0x3ffc4bb8` |
| Redirects | `esp_http_client` supports redirects; OTA has its own redirect handling | `FUN_40099184` |

Let’s Encrypt is viable **in principle** because ISRG Root X1/X2 are in the
bundle. The missing SNI is the deployment risk: a shared-IP/SNI-routed proxy
may serve a default certificate instead of the expected host certificate.

## 2. Preferred deployment

- A hostname under a domain we control, e.g. `iflo-backend.example.com`.
- A publicly trusted certificate obtained with **DNS-01** (no public A record
  required).
- Private DNS (dnsmasq on the lab gateway) resolves the hostname to the private
  backend IP.
- Caddy terminates TLS and proxies to the FastAPI emulator.
- Only the lab VLAN can reach the backend; no public inbound port.
- Caddy uses `default_sni` so a no-SNI ClientHello receives this host’s
  certificate.
- Full certificate chain served (leaf + intermediate).
- TLS 1.2 enabled; TLS 1.3 optional (firmware uses 1.2).
- Certificate renewal via ACME DNS-01; Caddy reloads automatically.

### Caddy (deployed, Mission 008A)

The live config is `gateway/rootfs/etc/caddy/Caddyfile`, applied by
`scripts/gateway-apply.sh`: a dedicated Caddy on the gateway container bound to
`192.168.30.1:443`, RSA-2048 leaf, chain pinned to ISRG Root X1, `default_sni`,
HTTP/1.1 only, device-IP guard, OTT header stripped from access logs.
Validation evidence: `research/emulator-infrastructure-remediation.md`.

`default_sni` is important because the device does not send SNI. If the proxy
serves multiple names on one IP, the fallback certificate must be the one for
`OPENFLO_HOST`.

### DNS and firewall

- Public DNS: only the ACME TXT challenge record is needed for DNS-01.
- Private DNS: `address=/iflo-backend.example.com/<backend-ip>` in dnsmasq.
- Firewall: allow VLAN 30 → backend `:443`; deny WAN → backend; no public
  ingress.
- Do not change production DNS/firewall/Caddy without approval.

## 3. Certificate-chain compatibility

- Serve the full chain (leaf + intermediate), not just the leaf.
- Avoid cross-signed/legacy chains the bundle may not contain.
- Test with `openssl s_client -connect host:443 -servername host` **and**
  without `-servername` to simulate the device’s no-SNI behavior.
- Verify the served chain includes a root/intermediate path to ISRG Root X1 or
  another bundle root.
- Check certificate validity dates and hostname.

## 4. Backend availability behavior

- If the backend is down, the device’s HTTP request times out (5 s) and the
  sync attempt fails; it should return to sleep and retry on a later wake.
- Exact retry/backoff and battery impact are not runtime-tested. Mission 008
  must measure this.
- Do not return malformed JSON or 5xx storms; they can cause repeated error
  paths and reduce battery life (INFERRED).

## 5. Deployment

Systemd on the gateway container, not containers. `scripts/gateway-apply.sh` installs the
gateway configs (nftables, dnsmasq, Caddy, unit files);
`scripts/deploy-backend.sh` ships the emulator code, runs the test suite on the
target, then restarts the service. The Mission 007 Docker Compose template was
removed: it was never deployed and its stock Caddy image lacked the DNS-01 module.

## 6. Operational checks (future, approved)

1. From the lab VLAN: `curl --resolve host:443:<backend-ip> https://host/healthz`.
2. `openssl s_client` with and without SNI.
3. Confirm the chain and root.
4. Confirm the backend log sees `POST /device-api/v2/update-device` with
   `x-device-id` and no OTT.
5. Confirm no OTA/remote-dispense fields are returned.
6. Confirm firewall has no public ingress.

## 7. Risks

- **No SNI**: wrong cert on shared IP; mitigate with `default_sni`/dedicated IP.
- **Hostname validation**: if the firmware validates the common name, the cert
  must match `https-host-address` exactly.
- **Bundle version**: a future root rotation could remove a root; verify before
  renewal.
- **TLS 1.2 ciphers**: mbedTLS cipher set is narrower than a browser; test.
- **Certificate renewal**: DNS-01 automation must be reliable; monitor expiry.
- **Private DNS**: device must resolve the host from VLAN 30; no public A
  record is needed.

## 8. What was not done

No DNS record, certificate, Caddy route, firewall rule, or device setting was
created or modified. The templates are inert.

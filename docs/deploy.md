# Deploying OpenFLO

This guide covers what OpenFLO needs from your network, how to get a certificate devices accept, and how to run it day to day. The examples use `openflo.example.com` for your DNS name and `192.168.1.10` for your server's LAN address. Replace both with your own.

## Requirements

- A Linux host (x86-64 or ARM64) with Docker and Docker Compose v2.
- A DNS name you control, for example `openflo.example.com`.
- Port 443 on that host, reachable by your devices.
- A way to get a certificate: port 80 reachable from the internet (HTTP-01), a Cloudflare-hosted DNS zone (DNS-01), or your own certificate.

### What the devices need

iFLO firmware 3.0.64 is strict about TLS. The shipped `deploy/Caddyfile` already meets every one of these rules. Don't change its `tls` block.

- **No SNI.** The device doesn't say which site it wants. The server must answer with the OpenFLO certificate anyway (Caddy: `default_sni`).
- **TLS 1.2.** The device speaks TLS 1.2 only. Browsers still get TLS 1.3.
- **An RSA-2048 certificate.** The device can't use an ECDSA certificate.
- **A chain to ISRG Root X1.** The device trusts ISRG Root X1 (Let's Encrypt), but not ISRG Root X2.
- **Port 443.** It is the only port verified with the firmware. Other ports are **unverified**: they may work, but nobody has confirmed it yet, and the setup check warns about them.

A device saves the server address when you add it. Changing the address later means adding the device again, so pick the name before you add devices.

## Install

```bash
git clone https://github.com/mitchboulay/OpenFlo.git openflo && cd openflo
cp .env.example .env
```

Edit `.env`. At least set:

| Variable | Example | What it is |
|---|---|---|
| `OPENFLO_DOMAIN` | `openflo.example.com` | The name devices and browsers use. |
| `OPENFLO_ACME_EMAIL` | `you@example.com` | Let's Encrypt sends expiry notices here. |
| `OPENFLO_PUBLIC_URL` | `https://openflo.example.com` | Pre-fills the server address in setup. |

Then start it with the certificate option you picked (see [Certificates](#certificates)):

```bash
docker compose up -d                                          # HTTP-01 (port 80)
docker compose -f compose.yaml -f compose.dns01.yaml up -d    # or DNS-01 (Cloudflare)
```

The first start pulls the image. If no image is published for your version yet, Compose builds it from source instead, which takes a few minutes.

Watch Caddy get its certificate with `docker compose logs -f caddy`. Then open `https://openflo.example.com` and finish the setup wizard. Its last step checks the address the way a device connects.

The stack runs two containers. `caddy` is the only one with published ports. `openflo` is the app, on port 8099 inside the compose network only. Your data lives in the `openflo-data` volume.

## DNS

Create an `A` record (and `AAAA` if you use IPv6) for `openflo.example.com` that points to your public IP address. For LAN-only use, see [LAN-only](#lan-only-split-dns).

### Cloudflare: DNS only

If your DNS is on Cloudflare, set the record to **DNS only (grey cloud)**.

- Don't use the orange-cloud proxy.
- Don't use Cloudflare Tunnel.

Both end the TLS connection at Cloudflare's edge, which can't meet the device's rules (no SNI, TLS 1.2, RSA, ISRG Root X1). Devices would fail to connect. You can still use Cloudflare to host the zone and for DNS-01 certificates, or skip Cloudflare entirely.

### Dynamic IP addresses

OpenFLO doesn't manage dynamic DNS. If your public IP changes, keep the record current with your router's DDNS feature, your DNS provider's API, or a client such as `ddclient`. Keep the record DNS only.

## Port forwarding

On your router, forward TCP **443** to your server (for example `192.168.1.10:443`). Devices connect to it directly.

Forward TCP **80** only if you use HTTP-01 certificates. With DNS-01 or your own certificate, you don't need port 80 at all.

Check that nothing on the router itself already uses WAN port 443. See [Troubleshooting](#this-server-answered).

## Certificates

### HTTP-01 (default)

`docker compose up -d` uses `deploy/Caddyfile`. Caddy gets a Let's Encrypt certificate over port 80, so port 80 must be reachable from the internet.

### DNS-01 with Cloudflare

Use this when you can't open port 80, or for a name the internet can't reach (LAN-only).

1. Create a Cloudflare API token with **Zone → DNS → Edit** on your zone only.
2. Set it in `.env`: `CLOUDFLARE_API_TOKEN=<token>`.
3. Start with both compose files:

   ```bash
   docker compose -f compose.yaml -f compose.dns01.yaml up -d
   ```

This uses `deploy/Caddyfile.dns01` and the `openflo-caddy` image, which is Caddy plus the Cloudflare DNS plugin. Only port 443 needs forwarding. Use the same two `-f` flags for every later `docker compose` command, or set `COMPOSE_FILE=compose.yaml:compose.dns01.yaml` in `.env`.

### Bring your own certificate

1. In `deploy/Caddyfile`, replace the `tls { … }` block with the commented `tls /certs/fullchain.pem /certs/privkey.pem` line.
2. Mount your files into the `caddy` service in `compose.yaml`, for example `- ./certs:/certs:ro`.
3. Run `docker compose up -d`.

The key must be **RSA-2048**, and `fullchain.pem` must chain to **ISRG Root X1**. A certificate from another authority will probably fail the "Certificate is one iFLO trusts" check. You renew it yourself.

## LAN-only (split DNS)

You can run OpenFLO without exposing anything to the internet. Devices on your home network then work normally.

1. Use DNS-01, because Let's Encrypt can't reach a private server for HTTP-01.
2. Create a local DNS record that points `openflo.example.com` at your server's LAN address, `192.168.1.10`. Use your router's local DNS records or a Pi-hole "Local DNS" entry. Your devices and your server must both use that DNS server.
3. Don't forward any ports.
4. Optionally set `OPENFLO_PUBLIC=false` in `.env`. That is the only setting that allows `OPENFLO_AUTH_MODE=none`, but keeping a login is still wise.

The limit: a device at another site (a second home, an office) can't resolve or reach a LAN-only name. It needs the public setup above. If you might move to public access later, choose a real name you own now, so devices don't need adding again.

## Sign-in

Basic sign-in with one admin account is the default. OIDC, auth-proxy and API tokens are covered in [auth.md](auth.md).

## Trusted proxy network

The app trusts `X-Forwarded-For` only from the Caddy container. Compose pins the network to `172.30.0.0/24`, with Caddy at `172.30.0.2` and OpenFLO at `172.30.0.3`. If that subnet collides with one on your host, change the subnet and both fixed addresses in `compose.yaml` together, plus `FORWARDED_ALLOW_IPS`.

## Backups

`openflo backup` writes a consistent copy of the database to `/data/backups/openflo-<UTC time>.db` (mode 0600). It is safe while OpenFLO runs. It checks the copy with `PRAGMA integrity_check`, keeps the newest 14, and exits non-zero if anything fails.

- **Back up now:** `docker compose run --rm backup openflo backup`
- **List backups:** `docker compose run --rm backup ls -l /data/backups`
- **Back up daily:** at 02:30 in `TZ`. It is off by default. Turn it on with `docker compose --profile backup up -d`.

Backups live in the same `openflo-data` volume as the database. Copy them off the host too.

## Restore

A restore replaces the database, so OpenFLO must be stopped first. `openflo restore` refuses while it runs.

```bash
docker compose stop openflo
docker compose run --rm backup openflo restore openflo-20261027T023000123456Z.db
docker compose up -d
```

The restore refuses a damaged backup. Before it replaces the database, it saves the current one as `/data/backups/pre-restore-<UTC time>.db`. Retention never deletes these. Remove them yourself once you're happy with the restore.

## Upgrading

Pin the version in `.env` (`OPENFLO_VERSION=<tag>`), so every upgrade is deliberate.

```bash
docker compose run --rm backup openflo backup      # 1. back up
# 2. set OPENFLO_VERSION=<new tag> in .env
docker compose pull                                # 3. pull the new image
docker compose up -d                               # 4. start it; migrations run on start
curl -fsS https://openflo.example.com/healthz
```

**Rollback:** migrations only go forward, so an older version needs the database from before the upgrade.

```bash
docker compose stop openflo
# set OPENFLO_VERSION=<previous tag> in .env
docker compose pull
docker compose run --rm backup openflo restore <backup from step 1>
docker compose up -d
```

## Operations checks

- `docker compose exec openflo openflo check-address` runs the same address check as the setup wizard, from the command line.
- `scripts/check-cert-chain.sh` checks the saved server address the way a device connects (DNS, TLS 1.2 without SNI, RSA key, chain to ISRG Root X1, the device healthcheck, the port). It prints one line per check and exits non-zero if any fails. Run it after a certificate or DNS change.
- `scripts/bench-device-api.sh` benchmarks the device API on a throwaway copy of the running image, with an empty in-memory database. It never sees your data. It fails if p99 exceeds 500 ms.

The address check also runs every night. A failure shows in Settings and in `/healthz`.

## Troubleshooting

The setup wizard and **Settings → Server address** show one row per check. The headings below use the same titles. **Details** on a row shows the server's exact error.

### Found your server

**"Create a DNS record for … that points to this server."** The name doesn't resolve from the server. Create the record, or for LAN-only, check that the server uses the DNS server with your local record.

**"This name goes through Cloudflare."** The name resolves to Cloudflare's proxy. Set the record to **DNS only (grey cloud)** and remove any Cloudflare Tunnel for this name. "This server answered" shows "Not checked" until this is fixed.

### Devices can connect securely

The server refused a TLS 1.2 handshake without SNI. Usual causes:

- The `tls` block in the Caddyfile was changed. Restore `default_sni` and `protocols tls1.2 tls1.3`.
- Caddy has no certificate yet. Run `docker compose logs caddy` and look for errors from `tls.obtain`.
- Something other than OpenFLO's Caddy answers on 443 (another reverse proxy, or the router). See [This server answered](#this-server-answered).

### Certificate is one iFLO trusts

The chain doesn't end at ISRG Root X1, or the certificate served without SNI isn't for this name.

- With Let's Encrypt, keep `preferred_chains { root_common_name "ISRG Root X1" }` in the Caddyfile.
- With your own certificate, use one that chains to ISRG Root X1.
- Make sure `OPENFLO_DOMAIN` matches the server address exactly.

### Certificate type works

The certificate isn't RSA, or is smaller than 2048 bits. Keep `key_type rsa2048` in the Caddyfile. For your own certificate, issue it with an RSA-2048 key.

### This server answered

The device healthcheck at the address didn't reach this OpenFLO. Usual causes:

- **The router uses port 443 itself.** For example, UniFi's **Direct Remote Connection** (remote management) listens on WAN port 443 and takes priority over a 443 port forward. Turn that feature off, or move it to another port, then check again.
- The port forward points to the wrong host, or is missing.
- Another reverse proxy on the server owns port 443 and doesn't pass this name to OpenFLO's Caddy.
- Your router doesn't support NAT loopback (hairpin), so the server can't reach its own public address. Add a split-DNS record that points the name at the server's LAN address.
- **"This name goes through Cloudflare"** here means a Cloudflare response header was seen. Set the record to DNS only.

### Port

**"Port … hasn't been tested with iFLO yet."** Only port 443 is verified with the firmware. The warning doesn't block adding devices, but a device may fail to connect. Use 443 if you can.

### Adding a device is turned off

**Add device** needs a passing address check. The three certificate checks above ("Devices can connect securely", "Certificate is one iFLO trusts", "Certificate type works") must not fail. Fix them, then select **Check again** in Settings.

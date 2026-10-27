# Lab VLAN profile (optional)

This profile predates the Docker deployment; see the main README for the product.

It is the setup used to reverse engineer the iFLO dispenser: one Proxmox LXC container (the gateway container, `openflo-gw`) that sits between the dispenser and the rest of the network. You do not need it to run OpenFLO. It is specific to Proxmox and LXC and to one lab network, so treat it as a worked example, not an installer.

## What it adds

- **An isolated VLAN.** The dispenser joins its own Wi-Fi network on VLAN 30 (`192.168.30.0/24`). The container is its gateway, so every packet the dispenser sends passes through one place.
- **nftables admission.** Only known devices (matched by MAC and IP) may reach the TLS listener on `192.168.30.1:443`. Everything else is dropped. See `rootfs/etc/nftables.conf`.
- **A DHCP reservation.** dnsmasq hands out DHCP and DNS on the VLAN and pins the dispenser to a fixed address. See `rootfs/etc/dnsmasq.d/openflo.conf`.
- **A passive wake sniffer.** `controller/` runs tcpdump on the lab interface and groups the dispenser's frames into wake sessions. It sends the device zero requests by default, because any local request keeps the dispenser awake.
- **A device-path Caddy.** `rootfs/etc/caddy/Caddyfile` terminates TLS for the dispenser with settings its firmware needs: a default certificate for handshakes with no SNI, an RSA key, and TLS 1.2. It forwards to the backend on `127.0.0.1:8099`.
- **A capture tool.** `scripts/capture.sh` is installed in the container as `openflo-capture` for recording labelled packet captures.

## Prerequisites

- A Proxmox host reachable over SSH as `root@192.168.1.2` (override with `PVE_HOST`), and a free container ID (default `200`, override with `CTID`).
- A VLAN-aware bridge `vmbr0`, and a Wi-Fi network on VLAN 30 for the dispenser.
- On the Proxmox host: the Debian 12 LXC template, a Cloudflare API token at `/root/secrets/cloudflare_api_token` (for the DNS-01 certificate), and a reverse-proxy container (`PROXY_CTID`, default `201`) that has a Caddy build with `caddy-dns/cloudflare`.
- Edit the addresses, MAC and hostname in `rootfs/` to match your own network before applying. The values there are placeholders: `192.168.1.0/24` LAN, `192.168.30.0/24` lab VLAN, `openflo-backend.home.example.com`, device MAC `68:67:25:00:00:01`, WAN `203.0.113.10`.

## How to apply

Run these from your workstation, from the repository root:

```bash
deploy/examples/lab-vlan/scripts/gateway-apply.sh      # create/configure the container; safe to re-run
deploy/examples/lab-vlan/scripts/deploy-backend.sh     # ship backend/ to the container, test it there, restart it
deploy/examples/lab-vlan/scripts/deploy-controller.sh  # ship the wake sniffer
```

Since task I2.1 the device-path Caddy forwards to an OpenFLO host on the LAN (`192.168.1.40`), and the gateway container backend is only the rollback target. To change just the device path (Caddyfile, dnsmasq, nftables) without touching the backend unit, run `scripts/apply-device-path.sh` (`DRY_RUN=1` validates in the container and changes nothing).

**Warning:** `gateway-apply.sh` restarts dnsmasq and nftables in the container. The dispenser loses DHCP, DNS and its route for a moment, and open connections are dropped.

To remove it, stop and destroy the container (`pct stop $CTID && pct destroy $CTID`) and delete the lab VLAN's Wi-Fi network.

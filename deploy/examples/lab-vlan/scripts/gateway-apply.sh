#!/usr/bin/env bash
# Create (if missing) and configure openflo-gw on Proxmox. Run from your workstation. Idempotent:
# re-run after editing anything under deploy/examples/lab-vlan/{rootfs,scripts/capture.sh}.
set -euo pipefail
PVE=${PVE_HOST:-root@192.168.1.2}
CTID=${CTID:-200}
PROXY_CTID=${PROXY_CTID:-201}   # container whose Caddy build (with caddy-dns/cloudflare) is copied
LAN_IP=${LAN_IP:-192.168.1.30/24}
LAN_GW=${LAN_GW:-192.168.1.1}
CF_TOKEN_FILE=${CF_TOKEN_FILE:-/root/secrets/cloudflare_api_token}   # on the Proxmox host
LAB=$(cd "$(dirname "$0")/.." && pwd)

if ! ssh "$PVE" "pct status $CTID" >/dev/null 2>&1; then
  echo "creating CT $CTID"
  ssh "$PVE" "pct create $CTID local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
    --hostname openflo-gw --unprivileged 1 --onboot 1 --timezone UTC \
    --cores 1 --memory 512 --swap 256 --rootfs fastz:8 \
    --net0 name=eth0,bridge=vmbr0,ip=$LAN_IP,gw=$LAN_GW,firewall=0 \
    --net1 name=eth1,bridge=vmbr0,tag=30,ip=192.168.30.1/24,firewall=0 \
    --nameserver '1.1.1.1 9.9.9.9' --searchdomain lab.openflo \
    --description 'OpenFLO lab gateway: VLAN 30 DHCP/DNS/NAT + capture. Source: deploy/examples/lab-vlan'"
  ssh "$PVE" "pct start $CTID"; sleep 5
fi

x() { ssh "$PVE" "pct exec $CTID -- $*"; }

x "bash -c 'DEBIAN_FRONTEND=noninteractive apt-get -qq update && DEBIAN_FRONTEND=noninteractive apt-get -qq -y \
  -o Dpkg::Options::=--force-confold install --no-install-recommends \
  dnsmasq nftables tcpdump conntrack iproute2 iputils-ping dnsutils curl mtr-tiny ethtool procps less logrotate ca-certificates >/dev/null'"

# Caddy for the device TLS path: the same xcaddy build (with caddy-dns/cloudflare) the shared
# Caddy on the proxy container runs, copied rather than rebuilt so the gateway container needs no Go toolchain.
if ! x "bash -c '/usr/local/bin/caddy list-modules 2>/dev/null | grep -q dns.providers.cloudflare'"; then
  ssh "$PVE" "pct pull $PROXY_CTID /usr/local/bin/caddy /root/caddy-openflo.bin && pct push $CTID /root/caddy-openflo.bin /usr/local/bin/caddy --perms 0755 && rm -f /root/caddy-openflo.bin"
fi
x "bash -c 'id caddy >/dev/null 2>&1 || useradd --system --home-dir /var/lib/caddy --create-home --shell /usr/sbin/nologin caddy'"
x "install -d -o root -g caddy -m 0750 /etc/caddy"
# DNS-01 token: the host copy the shared Caddy provisioner keeps current. Never echoed.
ssh "$PVE" "umask 077; T=\$(mktemp); { printf CLOUDFLARE_API_TOKEN=; cat $CF_TOKEN_FILE; echo; } > \$T; pct push $CTID \$T /etc/caddy/.env.new --perms 0640; rm -f \$T"

# Configs (owned by root), capture script, then validate before activating.
COPYFILE_DISABLE=1 tar -C "$LAB/rootfs" --uid 0 --gid 0 --no-xattrs -cf - etc \
  | ssh "$PVE" "pct exec $CTID -- tar -C / -xf - --no-same-permissions --warning=no-unknown-keyword"
# Rename into place: a running capture keeps reading the old inode instead of a half-written file.
ssh "$PVE" "pct exec $CTID -- tee /usr/local/sbin/openflo-capture.new >/dev/null" <"$LAB/scripts/capture.sh"
x "chmod 0755 /usr/local/sbin/openflo-capture.new"
x "mv /usr/local/sbin/openflo-capture.new /usr/local/sbin/openflo-capture"
x "chmod 0644 /etc/nftables.conf /etc/dnsmasq.d/openflo.conf /etc/sysctl.d/90-openflo.conf /etc/tmpfiles.d/openflo.conf /etc/logrotate.d/openflo-dnsmasq /etc/caddy/Caddyfile /etc/systemd/system/caddy.service /etc/systemd/system/openflo-backend.service"
x "bash -c 'chown root:caddy /etc/caddy /etc/caddy/.env.new && chmod 0750 /etc/caddy && mv /etc/caddy/.env.new /etc/caddy/.env'"
x "install -d -o caddy -g caddy -m 0750 /var/log/caddy"

x "nft -c -f /etc/nftables.conf"
x "dnsmasq --test"
x "bash -c 'cd /var/lib/caddy && runuser -u caddy -- bash -c \"set -a; . /etc/caddy/.env; set +a; /usr/local/bin/caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1\"'"
x "systemctl daemon-reload"
x "systemd-tmpfiles --create /etc/tmpfiles.d/openflo.conf"
x "sysctl -q -p /etc/sysctl.d/90-openflo.conf"
x "systemctl enable -q --now nftables"
x "systemctl restart nftables"
x "systemctl enable -q dnsmasq"
x "systemctl restart dnsmasq"
x "systemctl enable -q caddy"
x "systemctl reload-or-restart caddy"
# Nothing should listen on the LAN side: no sshd, no postfix.
x "bash -c 'systemctl disable -q --now ssh.socket ssh.service postfix.service 2>/dev/null; systemctl mask -q ssh.service ssh.socket 2>/dev/null; true'"

echo "--- state"
x "systemctl is-active nftables dnsmasq caddy"
x "sysctl net.ipv4.ip_forward net.ipv6.conf.all.disable_ipv6"
x "ss -lntup"

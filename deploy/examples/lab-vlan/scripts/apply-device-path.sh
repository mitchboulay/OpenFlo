#!/usr/bin/env bash
# Apply ONLY the device-path files (Caddyfile, dnsmasq, nftables) to openflo-gw. Run from your workstation.
#   DRY_RUN=1 deploy/examples/lab-vlan/scripts/apply-device-path.sh   # validate candidates in the CT, change nothing
#   deploy/examples/lab-vlan/scripts/apply-device-path.sh             # validate, install, reload
# Unlike gateway-apply.sh it leaves the backend unit and everything else alone, so the gateway container's backend
# stays exactly as deployed (it is the rollback target). Rollback: check out the previous versions of
# these three files and re-run. Caddy reloads gracefully; dnsmasq and nftables restart in well under
# a second, which only matters if the dispenser is awake.
set -euo pipefail
PVE=${PVE_HOST:-root@192.168.1.2}
CTID=${CTID:-200}
ROOT=$(cd "$(dirname "$0")/../rootfs" && pwd)
FILES=(etc/caddy/Caddyfile etc/dnsmasq.d/openflo.conf etc/nftables.conf)

# Candidates go to /tmp, never next to the live files (dnsmasq would load a stray file in /etc/dnsmasq.d).
C=/tmp/openflo-candidate
x() { ssh "$PVE" "pct exec $CTID -- $*"; }
x "bash -c 'rm -rf $C && install -d -m 0755 $C'"
for f in "${FILES[@]}"; do
  ssh "$PVE" "pct exec $CTID -- tee $C/$(basename "$f") >/dev/null" <"$ROOT/$f"
done
x "nft -c -f $C/nftables.conf"
x "dnsmasq --test --conf-file=$C/openflo.conf"
x "bash -c 'cd /var/lib/caddy && runuser -u caddy -- bash -c \"set -a; . /etc/caddy/.env; set +a; /usr/local/bin/caddy validate --config $C/Caddyfile --adapter caddyfile\"'"
echo "candidates valid"
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  x "rm -rf $C"; echo "DRY_RUN: nothing changed"; exit 0
fi
for f in "${FILES[@]}"; do x "install -o root -g root -m 0644 $C/$(basename "$f") /$f"; done
x "rm -rf $C"
x "systemctl restart nftables"
x "systemctl restart dnsmasq"
x "systemctl reload caddy"
x "systemctl is-active nftables dnsmasq caddy"

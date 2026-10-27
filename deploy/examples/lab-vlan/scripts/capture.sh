#!/usr/bin/env bash
# OpenFLO lab capture. Runs on openflo-gw (installed as /usr/local/sbin/openflo-capture).
#
#   openflo-capture start <label>   begin a session in the background (systemd transient unit)
#   openflo-capture stop            end it cleanly (SIGTERM to tcpdump, then finalize: counters + checksums)
#   openflo-capture status | list
#
# Session dir /var/lib/openflo/captures/<UTC start>_<label>/ (0700, files 0600):
#   openflo_<UTC>.pcap[N]  full packets on eth1, new file every ROTATE_SECONDS or ROTATE_MB
#   dnsmasq.log            DNS/DHCP log lines written during the session
#   manifest.txt           start/stop times, settings, nft counters, DHCP leases
#   SHA256SUMS             written at stop
# Disk guard: the session stops itself at MAX_SESSION_MB or when free space < MIN_FREE_MB.
# Nothing is ever deleted or overwritten, so first-boot traffic is never rotated away.
set -euo pipefail
umask 077
export TZ=UTC

IFACE=${OPENFLO_IFACE:-eth1}
ROOT=${OPENFLO_CAPTURE_ROOT:-/var/lib/openflo/captures}
ROTATE_SECONDS=${OPENFLO_ROTATE_SECONDS:-3600}
ROTATE_MB=${OPENFLO_ROTATE_MB:-100}
MAX_SESSION_MB=${OPENFLO_MAX_SESSION_MB:-3072}
MIN_FREE_MB=${OPENFLO_MIN_FREE_MB:-1024}
DNS_LOG=/var/log/openflo/dnsmasq.log
UNIT=openflo-capture

utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
die() { echo "openflo-capture: $*" >&2; exit 1; }

state() {  # append counters + leases to the manifest
  { echo "== $1 $(utc)"; nft list counters table inet openflo 2>/dev/null | grep -E 'counter|packets' || true
    echo "-- leases"; cat /var/lib/misc/dnsmasq.leases 2>/dev/null || true; } >>"$2/manifest.txt"
}

# Lifecycle: the unit's main process IS tcpdump (exec), so systemd's SIGTERM goes straight to it and
# tcpdump closes its file cleanly. Helpers (DNS-log tail, disk guard) are recorded by pid and ended by
# finalize, which systemd runs as ExecStopPost however tcpdump exited (stop, guard, crash).
run() {
  local dir=$1
  printf 'started %s\ninterface %s\nrotate %ss / %sMB\nlimits session %sMB, min free %sMB\n%s\n' \
    "$(utc)" "$IFACE" "$ROTATE_SECONDS" "$ROTATE_MB" "$MAX_SESSION_MB" "$MIN_FREE_MB" "$(tcpdump --version 2>&1 | head -1)" >"$dir/manifest.txt"
  state start "$dir"
  tail -F -n0 "$DNS_LOG" >>"$dir/dnsmasq.log" 2>/dev/null & echo $! >"$dir/.tail.pid"
  guard "$dir" & echo $! >"$dir/.guard.pid"
  exec tcpdump -i "$IFACE" -s 0 -n -U -Z root -G "$ROTATE_SECONDS" -C "$ROTATE_MB" \
    -w "$dir/openflo_%Y%m%dT%H%M%SZ.pcap" 2>>"$dir/tcpdump.err"
}

guard() {  # stop the session (never delete) when it gets too big or the disk too full
  local dir=$1 used free
  sleep 5
  while :; do
    used=$(du -sm "$dir" | cut -f1); free=$(df -Pm "$dir" | awk 'NR==2{print $4}')
    if (( used >= MAX_SESSION_MB || free <= MIN_FREE_MB )); then
      echo "disk guard stop $(utc): session ${used}MB, free ${free}MB" >>"$dir/manifest.txt"
      systemctl stop --no-block "$UNIT"; return
    fi
    sleep 15
  done
}

finalize() {
  local dir=$1 f
  for f in "$dir/.tail.pid" "$dir/.guard.pid"; do
    [ -f "$f" ] && { kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; }
  done
  state stop "$dir"
  echo "stopped $(utc) (tcpdump ${SERVICE_RESULT:-?}/${EXIT_CODE:-?}/${EXIT_STATUS:-?})" >>"$dir/manifest.txt"
  (cd "$dir" && sha256sum -- * >SHA256SUMS)
  rm -f "$ROOT/.current"
}

[ "$(id -u)" = 0 ] || die "run as root"
case "${1:-}" in
  start)
    label=${2:-}; [[ $label =~ ^[A-Za-z0-9_-]{1,40}$ ]] || die "label: 1-40 chars of A-Z a-z 0-9 _ -"
    systemctl is-active --quiet "$UNIT" && die "already running: $(cat "$ROOT/.current")"
    systemctl reset-failed "$UNIT" 2>/dev/null || true
    dir="$ROOT/$(date -u +%Y%m%dT%H%M%SZ)_$label"; mkdir -p "$dir"; chmod 700 "$ROOT" "$dir"
    echo "$dir" >"$ROOT/.current"
    systemd-run --quiet --unit "$UNIT" -p KillMode=mixed -p KillSignal=SIGTERM -p TimeoutStopSec=20 \
      -p ExecStopPost="$(readlink -f "$0") _finalize $dir" \
      --setenv=OPENFLO_IFACE="$IFACE" --setenv=OPENFLO_CAPTURE_ROOT="$ROOT" \
      --setenv=OPENFLO_ROTATE_SECONDS="$ROTATE_SECONDS" --setenv=OPENFLO_ROTATE_MB="$ROTATE_MB" \
      --setenv=OPENFLO_MAX_SESSION_MB="$MAX_SESSION_MB" --setenv=OPENFLO_MIN_FREE_MB="$MIN_FREE_MB" \
      "$(readlink -f "$0")" _run "$dir"
    sleep 2; systemctl is-active --quiet "$UNIT" || die "failed to start; see $dir/tcpdump.err"
    echo "capturing on $IFACE -> $dir" ;;
  stop)
    systemctl is-active --quiet "$UNIT" || die "not running"
    dir=$(cat "$ROOT/.current"); systemctl stop "$UNIT"
    echo "stopped -> $dir"; ls -l "$dir" ;;
  status)
    if systemctl is-active --quiet "$UNIT"; then dir=$(cat "$ROOT/.current")
      echo "running: $dir ($(du -sh "$dir" | cut -f1))"; else echo "not running"; fi
    df -h "$ROOT" | tail -1 ;;
  list) ls -1 "$ROOT" ;;
  _run) run "$2" ;;
  _finalize) finalize "$2" ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac

#!/usr/bin/env bash
# Benchmark the device API: a scratch OpenFLO container (the deployed image) joins the compose network with its
# database on tmpfs and no volume, so the live /data is never touched. It seeds active devices with schedules,
# runs the firmware sync cycle (healthcheck, update-device, get-schedule, get-bottle, send-events) from a second
# container, and prints p50/p99. Exits 1 on server errors or p99 > 500 ms.
#
#   scripts/bench-device-api.sh [--devices N] [--cycles N] [--concurrency N] [--p99-max-ms MS]
#
# Needs the stack running (docker compose up -d). Safe to re-run: the scratch container is replaced and removed.
set -euo pipefail
cd "$(dirname "$0")/.."

name=openflo-bench
load_script=scripts/bench_device_api.py

live=$(docker compose ps -q openflo)
if [ -z "$live" ]; then
  echo "bench: the openflo service is not running; start the stack with: docker compose up -d" >&2
  exit 1
fi
image=$(docker inspect -f '{{.Config.Image}}' "$live")
network=$(docker inspect -f '{{range $net, $_ := .NetworkSettings.Networks}}{{$net}}{{end}}' "$live")

cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
cleanup
trap cleanup EXIT

healthy() {
  docker exec "$name" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=2)" 2>/dev/null
}

# Same hardening as compose.yaml. X-Forwarded-For is trusted from anyone here (and only here) so each simulated
# device gets its own source IP, as real devices do, and the per-IP rate limit applies per device.
docker run -d --name "$name" --network "$network" \
  --read-only --tmpfs /tmp --tmpfs /bench:uid=10001,gid=10001,mode=0700 \
  --cap-drop ALL --security-opt no-new-privileges \
  -e OPENFLO_BACKEND_DB=/bench/openflo.db -e FORWARDED_ALLOW_IPS='*' \
  "$image" >/dev/null

for _ in $(seq 1 30); do
  healthy && break
  sleep 1
done
if ! healthy; then
  echo "bench: the scratch server did not become healthy" >&2
  docker logs --tail 50 "$name" >&2
  exit 1
fi

devices=50
args=("$@")
for ((i = 0; i + 1 < ${#args[@]}; i++)); do
  if [ "${args[i]}" = "--devices" ]; then devices=${args[i + 1]}; fi
done

docker exec -i "$name" python - --seed /bench/openflo.db --devices "$devices" < "$load_script"
docker run --rm -i --network "$network" --read-only --cap-drop ALL --security-opt no-new-privileges \
  "$image" python - --url "http://$name:8099" "$@" < "$load_script"

#!/usr/bin/env bash
# Deploy the device backend emulator to openflo-gw (the gateway container). Run from your workstation.
# Tests run on the target against the new code before it replaces the live copy.
# The SQLite DB in /opt/openflo/backend is never touched.
set -euo pipefail
PVE=${PVE_HOST:-root@192.168.1.2}
CTID=${CTID:-200}
LAB=$(cd "$(dirname "$0")/.." && pwd)
REPO=$(cd "$LAB/../../.." && pwd)
DEST=/opt/openflo/backend
x() { ssh "$PVE" "pct exec $CTID -- $*"; }

COPYFILE_DISABLE=1 tar -C "$REPO/backend" --no-xattrs --no-mac-metadata --exclude=__pycache__ --exclude=.pytest_cache --exclude='*.db*' \
  -czf - app tests requirements.txt \
  | ssh "$PVE" "pct exec $CTID -- bash -c 'rm -rf $DEST.new && mkdir -p $DEST.new && tar -C $DEST.new -xzf -'"
x "bash -c 'cd $DEST.new && /opt/openflo/venv/bin/python -m pytest -q -p no:cacheprovider tests'"

ssh "$PVE" "pct exec $CTID -- tee /etc/systemd/system/openflo-backend.service >/dev/null" \
  <"$LAB/rootfs/etc/systemd/system/openflo-backend.service"
x "bash -c 'set -e; cd $DEST; rm -rf app.old tests.old; mv app app.old; mv tests tests.old
  mv $DEST.new/app $DEST.new/tests .; cp $DEST.new/requirements.txt .; rm -rf $DEST.new app.old tests.old
  systemctl daemon-reload; systemctl enable -q openflo-backend; systemctl restart openflo-backend'"

for _ in $(seq 1 20); do
  x "curl -fsS -m2 http://127.0.0.1:8099/healthz" && echo && exit 0
  sleep 1
done
echo "backend did not become healthy" >&2
exit 1

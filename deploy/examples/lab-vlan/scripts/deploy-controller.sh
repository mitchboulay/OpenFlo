#!/usr/bin/env bash
# Deploy OpenFLO controller to the gateway container (openflo-gw)
set -euo pipefail

PROXMOX=${PVE_HOST:-root@192.168.1.2}
CTID=${CTID:-200}
REMOTE_DIR=/opt/openflo
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB="$(dirname "$SCRIPT_DIR")"

echo "=== Deploying OpenFLO controller to CT $CTID ==="

# Push controller files
echo "Pushing files..."
for f in controller/app.py controller/dashboard.html controller/requirements.txt; do
  src="$LAB/$f"
  dest="$REMOTE_DIR/$(basename "$f")"
  scp "$src" "$PROXMOX:/tmp/openflo_$(basename "$f")"
  ssh "$PROXMOX" "pct push $CTID /tmp/openflo_$(basename "$f") $dest"
done

# Install dependencies and create venv if needed
echo "Setting up venv..."
ssh "$PROXMOX" "pct exec $CTID -- bash -c '
  mkdir -p $REMOTE_DIR
  if [ ! -d $REMOTE_DIR/venv ]; then
    python3 -m venv $REMOTE_DIR/venv
  fi
  $REMOTE_DIR/venv/bin/pip install -q -r $REMOTE_DIR/requirements.txt
'"

# Deploy systemd unit
echo "Installing systemd service..."
ssh "$PROXMOX" "pct exec $CTID -- bash -c 'cat > /etc/systemd/system/openflo.service << EOF
[Unit]
Description=OpenFLO Local Controller
After=network.target

[Service]
Type=simple
WorkingDirectory=$REMOTE_DIR
ExecStart=$REMOTE_DIR/venv/bin/python $REMOTE_DIR/app.py
Restart=always
RestartSec=5
Environment=OPENFLO_DEVICE_IP=192.168.30.80
Environment=OPENFLO_DB_PATH=/var/lib/openflo/openflo.db
Environment=OPENFLO_PORT=8080
# Passive only. 1 = one /dev_info read per wake (each request extends the wake).
Environment=OPENFLO_READ_ON_WAKE=0
# Backend API token (OPENFLO_API_TOKEN) for the dashboard controls (server-side only).
EnvironmentFile=-/etc/openflo/backend.env

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable openflo
systemctl restart openflo
'"

echo "Waiting for service to start..."
sleep 3

ssh "$PROXMOX" "pct exec $CTID -- systemctl status openflo --no-pager -l" || true

echo ""
echo "=== Deployed. Dashboard at http://192.168.30.1:8080 ==="

# Mission 006: Local Controller and Wake-Aware Monitoring

Date: 2026-10-26. Status: **IN PROGRESS** — controller deployed, awaiting first wake event.

## Executive summary

The OpenFLO local controller is deployed on the gateway container and passively monitoring the lab interface for device activity. When the device MAC appears on the wire (via tcpdump), the controller starts a burst of `GET /dev_info` polls to capture telemetry. Zero network traffic when the device is sleeping.

The controller listens on localhost only. No firewall rules were modified, no external routes were added. Access is via SSH into the gateway container or SSH tunnel.

The controller has not yet observed a device wake event. Analysis of the baseline capture shows the device woke frequently during provisioning and app interaction (5 sessions in 75 minutes), but the true idle wake interval is undetermined — the device has been asleep for over an hour since the last app-triggered activity.

## Phase 1 — Environment verification

The gateway container (openflo-gw) confirmed operational:
- Uptime: 2h12m at mission start
- Disk: 8GB total, 6GB free (26% used)
- Baseline capture: active, 1.2GB across 13 pcap files (3072MB session limit)
- DHCP lease: device at 192.168.30.80 (MAC 68:67:25:00:00:01)
- Device configuration: unchanged from Mission 004

## Phase 2 — Wake/sleep analysis

### Raw data

Analyzed all pcap files for frames involving the device MAC (`68:67:25:00:00:01`). Merged sub-bursts with <120s gaps into wake sessions:

| Session | Start (UTC) | Duration | Frames | Likely trigger |
|---|---|---|---|---|
| 1 | 14:56:36 | 107s | 1937 | Initial provisioning |
| 2 | 15:01:40 | 189s | 542 | Cartridge activation |
| 3 | 15:33:45 | 187s | 1082 | Idle wake? App poll? |
| 4 | 16:03:37 | 33s | 218 | App interaction |
| 5 | 16:07:25 | 56s | 267 | App interaction |

### Inter-session gaps

| Gap | Duration | Notes |
|---|---|---|
| 1→2 | 3.3 min | Post-provisioning rapid check |
| 2→3 | 28.9 min | First idle interval |
| 3→4 | 26.8 min | Second idle interval |
| 4→5 | 3.3 min | Likely app-triggered |
| 5→now | 60+ min | Device still sleeping |

### Findings

1. **Wake duration varies widely**: 33s to 189s. Longer sessions correlate with more cloud traffic (TLS exchanges).

2. **Idle interval is not yet determined.** The 27-29min gaps may have been app-triggered, not idle-timer wakes. The device has been asleep for over an hour since the last interaction, suggesting the true idle interval is significantly longer — possibly hours.

3. **Protocol breakdown** (all device-originated frames):
   - TCP: 1653 frames (raw connections)
   - TLS: 306 frames (cloud polls)
   - ARP: 84 frames (network discovery)
   - mDNS: 42 frames (service announcements)
   - DNS: 20 frames (name resolution)
   - HTTP: 19 frames (local API requests from us)
   - DHCP: 16 frames (IP lease)
   - NTP: 7 frames (time sync)

4. **Wake detection approach.** The device sends ARP, DHCP, and mDNS frames immediately on wake. Passive tcpdump monitoring on eth1 for the device MAC detects wakes with zero unsolicited traffic.

## Phase 3-7 — Controller implementation

### Architecture

```
The gateway container (openflo-gw)
├── /opt/openflo/app.py          # FastAPI app: passive wake detector + device client + API
├── /opt/openflo/dashboard.html  # Monitoring dashboard
├── /opt/openflo/venv/           # Python virtual environment
├── /var/lib/openflo/openflo.db  # SQLite telemetry database
└── /etc/systemd/system/openflo.service
```

### Wake detection (passive)

`tcpdump -l -i eth1 -c 1 --immediate-mode -q "ether src 68:67:25:00:00:01"` blocks until any frame from the device MAC appears on the lab interface. When tcpdump exits (one packet captured), the controller starts a polling burst. Zero network traffic when the device is sleeping.

### Burst polling

On wake detection, poll `GET /dev_info` every 2 seconds. After 5 consecutive failures (10 seconds of silence), conclude the device has gone back to sleep and return to passive waiting.

### Device client

Read-only `httpx.AsyncClient` with 2-second timeout. Only calls `GET /dev_info`. No POST endpoints. No authentication (device requires none).

### Data model

```sql
wake_events (id, started_at, ended_at, readings_count)
readings (id, wake_event_id, captured_at, signal, battery, doses, bottle_status,
          firmware_version, device_id, pcb_version, device_type, device_mode,
          ext_power_state, flood_now, float_en, wifi_ssid, is_pro_version,
          demo_mode_visible, nam_visible, user_dispense_visible, raw_json)
```

WAL mode, busy timeout 5s, indexed on `captured_at DESC` and `wake_event_id`.

### API

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Current monitor state: awake/asleep, poll stats, last reading |
| `/api/readings` | GET | Paginated telemetry history (limit, offset, wake_event_id) |
| `/api/wake-events` | GET | Paginated wake session history |
| `/api/stats` | GET | Summary statistics: battery trend, wake frequency, avg duration |
| `/` | GET | Monitoring dashboard |

### Dashboard

Dark-themed, responsive HTML served by FastAPI. Six metric cards (device status, battery, doses, signal, wake count, uptime) plus tables for recent wake events and readings. Auto-refreshes every 5 seconds.

### Access

The service listens on `127.0.0.1:8080` only. No firewall ports were opened, no Caddy routes were added, no external access was configured.

Access methods:
- From within the gateway container: `curl http://127.0.0.1:8080/api/status`
- SSH tunnel: `ssh -L 8080:localhost:8080 root@192.168.1.2 "pct exec $CTID -- socat TCP-LISTEN:8080,bind=127.0.0.1,reuseaddr,fork TCP:127.0.0.1:8080"`

Exposing the dashboard externally (Caddy route, nftables rule) is deferred until the controller is validated and the access model is explicitly approved.

### Deployment

```bash
./scripts/deploy-controller.sh
```

Pushes files to the gateway container, creates venv, installs deps, deploys systemd unit, enables and starts the service.

## Phase 8 — Validation

### Verified

- [x] Controller starts and runs as systemd service
- [x] Passive wake detection via tcpdump (process visible in service tree)
- [x] Zero HTTP traffic when device is sleeping (total_polls=0 while waiting)
- [x] API endpoints return correct JSON from localhost
- [x] SQLite database created with correct schema
- [x] Service listens on 127.0.0.1 only (not externally accessible)
- [x] No firewall modifications on the gateway container
- [x] No Caddy routes added
- [x] Baseline capture undisturbed

### Pending (requires device wake)

- [ ] Successful `GET /dev_info` reading during wake window
- [ ] Wake event created in database
- [ ] Reading persisted with all fields
- [ ] Wake session end detected after device sleeps
- [ ] Dashboard displays live telemetry
- [ ] Multiple wake cycles captured with correct interval stats

## Changes made this mission

### On the gateway container
- Created `/opt/openflo/` with app.py, dashboard.html, requirements.txt, venv
- Created `/var/lib/openflo/openflo.db` (SQLite)
- Installed systemd service `openflo.service` (enabled, running)
- Installed system packages: python3-pip, python3-venv, python3-dev, sqlite3

### In this repository
- Created `controller/app.py` — FastAPI controller (passive wake detection, device client, API, dashboard)
- Created `controller/dashboard.html` — monitoring dashboard
- Created `controller/requirements.txt` — Python dependencies
- Created `scripts/deploy-controller.sh` — deployment script

### No network changes
- Gateway nftables: unchanged from Mission 003
- Caddy reverse proxy: unchanged
- No ports opened, no routes added

### No device changes
- No firmware modifications
- No configuration changes
- No POST requests sent to device
- Baseline capture undisturbed

## Deliverables

- [x] Wake/sleep analysis from existing captures
- [x] Passive wake detection service (tcpdump-based, running as systemd unit)
- [x] Read-only device client (GET /dev_info only)
- [x] SQLite persistence (wake_events + readings tables)
- [x] FastAPI API (4 endpoints)
- [x] Monitoring dashboard (localhost only)
- [ ] First successful telemetry capture (awaiting device wake)
- [x] This mission report

## Mission 007 proposal

### Objective

Validate the full telemetry pipeline across multiple natural wake cycles and determine the true idle wake interval.

### Scope

1. **Let the controller run for 24-48 hours** unattended. Collect wake events and telemetry across a full day/night cycle.

2. **Analyze wake patterns:**
   - True idle interval (without app interaction)
   - Whether the interval is fixed or variable
   - Whether time-of-day affects wake behavior
   - Wake duration distribution

3. **Validate telemetry integrity:**
   - All 17 `/dev_info` fields captured correctly
   - Wake session start/end detection accuracy
   - Database growth rate and disk projections

4. **Baseline capture retention:** Keep the baseline pcap capture running alongside the controller until the controller has proven it captures wake events reliably. The capture provides independent verification. Consider safe rotation and retention controls if disk pressure becomes a concern.

5. **Access model decision:** Present options for dashboard exposure (localhost-only, SSH tunnel, restricted Caddy route) for explicit approval before adding any network routes.

### Prerequisites

- Controller has captured at least 3 wake events
- Operator approval for any network exposure changes
- Operator approval for any active experiments (No-App Mode, etc.)

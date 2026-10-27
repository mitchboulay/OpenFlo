# Mission 003: First contact and protocol discovery

Date: 2026-10-26. Status: **first-boot capture complete and analysed. The baseline capture is still running.** `cloud-replacement-feasibility.md` (Phase 5) was **not produced** in this session.

## Phase 0: capture readiness

| Check | Result |
|---|---|
| Signal handling audit | Two defects found and fixed in `scripts/capture.sh`: (1) `OPENFLO_*` limits weren't passed into the systemd unit; (2) the stop/guard path relied on bash signal handling, which lost early SIGINTs and could kill the worker before it sealed the session. Now tcpdump is the unit's main process (`exec`, SIGTERM, `KillMode=mixed`), the disk guard calls `systemctl stop`, and sealing runs as `ExecStopPost` |
| Repeated start/stop | 3 cycles + idle + 2 guard sessions: all `Result=success`, stop in 1–2 s, no leftover processes |
| PCAP integrity | `tcpdump -r` without errors, 0 kernel drops, `sha256sum -c` OK, perms 0700/0600 |
| DNS log / manifest / checksums | DNS slice caught 20/20 test queries. Manifest has start/stop counters and leases |
| Rotation | `-G` rotation produced predictable UTC filenames |
| Disk guard | Size and free-space limits both stop the session cleanly |
| Wi-Fi password | Rotation not done: **operator decision** to keep the simple PSK (isolation doesn't depend on it) |
| Revalidation | DHCP, DNS, internet and isolation re-verified 14:44Z with the Pixel |
| Disk | 7.5 GB free at analysis time (session 38 MB) |

## Operator checkpoints

| Checkpoint | Approved | Notes |
|---|---|---|
| 1 First power-on | "go" ~14:44Z | Batteries inserted after capture start |
| 2 Pairing | "approve pairing" ~14:52Z | PCAPdroid had to be stopped (app blocks VPNs) |
| 3 Cartridge activation | "approve cartridge" ~15:00Z | QR scan 15:00:44, cartridge inserted |
| 4 Dispensing | **Not requested, not performed** | App offered dispense/schedule; operator exited |

## Results (detail in the linked documents)

1. **Device identity:** `IFLOKIT01`, ESP32 (Espressif OUI, `board=esp32`), 4×AA, no FCC ID on the label. See `device-identification.md`.
2. **Provisioning:** SoftAP `iFLO device` + HTTP to `192.168.4.1:80`, no BLE. The app refuses to pair with a VPN on. A firmware update (~1.39 MB) was LIKELY applied during setup. See `provisioning-flow.md`.
3. **Cloud endpoints:** the device talks only to `backend.iflo.com` (34.120.139.126:443) plus NTP. The app uses the same backend, `app.iflo.com`, and Firebase project `iflo-61da5`. See `cloud-endpoints.md`.
4. **Protocol / TLS:** HTTPS over TLS 1.2, no SNI, no ALPN, short device-initiated request bursts, no inbound connections, no MQTT/WebSocket. Wi-Fi is off between wakes. The device advertises a local HTTP server on port 80 while awake. See `protocol-analysis.md`.
5. **Timeline:** see `event-timeline.md`.

## Evidence (private, outside the repo)

| Item | Location |
|---|---|
| Gateway session (live, continuing as the baseline) | the gateway container `/var/lib/openflo/captures/20261026T144415Z_first-provision/` |
| Snapshot of the first-provision window | `~/openflo-private/captures/first-provision-snapshot-20261026T150721Z.tar` |
| PCAPdroid captures | `~/openflo-private/phone/PCAPdroid/` (copies in the gateway container `/var/lib/openflo/phone/`, 0700) |
| APK splits | `~/openflo-private/apk/` |
| Photos | `~/openflo-private/photos/` |

## Changes made this mission

- `scripts/capture.sh` restructured (see Phase 0). Redeployed to the gateway container.
- `tshark` installed in the gateway container for analysis.
- Phone: iFLO app and PCAPdroid installed, USB debugging on, home Wi-Fi auto-connect disabled by the operator. **No certificate installed** (Proxyman step skipped: the app trusts system CAs only).
- The iFLO is provisioned to OpenFLO, cartridge activated, firmware updated by the vendor during setup.

## Open items

- ~~Phase 5 feasibility write-up not produced.~~ Produced in a follow-up session. See `cloud-replacement-feasibility.md`.
- Stop the baseline capture after ≥24 h (`openflo-capture stop`), then analyse the wake interval.
- Phone clean-up when finished: re-enable home Wi-Fi auto-connect, optionally uninstall PCAPdroid, turn off USB debugging.

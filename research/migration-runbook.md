# Migration runbook — stock iFLO 3.0.64 → OpenFLO (Mission 008C)

> **Historical.** This runbook records a one-time manual migration of the lab device. It is not how to add a device today: use the Add device wizard ([docs/provisioning.md](../docs/provisioning.md)).

**Do not execute without Mission 008C authorization.** The device is an
expendable R&D unit. This procedure **factory-resets** it: vendor registration,
Wi-Fi settings and cartridge state are wiped. Rollback to the vendor cloud is not
guaranteed.

Evidence classes: **[S]** confirmed by static firmware analysis, **[R]**
runtime-verified on this device or stack, **[I]** inference.
Sources: `firmware-provisioning-and-responses.md`, `backend-recovery-readiness.md`.

Conventions: `PVE="ssh root@192.168.1.2"`, `CT="pct exec $CTID --"`. All times UTC.

---

## 0. Never do

- Do not press the user button. A long press can reach the manual-dispense
  routine (`FUN_4008e344`) [S].
- Do not poll `/dev_info` in a loop. Every local request reloads the sleep timer
  [S][R]. A single read is fine.
- Do not set `OPENFLO_BACKEND_ENABLE_SCHEDULE` / `_BOTTLE`. A 200 there writes a
  schedule or bottle config [S].

## 1. Readiness checks (backend side; device untouched)

```bash
$PVE "$CT bash -c '
systemctl is-active caddy openflo-backend dnsmasq nftables openflo-capture openflo
curl -fsS http://127.0.0.1:8099/healthz; echo
systemctl show openflo-backend -p Environment | tr \" \" \"\n\" | grep OPENFLO_
nft list counter inet openflo lab_device_tls | grep packets
grep 68:67:25:00:00:01 /var/lib/misc/dnsmasq.leases
'"
```

Expect:

- All six units `active`.
- `safe_mode` shows ota/remote_dispense suppressed and schedule/bottle disabled.
- `OPENFLO_ALLOWED_DEVICE_IDS=D8256700000A0001` and `OPENFLO_REGISTER_ALLOWED_SOURCES=192.168.30.80`.
- `OPENFLO_ADOPT_UNREGISTERED=true` (lab-only recovery; see §6).
- `lab_device_tls` packets 0.
- Lease shows `192.168.30.80`.

**1b. Pin the device IP** (the firewall and allowlists depend on it). Add a
reservation, validate, restart dnsmasq:

```bash
# in openflo/gateway/rootfs/etc/dnsmasq.d/openflo.conf, after dhcp-range:
#   dhcp-host=68:67:25:00:00:01,192.168.30.80
$PVE "$CT tee /etc/dnsmasq.d/openflo.conf >/dev/null" < gateway/rootfs/etc/dnsmasq.d/openflo.conf
$PVE "$CT bash -c 'dnsmasq --test && systemctl restart dnsmasq'"
```

**1c. Choose and pin the pairing token.** The firmware sends the provisioned
`TOKEN` as `x-device-ott` on `register` [S]. Generate one and pin its hash, so
only this token can enroll:

```bash
TOKEN=$(openssl rand -hex 12); echo "$TOKEN"   # keep for step 3; >= 4 chars, not "null" [S]
HASH=$(printf %s "$TOKEN" | shasum -a 256 | cut -d" " -f1)
$PVE "$CT bash -c 'mkdir -p /etc/systemd/system/openflo-backend.service.d && printf \"[Service]\nEnvironment=OPENFLO_ENROLL_TOKEN_SHA256=$HASH\n\" > /etc/systemd/system/openflo-backend.service.d/enroll-token.conf && systemctl daemon-reload && systemctl restart openflo-backend && curl -fsS http://127.0.0.1:8099/healthz >/dev/null && echo pinned'"
```

**1d. Start a dedicated capture marker.** The baseline capture keeps running.
Note the start time:

```bash
date -u +%FT%TZ   # T0
```

**Checkpoint 1:** every check above passes. If any fails, stop.

## 2. Reset (least destructive viable method)

There is **no non-destructive way** to change the host on a registered device
[S]. Every operator-reachable reset is mode 0, which wipes registration, host,
Wi-Fi and cartridge state (`bttl_vald`, `max_doses`, `started_disp_cnt`,
`dose_time`) [S]. The mode-1 path (which keeps the cartridge) is reachable only
through a vendor `NOT_UNIQUE` reply.

**2a. Get the device awake on demand.** Remove and reinsert the batteries
(≥ 10 s out). It boots registered, joins `OpenFLO` and syncs with the vendor
[I: boot → STA → sync]. Watch for the wake:

```bash
$PVE "$CT curl -sS http://127.0.0.1:8080/api/status"   # device_awake: true
```

(Or wait for a natural wake. The passive controller sends nothing [R].)

**2b. Confirm identity, then reset** in the same wake (one read, then one action):

```bash
$PVE "$CT curl -sS -m 3 http://192.168.30.80/dev_info"
# expect deviceId D8256700000A0001, firmwareVersion 3.0.64, deviceMode Normal
$PVE "$CT curl -sS -m 5 -X POST http://192.168.30.80/dev_actions -H 'Content-Type: application/json' -d '{\"restoreToDefault\": true}'"
```

Expected [S]: an HTTP reply, then the config wipe, then a restart within about 5 s. The
device disappears from VLAN 30 (Wi-Fi credentials wiped).

These requests originate on the gateway container, whose OUTPUT is unfiltered (this is the path
the old controller used [R]). No firewall change is needed.

**Fallback** if 2b fails or the device never wakes: `GET
http://192.168.30.80/resetdefault` during a wake (mode INFERRED 0), or the reset
button long press (mode 0 [S]; hold time UNKNOWN; this is the *reset* button,
not the user button).

**Checkpoint 2:** within 60 s, a Wi-Fi network named **`iFLO device`** appears
[S]. If it doesn't appear within 5 min, pull and reinsert the batteries once.
An unregistered device boots straight into AP [S].

## 3. Provision directly to OpenFLO

> **Mission 008C result: use the phone path below.** The Mac CLI could not
> switch Wi-Fi (macOS 27: `networksetup` reports success but doesn't move), and
> manual Mac joins to `iFLO device` bounced back within 2–4 s. A phone worked
> first try: join `iFLO device`, then open the device's own page
> `http://192.168.4.1/index.html?ott=<TOKEN>&apiUrl=https://openflo-backend.home.example.com&deviceType=0`
> (QR-encode it), pick `OpenFLO`, and enter the PSK (from your secrets manager
> `.wifi.psk`). The page sends the same three-item `/config`. A mode-0 reset
> also makes the device **prime at power-on**; that is expected before
> provisioning.

From the Mac: join Wi-Fi **`iFLO device`**, password **`13106423`** [S]. The
device is at `192.168.4.1` [I, high]. Then:

```bash
curl -sS -m 10 -X POST http://192.168.4.1/config \
  -H 'Content-Type: application/json' \
  -d '{"data":[
        {"type":"TOKEN","data":"'"$TOKEN"'"},
        {"type":"SERVER_CREDENTIALS","host":"https://openflo-backend.home.example.com"},
        {"type":"WIFI_CONFIG","ssid":"OpenFLO","pass":"<OpenFLO-Lab SSID password>"}
      ]}'
```

Expect `200 OK` [S]. On an unregistered device, `/config` then starts
`Pairing_task` [S]. Errors:

- `400 device is already registered`: the reset did not happen. Go back to step 2.
- `400 one of object is wrong`: there's a typo in a `type`.
- `400 Bad json`: the body is malformed (it must be ≤ 512 bytes).

Rejoin the Mac to the home network.

## 4. Capture registration and first sync

Expected sequence [S] (about 10–60 s after `/config`):

1. The device leaves AP, joins `OpenFLO`, and DHCP gives it `192.168.30.80`.
2. DNS `openflo-backend.home.example.com` → `192.168.30.1`.
3. TLS 1.2 to `192.168.30.1:443` without SNI (`lab_device_tls` counter > 0).
4. `POST /device-api/v2/healthcheck {"deviceId"}` → **200** (loops until 200).
5. `POST /device-api/v2/register` with `x-device-ott: $TOKEN`, body `{"deviceId"}`
   → **200** → `registred=1` persisted.
6. Later: `POST /device-api/v2/update-device` → `{"data":{"isUpToDate":true}}`.

Watch:

```bash
$PVE "$CT bash -c '
grep 192.168.30.80 /var/log/openflo/dnsmasq.log | tail -5
nft list counter inet openflo lab_device_tls | grep packets
tail -n 20 /var/log/caddy/openflo-access.log | cut -c1-300
tail -n 20 /var/log/caddy/caddy.log | grep -i -E \"tls|handshake|error\" | cut -c1-300
'"
$PVE "$CT /opt/openflo/venv/bin/python -c \"
import sqlite3; c=sqlite3.connect('/opt/openflo/backend/openflo-backend.db')
for r in c.execute('select ts,path,status from protocol_logs order by id desc limit 15'): print(r)
print('registrations', c.execute('select device_id,status,remote_addr,created_at from registrations').fetchall())
\""
```

## 5. Success is two milestones (registration alone is not a migration)

### Milestone 1: enrolled and synchronized

- A `registrations` row for `D8256700000A0001` from `192.168.30.80`, with an
  `ott_sha256` equal to the pinned hash. A row marked `adopted` means pairing's
  `register` failed and the lab recovery path was used. Record it, because that
  is not a clean enrollment.
- At least one `update-device` → 200 `{"data":{"isUpToDate":true}}`.
- The latest `telemetry` row has `batteryLevel`, `firmwareVersion` = `3.0.64`, and signal.

### Milestone 2: proven battery-safe operating cycle

All three must be observed passively (nothing polls the device):

1. **Returns to deep sleep.** The wake that contained Milestone 1 ends: the
   controller wake row gets `ended_at`, and the pcap shows **zero frames** from
   the device MAC for longer than the 120 s idle gap. Wake duration ≤ 10 min.
   ```bash
   $PVE "$CT curl -sS 'http://127.0.0.1:8080/api/wake-events?limit=3'"
   ```
2. **Wakes on its own.** A later wake starts with no operator action (new
   controller wake row; DHCP + DNS for the OpenFLO host in the dnsmasq log).
3. **Re-synchronizes.** That wake produces another `update-device` 200, and then
   that wake also ends (≤ 10 min).

**The migration is complete only after Milestone 2.** If no natural wake occurs
within the 4 h observation window, Milestone 2 is **pending**, not failed: keep
the passive watch (capture, controller, backend logs) running and evaluate the
next wake against the same criteria and stop conditions. Do not induce a wake by
polling. A battery power-cycle wake does **not** count as a natural wake.

Optional, once per later wake (not a loop): one `/dev_info` read to see `doses`
and `bottleStatus` after the mode-0 wipe. That read extends the wake by one
sleep-timer period, so don't take it in the wake being measured for item 1.

## 6. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| No `iFLO device` AP after reset | Reset didn't run, or the AP timer expired | Pull and reinsert the batteries; retry 2b at the next wake; then the reset button |
| `/config` → `already registered` | Reset didn't happen | Back to step 2 |
| No DHCP from the device after `/config` | Wrong SSID/password in `WIFI_CONFIG` | The device stays or returns to AP. Re-send `/config` with the correct credentials (still unregistered) |
| DHCP OK, no DNS query for the OpenFLO host | Host not stored | Re-provision |
| `lab_device_tls` stays 0 after DNS | Lease ≠ .80 or MAC mismatch | Check the lease and the step 1b reservation |
| TLS packets but no HTTP in the Caddy log | mbedTLS rejected the chain or handshake | Check `caddy.log` for the handshake error; re-run `tools/dump_crt_bundle.py verify` on the served chain. **Stop** and analyze; don't loop |
| `healthcheck` 403 | Device ID not allowlisted | Check `OPENFLO_ALLOWED_DEVICE_IDS` |
| `register` 403 `SOURCE_NOT_ALLOWED` / `INVALID_ENROLLMENT_TOKEN` | Source or token mismatch | Fix the allowlist or hash. The device retries 3×, then pairing fails; at the next boot it marks itself registered anyway and syncs `update-device` [S]. With the **lab-only** `OPENFLO_ADOPT_UNREGISTERED=true`, the backend adopts it (allowlisted ID + source; bypasses the token pin; audited as `adopted`) [R: test]. Without the flag, it gets ignorable 422s until re-provisioned |
| `update-device` 422 `DEVICE_NOT_REGISTERED` | Backend DB lost the row and the source didn't match | Harmless: error bodies carry no `fields`, so the firmware ignores them [S]. Fix the source and it is adopted |

Re-provisioning is always possible while the device is unregistered and in AP.
Once registered, only another reset (step 2) changes the host.

## 7. Stop conditions (abort and assess; no automated rollback)

- Any `doses` decrease, dispense event, or motor sound: **stop immediately**.
- `firmwareVersion` ≠ 3.0.64: stop.
- A wake longer than 10 min with nothing polling the device.
- More than 5 TLS handshakes or more than 10 API requests in one wake (retry loop).
- Battery below 90 %, or down ≥ 3 points during the observation window (same as `device-baseline.md` §5).
- 2 consecutive wakes without a 200 `update-device` after registration.

## 8. After success

- Keep `enroll-token.conf` (it pins the enrollment token).
- Once Milestone 2 is reached and no recovery is needed, consider unsetting
  `OPENFLO_ADOPT_UNREGISTERED` so that the token pin is the only enrollment path.
- Add `dhcp-host` and the token-pin approach to the repo (`gateway/rootfs`),
  without committing the token itself.
- Record evidence in `research/mission-008c.md`.

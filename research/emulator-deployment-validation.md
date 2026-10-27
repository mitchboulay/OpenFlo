# Emulator deployment validation — Mission 008 Phase 1

Date: 2026-10-26. Independent verification of the deployed backend emulator.

## 1. Process health

| Check | Result |
|---|---|
| Service name | `openflo-backend.service` |
| State | `active (running)` |
| PID | 22194 |
| Started | 2026-10-26 18:48:18 UTC |
| Listening | `0.0.0.0:8099` (uvicorn) |
| Host | the gateway container (`openflo-gw`, 192.168.1.30 / 192.168.30.1) |

## 2. Source and configuration

| Item | Value |
|---|---|
| Source path | `/opt/openflo/backend/` |
| Python | 3.11.2 via `/opt/openflo/venv/` |
| Framework | FastAPI 0.115.0, uvicorn 0.30.6 |
| DB path | `/opt/openflo/backend/openflo-backend.db` |
| DB writable | YES |
| Enrollment tokens | NOT CONFIGURED (open enrollment) |
| Payload logging | ENABLED (default) |
| Max body size | 65536 bytes (default) |
| Schedule endpoints | DISABLED (default safe mode) |
| Bottle endpoints | DISABLED (default safe mode) |
| Registration required | YES (default) |

## 3. Route verification

All eight `/device-api/v2/` endpoints tested with actual HTTP requests from
`127.0.0.1` on the gateway container.

| Endpoint | Status | Response |
|---|---|---|
| `POST /register` | 200 | `{}` |
| `POST /update-device` | 200 | `{"data":{"isUpToDate":true}}` |
| `POST /get-fw` | 200 | `{"actualFirmwareVersion":"3.0.64"}` |
| `POST /get-schedule` | 501 | `NOT_IMPLEMENTED` (disabled) |
| `POST /get-bottle` | 501 | `NOT_IMPLEMENTED` (disabled) |
| `POST /healthcheck` | 200 | `{}` |
| `POST /send-events` | 200 | `{}` |
| `POST /create-qc-report` | 200 | `{}` |

## 4. Safe-mode response verification

The `/update-device` response was inspected field by field:

```json
{"data": {"isUpToDate": true}}
```

| Safety check | Result |
|---|---|
| `isUpToDate` is `true` | PASS |
| No `remoteDispense` field | PASS |
| No OTA `url` field | PASS |
| No `extPowerState` directive | PASS |
| No `isSettingsSynced` directive | PASS |
| No `isWifiUpdated` directive | PASS |
| Response contains ONLY `data.isUpToDate` | PASS |

The `/get-fw` response contains only `actualFirmwareVersion` — no `url` or
`redirectLocation`.

## 5. Protocol logging and redaction

- Protocol logging is enabled (14 entries created during testing).
- The OTT value `test-ott-008` was NOT found in any protocol log row
  (checked `request_json`, `response_json`, `headers_json`).
- The `x-device-ott` header is deliberately excluded from logged headers.
- OTT is stored only as SHA-256 in the `registrations` table.

## 6. Network isolation

| Check | Result |
|---|---|
| Public tunnel routes | NOT in `cloudflare/routes.yml` |
| Cloudflared config | NOT in the Cloudflare Tunnel config |
| Firewall: who can reach 8099 | Only 192.168.1.10 (Caddy CT) via nftables |
| Firewall: VLAN 30 to backend | BLOCKED (lab-to-gw-blocked counter active) |
| Caddy HTTPS route | `openflo-backend.home.example.com` → 192.168.1.30:8099 |

The backend is reachable only through the LAN-side Caddy reverse proxy.
VLAN 30 (lab network) cannot reach port 8099 directly — the nftables `input`
chain drops all eth1 traffic to the gateway except DHCP, DNS, and ICMP.

## 7. Existing services

| Service | Port | Status |
|---|---|---|
| Mission 006 controller | 8080 | Running (PID 18283, HTTP 200) |
| dnsmasq (VLAN 30 DNS) | 53 | Running |
| Backend emulator | 8099 | Running |

No conflicts. All three coexist on the gateway container.

## 8. Test suite

```
31 passed in 1.31s (the gateway container)
```

All tests executed against temporary SQLite databases on the deployed host.
No interaction with the production DB or the physical device.

## 9. Healthcheck endpoint

```json
{
  "status": "ok",
  "service": "openflo-device-backend",
  "version": "0.1.0",
  "firmware_version": "3.0.64",
  "safe_mode": {
    "ota": "suppressed",
    "remote_dispense": "suppressed",
    "schedule": "disabled",
    "bottle": "disabled"
  }
}
```

## Assessment

The emulator is correctly deployed, all routes respond as expected, safe-mode
invariants hold, secrets are redacted, and the service is not publicly
accessible. **Phase 1: PASS.**

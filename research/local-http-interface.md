# Local HTTP interface — iFLO device port 80

## Discovery

The iFLO device advertises two mDNS services after provisioning and firmware update:

### Service 1: `_iflo._tcp` (vendor-specific)

```
Instance: iFlo._iflo._tcp.local
Port:     80
Host:     iflo.local (192.168.30.80)
TXT:      name=iFlo
          id=D8256700000A0001
          type=standart
```

### Service 2: `_http._tcp` (standard HTTP)

```
Instance: ESP32-WebServer._http._tcp.local
Port:     80
Host:     iflo.local (192.168.30.80)
TXT:      name=iFlo
          id=D8256700000A0001
          type=STANDART
          u=user
          p=password
          board=esp32
```

Evidence: mDNS packets in the gateway capture at 14:56:40Z (service 1, pre-update firmware) and 14:57:28Z (service 1 + 2, post-update firmware). The `_http._tcp` service with the `u=/p=` credentials appeared only after the firmware update.

## HTTP testing results — 2026-10-26

All pages returned HTTP 200 **with no authentication**. The mDNS-advertised `u=user`, `p=password` credentials were not required.

### Pages

| Path | Title | Purpose |
|---|---|---|
| `/` (`/index.html`) | Connections | WiFi provisioning — scan networks, enter credentials, send config payload |
| `/ota.html` | Firmware | OTA firmware upload, password change, factory reset, reboot |
| `/settings.html` | Settings | Device info display, demo mode, no-app mode, device type, manual dispense, iFLO Plus toggle, reboot, factory reset |

### Static assets

| Path | Type |
|---|---|
| `/styles.f0a818e4.css` | Stylesheet |
| `/favicon.a359c77d.png` | Favicon |
| `/logo.caeccb57.svg` | Logo |
| `/success.3ad306c4.svg` | Success icon |

## Complete API surface

### `GET /dev_info` — device status (TESTED)

Returns JSON with full device telemetry. No authentication required.

```json
{
  "signal": 100,
  "battery": 100,
  "doses": 6,
  "bottleStatus": "OK",
  "wifiSSID": "OpenFLO",
  "floodNow": false,
  "floatEn": false,
  "firmwareVersion": "3.0.64",
  "deviceId": "D8256700000A0001",
  "extPowerState": false,
  "pcbVersion": "6.3.0",
  "deviceType": 0,
  "deviceMode": "Normal",
  "isProVersion": false,
  "demoModeVisible": false,
  "namVisible": false,
  "userDispenseVisible": true
}
```

| Field | Type | Meaning |
|---|---|---|
| `signal` | int (0–100) | WiFi signal strength % |
| `battery` | int (0–100) | Battery level % |
| `doses` | int | Dispenses remaining in cartridge |
| `bottleStatus` | string | `OK`, `EMPTY`, `MISSING`, `UNCONFIRMED` |
| `wifiSSID` | string | Connected WiFi network name |
| `floodNow` | bool | Float switch currently triggered |
| `floatEn` | bool | Float switch (iFLO Plus) enabled |
| `firmwareVersion` | string | Firmware version (currently `3.0.64`) |
| `deviceId` | string | 16-char hex device ID |
| `extPowerState` | bool | External power supply connected |
| `pcbVersion` | string | PCB hardware revision |
| `deviceType` | int | 0=Consumer HVAC, 1=PRO HVAC, 2=Mini, 3=Septic |
| `deviceMode` | string | Operating mode (`Normal`, others unknown) |
| `isProVersion` | bool | Pro hardware variant |
| `demoModeVisible` | bool | Whether demo mode toggle is shown |
| `namVisible` | bool | Whether No-App Mode toggle is shown |
| `userDispenseVisible` | bool | Whether manual dispense button is shown |

### `POST /scan_wifi` — WiFi network scan (NOT TESTED)

Triggers a scan, returns available networks.

```json
{
  "data": [
    { "name": "string", "authmode": 0, "signal": -70 }
  ]
}
```

### `POST /config` — provisioning payload (NOT TESTED)

The main provisioning endpoint. Accepts a JSON array with three config items:

```json
{
  "data": [
    { "type": "TOKEN", "data": "<one-time-token>" },
    { "type": "SERVER_CREDENTIALS", "host": "<cloud-api-url>" },
    { "type": "WIFI_CONFIG", "ssid": "<ssid>", "pass": "<password>" }
  ]
}
```

The `SERVER_CREDENTIALS.host` field is how the device learns its cloud backend URL. During normal provisioning, the app passes `https://backend.iflo.com` (or whatever Firebase Remote Config returns). **This means re-provisioning can point the device at a local server.**

URL parameters used by the app when loading the page:
- `ott` — one-time token (stored in localStorage as `__OTT__`)
- `apiUrl` — cloud API URL (stored as `__API_URL__`)
- `mode` — operation mode, e.g. `change_creds` (stored as `__MODE__`)
- `deviceType` — device type number (stored as `__DEVICE_TYPE__`)

### `POST /dev_actions` — device actions (NOT TESTED)

Multi-purpose action endpoint. Accepts different JSON payloads:

| Action | Payload | Source page |
|---|---|---|
| Reboot | `{reboot: true, restoreToDefault: false}` | settings.html |
| Factory reset | `{reboot: false, restoreToDefault: true}` | settings.html |
| Manual dispense | `{manualDispense: true, reboot: false, restoreToDefault: false}` | settings.html |
| Set device type | `{deviceType: <int>}` | index.html, settings.html |
| Toggle demo mode | `{demoMode: <bool>}` | settings.html |
| Toggle no-app mode | `{noAppMode: <bool>}` | settings.html |
| Toggle iFLO Plus | `{floatEn: <bool>}` | settings.html |

### `POST /ota` — firmware upload (NOT TESTED)

Accepts a binary firmware file via multipart form upload. Constraints from the JavaScript:
- File must be `.bin` type (MIME: `application/octet-stream` or related binary types)
- Maximum size: 2 MB (2,097,152 bytes)

### `GET /newauthpass?newpass=<password>` — change auth password (NOT TESTED)

Changes the device's authentication password. Accessed from the OTA page.

### `GET /resetdefault` — factory reset (NOT TESTED)

Resets device to factory settings. Duplicate of the `dev_actions` factory reset.

### `GET /reboot` — reboot device (NOT TESTED)

Reboots the device. Duplicate of the `dev_actions` reboot.

## Authentication

**No authentication is required.** All three pages and the `/dev_info` endpoint returned HTTP 200 without any `Authorization` header. The mDNS-advertised credentials (`u=user`, `p=password`) appear to be defaults that are not enforced — or the device accepts unauthenticated requests by default and the password is for optional use with `/newauthpass`.

## Encoding quirk

The JavaScript uses a custom encoding function (`L()` in the minified source) when sending POST payloads. It converts characters with charCode > 127 using a Cyrillic-aware transformation (subtracts 848 from charCodes > 1024, with special handling for chars 1025 and 1105). All JSON payloads are encoded to a `Uint8Array` before sending. This suggests the firmware's HTTP parser expects a specific byte encoding, not standard UTF-8, for non-ASCII characters.

## What the local interface does NOT expose

- **No schedule endpoints** — schedules are managed entirely through the cloud
- **No dispensing history** — only the remaining dose count
- **No cloud connection status** — no indication of whether the device has reached `backend.iflo.com`
- **No time synchronization** — the app's `sendCurrentTimeToFirmware` function routes through the cloud

## Key findings for local control

1. **The cloud URL is a provisioning parameter.** `POST /config` with `SERVER_CREDENTIALS.host` pointed at a local server could redirect the device's polling. This is the cleanest path to cloud-free operation.

2. **No-App Mode exists.** The `noAppMode` toggle in `/dev_actions` may enable the device to operate without cloud or app interaction. The `namVisible` field in `/dev_info` controls whether this option is shown. Currently `false` for this device — it may be firmware-gated or device-type-gated.

3. **Manual dispense is available locally.** `POST /dev_actions` with `{manualDispense: true}` triggers a dispense through the local interface. The `userDispenseVisible` field (currently `true`) controls whether this is exposed.

4. **Full device telemetry is available.** Battery, signal, doses remaining, cartridge status, firmware version, device type, and mode — all via a single `GET /dev_info` call.

5. **Device type is configurable.** The device supports four types: Consumer HVAC (0), PRO HVAC (1), Mini (2), Septic (3). Changing the type changes available options in the settings UI.

## Evidence

| Item | Retrieved | Location |
|---|---|---|
| Root page HTML (18,248 bytes) | 2026-10-26 ~15:30Z | In conversation context (full JavaScript extracted) |
| `/dev_info` JSON response | 2026-10-26 ~15:30Z | In conversation context |
| `/ota.html` source | 2026-10-26 ~15:30Z | In conversation context |
| `/settings.html` source | 2026-10-26 ~15:30Z | In conversation context |

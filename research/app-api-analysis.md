# App API analysis — iFLO 4.4.0 (com.iflo.app)

Static analysis of APK 4.4.0 (Hermes bytecode v96, Expo SDK 54, React Native). No runtime instrumentation or certificate interception was performed. The Hermes bytecode resisted full string table extraction (v96 format unsupported by available decompilers), so findings are from partial string search, DEX decompilation, mDNS capture, and network observation.

## App architecture

| Component | Detail | Status |
|---|---|---|
| Runtime | React Native with Hermes bytecode (v96) | CONFIRMED |
| Build system | Expo SDK 54 | CONFIRMED (app.config) |
| WiFi provisioning | `react-native-wifi-reborn` (Expo plugin) | CONFIRMED |
| Backend auth | Firebase Auth (`firebase/auth` module) | CONFIRMED (DEX imports) |
| Analytics | Firebase Analytics, Remote Config, Crashlytics | CONFIRMED (DNS traffic) |
| Error reporting | Sentry (`o447951.ingest.sentry.io`) | CONFIRMED (bundle string) |
| In-app support | LiveChat (`api.livechatinc.com`) | CONFIRMED (DNS traffic) |
| VPN detection | `react-native-vpn-detect` | CONFIRMED (bundle string + observed behavior) |
| QR scanning | Vision Camera + QR code scanner | CONFIRMED (DEX + cartridge scan observed) |

## Backend endpoints

| Host | Source | Role |
|---|---|---|
| `backend.iflo.com` | DNS logs (device + app), DEX string table | Device management API, firmware OTA, poll responses |
| `app.iflo.com` | DNS logs (app), DEX string table | Web/app host, deep links |
| Firebase project `iflo-61da5` | DNS logs (various `*.googleapis.com`) | Auth, Remote Config, Crashlytics, Analytics, Cloud Messaging |

**Notable:** `backend.iflo.com` and `app.iflo.com` are NOT in the Hermes string table. They are likely fetched from Firebase Remote Config at runtime, making them changeable without an app update.

## Firmware API (CONFIRMED 2026-10-26)

The consumer web app (`app.iflo.com`) is a readable Webpack bundle and exposes
the same backend contract as the mobile app. It resolves the firmware-endpoint
gap left by Hermes v96:

| Item | Value |
|---|---|
| API base | `https://backend.iflo.com/api/v1/` |
| Session storage | `localStorage["__SESSION_DATA_KEY__"] = {"accessToken":"…"}` |
| Auth header | `x-access-token: <accessToken>` (not `Authorization: Bearer`) |
| Firmware list | `GET /firmwares` — `{"data":{"firmwares":[]},"meta":{"total":42,"filteredCount":0}}` without device filters |
| Current image | `GET /firmwares/global-url` — `{"url":"https://storage.googleapis.com/iflo-firmwares-bucket/…bin","version":"3.0.64"}` |
| Firmware host | `https://storage.googleapis.com/iflo-firmwares-bucket/` |

See `research/firmware-3.0.64-acquisition.md`.

## Provisioning flow (code-derived)

The app uses `react-native-wifi-reborn` to:

1. Scan for the device's SoftAP (`connectToHotspot`, `connectToProtectedSSIDOnce`)
2. Connect to the `iFLO device` SSID (password: UNKNOWN — not found as a literal in the string table)
3. Send HTTP requests to `192.168.4.1:80` (the ESP32's default SoftAP gateway)
4. Transmit WiFi credentials (SSID + password) and likely a cloud binding token
5. Disconnect from the SoftAP
6. Reconnect to the home network and poll `backend.iflo.com` for the device to appear

**Not captured:** The actual HTTP payload during SoftAP handoff. PCAPdroid's VPN mode prevented capture (the app blocks pairing with a VPN active). The address `192.168.4.1` does not appear as a literal in either the Hermes bundle or the DEX files — it is likely derived from the network gateway address when connected to the SoftAP, or hardcoded in the WiFi reborn native module.

## Device communication patterns (code-derived)

| Function/symbol | Location | Likely purpose |
|---|---|---|
| `sendCurrentTimeToFirmware` | Hermes bundle | Time synchronization with the device (post-provisioning, via cloud) |
| `ota_update` / `OTA_UPDATE` | Hermes bundle | Firmware update handling |
| `getDeviceInfo` | Hermes bundle | Device information retrieval (may be React Native's own DeviceInfo) |
| `getSchedule` | Hermes bundle | Schedule readback (may be React Native's LocalNotifications, not iFLO-specific) |
| `connectToHotspot` | Hermes bundle | WiFi reborn SoftAP connection |
| `connectToProtectedSSIDOnce` | Hermes bundle | WiFi reborn SSID connection with credentials |
| `X_DEVICE_IP` | DEX (classes2.dex) | HTTP header for device IP address |

**Caveat:** Many of these symbol names are from the Hermes identifier table, which interleaves iFLO-specific names with framework identifiers. Without full decompilation, it is not possible to confirm which are iFLO business logic vs. library code.

## What the app does NOT do post-setup

After provisioning, the app **never contacts the device directly on the local network** (CONFIRMED from the full gateway capture session). All post-setup interaction routes through `backend.iflo.com`:

- Schedule changes → app → cloud → device polls cloud
- Cartridge validation → app → cloud (QR code verified server-side)
- Dispense commands → app → cloud → device polls cloud
- Device status → device → cloud → app

The device's mDNS-advertised HTTP server on port 80 is **not used by the app** after provisioning.

## Security observations

1. **No certificate pinning.** The app does not include a `networkSecurityConfig` and sets `usesCleartextTraffic=true`. It trusts the system CA store only.
2. **Embedded third-party webhook.** A Slack incoming-webhook URL was found in the app's string resources. Not tested. Consider responsible disclosure.
3. **SoftAP provisioning is cleartext HTTP** (port 80, LIKELY). WiFi credentials are transmitted in the clear during setup.
4. **VPN detection as security.** The app refuses to pair while a VPN is active, likely to prevent the provisioning HTTP traffic from being captured. This is obfuscation, not security.

## Hermes bytecode limitations

The Hermes v96 bytecode format is not supported by `hbctool` (the primary open-source HBC parser). The string table uses a compact encoding with interleaved identifier hashes, making simple `strings` extraction unreliable. A proper disassembler for v96 would reveal:

- The exact SoftAP HTTP endpoints and request/response schemas
- The cloud API paths and authentication flow
- Whether the app has any code for local device control post-setup
- The firmware update validation logic

This is the highest-value remaining static analysis task.

**Update (2026-10-26):** the web bundle provided the firmware API paths and the
`x-access-token` header; the stock 3.0.64 image provides the device-side OTA and
cloud strings. Hermes v96 remains relevant for mobile-only logic, not for the
firmware API contract.

## Evidence

| Item | Location |
|---|---|
| Extracted APK (base + splits) | `~/openflo-private/apk/` |
| Hermes bundle | `~/openflo-private/apk/x.hq9t/assets/index.android.bundle` |
| DEX files | `~/openflo-private/apk/x.hq9t/classes{,2,3}.dex` |
| App config | `~/openflo-private/apk/x.hq9t/assets/app.config` |
| PCAPdroid captures | `~/openflo-private/phone/PCAPdroid/` |
| Gateway capture | the gateway container `/var/lib/openflo/captures/20261026T144415Z_first-provision/` |
| Official firmware image | `artifacts/firmware/iflo-3.0.64.bin` |
| Firmware acquisition notes | `research/firmware-3.0.64-acquisition.md` |

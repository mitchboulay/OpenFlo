# Cloud endpoints

Observed 2026-10-26 (UTC). Only DNS names, IPs, ports and TLS metadata are recorded. No payloads were decrypted. No endpoint was probed, scanned or contacted by us.

## Device (iFLO, 192.168.30.80)

| Host | Resolved IP | Port / proto | Purpose | Status | Evidence |
|---|---|---|---|---|---|
| `backend.iflo.com` | 34.120.139.126 (Google Cloud address space; one IP) | 443/TCP, TLS 1.2 | All device ↔ cloud traffic: setup calls, firmware download, polling | CONFIRMED | dnsmasq log, gateway pcap streams 65–100+ |
| `pool.ntp.org` | various | 123/UDP | Time sync after each Wi-Fi join | CONFIRMED | dnsmasq + pcap |
| `google.com` | 173.194.210.x | DNS only (no connection seen) | LIKELY a DNS-based internet check after joining | CONFIRMED query / LIKELY purpose | dnsmasq 14:57:29, 15:01:41 |
| mDNS `224.0.0.251:5353` | local | UDP | Announces `iFlo._iflo._tcp.local` and `ESP32-WebServer._http._tcp.local`, both port 80 | CONFIRMED | pcap |

Nothing else. No MQTT (1883/8883), no WebSocket upgrade visible, no plaintext HTTP to the internet, no other hostnames.

## App (`com.iflo.app` on the Pixel)

| Host | Purpose | Status | Evidence |
|---|---|---|---|
| `backend.iflo.com` | Same backend as the device | CONFIRMED | Gateway DNS 14:47:16, Pi-hole 14:57:23/14:58:26, PCAPdroid SNI 14:47:16, 14:58:26, 15:00:46 |
| `app.iflo.com` | Web/app host, also declared as an app link in resources | CONFIRMED | DNS + SNI 14:47:10, 14:58:50, 15:00:44 |
| `firebaseinstallations.googleapis.com`, `firebaseremoteconfig.googleapis.com`, `firebase-settings.crashlytics.com`, `firebaselogging*.googleapis.com`, `app-measurement.com` | Firebase project `iflo-61da5` (Installations, Remote Config, Crashlytics, Analytics) | CONFIRMED | DNS 14:47:09–10 |
| Firebase Auth / Cloud Messaging | Present in the app (modules `firebase/auth`, `firebase/messaging`). No auth hostname seen on OpenFLO during sign-in (sign-in may have happened on the home Wi-Fi) | CONFIRMED present / UNKNOWN timing | dex |
| `*.ingest.sentry.io` | Error reporting | CONFIRMED | DNS 14:47:10 |
| `api.livechatinc.com`, `cdn.livechatinc.com`, `secure.livechatinc.com` | In-app support chat | CONFIRMED | DNS / SNI |
| `192.168.4.1:80` | The device's own hotspot during setup (HTTP) | CONFIRMED attempts | PCAPdroid |

## TLS properties (`backend.iflo.com`)

| Property | Value | Status |
|---|---|---|
| Server certificate | `CN=backend.iflo.com`, issuer Google Trust Services WR3 → GTS Root R1 (cross-signed by GlobalSign Root CA) | CONFIRMED |
| Negotiated | TLS 1.2, `TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256` (0xc02f) | CONFIRMED |
| Device SNI | **None sent.** The server answers with the `backend.iflo.com` certificate regardless | CONFIRMED |
| Device ALPN | None (so HTTP/1.1 over TLS, LIKELY) | CONFIRMED absent |
| Device TLS 1.3 | Not offered (no `supported_versions`) | CONFIRMED |
| Device fingerprint A (setup firmware) | record 0x0301, 49 suites incl. DHE/CCM/PSK families | CONFIRMED |
| Device fingerprint B (after update) | record 0x0303, ~55 suites incl. ARIA/CAMELLIA families | CONFIRMED |
| Does the device validate the server certificate (and against which CA)? | UNKNOWN | Needs a controlled test (Mission 004+) |

## Vendor secret exposure (redacted)

The app package embeds a third-party incoming-webhook credential (a Slack URL) in its string resources. It was not used or tested. The value is kept only in the private APK copy. Consider responsible disclosure to the vendor.

## Device API (CONFIRMED 2026-10-26)

The device polls `POST <host>/device-api/v2/<endpoint>` with JSON bodies,
`Accept: */*`, `Content-Type: application/json`, `Accept-Encoding: gzip, deflate,
br`, and a device header (`x-device-id`, or `x-device-ott` for registration).
TLS validation is enabled with the ESP-IDF `esp-x509-crt-bundle` CA bundle.

| Endpoint | Body / purpose |
|---|---|
| `register` | `{"deviceId": ...}` + `x-device-ott`; 200/422. |
| `update-device` | telemetry JSON; returns schedule/settings/remote-dispense/OTA state. |
| `get-fw` | `{"firmwareVersion": ..., "deviceId": ...}`; returns `actualFirmwareVersion` / `url.redirectLocation`. |
| `get-bottle` | empty; bottle status/doses. |
| `get-schedule` | empty; schedule list, persisted as `schedule.txt`. |
| `healthcheck` | `{"deviceId": ...}`. |
| `send-events` | event JSON. |
| `create-qc-report` | device/QC info. |

See `research/rea-firmware-analysis.md`.

## Firmware distribution (CONFIRMED 2026-10-26)

`GET https://backend.iflo.com/api/v1/firmwares/global-url` (header
`x-access-token`) returns the current global image. The GCS object is readable
without auth once the URL is known; anonymous bucket listing is denied (`403`),
so the API remains the index.

| Field | Value |
|---|---|
| Version | `3.0.64` |
| URL | `https://storage.googleapis.com/<vendor-bucket>/<object>.bin` |
| Size | 1,309,376 bytes |
| SHA-256 | `3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2` |
| Build | ESP-IDF `v5.3.2-dirty`, 2026-02-09 |

This is distinct from the public `iflo-static` bucket, which holds media and
training assets only. See `research/firmware-3.0.64-acquisition.md`.

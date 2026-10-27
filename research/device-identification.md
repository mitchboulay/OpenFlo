# Device identification

Sources: operator photos (`~/openflo-private/photos/`, private), Wi-Fi scan from the Pixel, gateway DHCP/mDNS capture, the iFLO Android app package. Device identifiers are partly redacted here; full values are in the private evidence.

| Attribute | Value | Status | Evidence |
|---|---|---|---|
| Product | iFLO Smart Automated A/C Drain Line & Drain Pan Cleaning System | CONFIRMED | Box (IMG_3753) |
| Model / item no. | `IFLOKIT01` | CONFIRMED | Device label + box (IMG_3755, IMG_3754) |
| Manufacturer | Great Innovations, LLC, Miramar FL (©2024). Cartridge ©2025 iFLO, LLC. Assembled in China | CONFIRMED | Box, cartridge label |
| Power | 4 × 1.5 V AA alkaline | CONFIRMED | Device label |
| Date code / PCB code | `MX5224` / `P601` | CONFIRMED | Device label |
| FCC ID | **None printed.** FCC logo only (suggests SDoC, or an FCC-certified module ID inside the enclosure) | CONFIRMED absent on label | Device label |
| Per-device QR on label | Present (contents not decoded or published) | CONFIRMED | Device label |
| Patents | US 11,761,675 B1; 11,719,464 B1; 11,654,462 B1; 11,826,799 B2; 12,031,745 B2; 12,030,097 B2 | CONFIRMED | Box |
| Cartridge | Model `IFLO36PF`, 36 fl oz primer & flush, labelled "Not Intended for Retail Sale" | CONFIRMED | IMG_3757 |
| Wi-Fi chipset vendor | **Espressif** (OUI `68:67:25`) | CONFIRMED | SoftAP BSSID, station MAC |
| SoC family | **ESP32-S2** | CONFIRMED | Official 3.0.64 image header: `chip_id=2`; mDNS TXT `board=esp32`, mDNS service `ESP32-WebServer._http._tcp` |
| Station MAC | `68:67:25:xx:xx:01` (SoftAP BSSID = station MAC + 1, the Espressif default) | CONFIRMED | DHCP + scan |
| DHCP hostname | `espressif` in setup firmware, then `iFlo` after the update | CONFIRMED | dnsmasq log 14:56:36 / 14:57:27 |
| Setup hotspot | SSID `iFLO device`, 2.412 GHz (ch 1), WPA/WPA2-PSK mixed (TKIP+CCMP), so it has a password | CONFIRMED | `cmd wifi list-scan-results` 14:51Z |
| Device ID | 16 hex chars in mDNS TXT `id=` (redacted) | CONFIRMED | mDNS 14:56:42 |
| Firmware framework | **ESP-IDF v5.3.2** with mbedTLS | CONFIRMED | Official 3.0.64 image `esp_app_desc`: `idf=v5.3.2-dirty`; embedded ESP-IDF web UI |
| Stock firmware | 3.0.64 (`20251201_3.0.64`), built 2026-02-09 18:32:28 | CONFIRMED | `esp_app_desc`; SHA-256 `3b1df98a…a40f2`; see `research/firmware-3.0.64-acquisition.md` |
| Radio | 2.4 GHz only (ESP32) | LIKELY | Chipset; app instructions |

## Lights (vendor KB)

| LED | Meaning |
|---|---|
| Green blinking slowly | A user (phone) is connected to the device's hotspot |
| Green solid | Successful communication with the iFLO server |
| Blue blinking slowly | Wi-Fi pairing mode |
| Blue solid | Connected to Wi-Fi |
| Yellow | Battery level; blinking = replace batteries |

After setup the lights switch off in "battery-saving mode" and wake for a dispense, a low battery or an empty bottle ([KB](https://iflo.onsitesupport.io/knowledge-base/article/why-do-my-iflow-lights-shut-off-after-setup-and-installation)).

## Mobile app

| Attribute | Value | Status |
|---|---|---|
| Android package | `com.iflo.app` 4.4.0 (versionCode 47), minSdk 26, targetSdk 36, from Google Play | CONFIRMED (`dumpsys package`) |
| Framework | React Native (Hermes bytecode v96) on Expo SDK 54 | CONFIRMED (`app.config`, native libs) |
| Related app | `com.iflo.pro` (iFLO PRO, professional model), not analysed | CONFIRMED (Play search) |
| APK hashes | base `f4966c80…d51ef6`, arm64 split `7396862a…a747f663f` (full values in `~/openflo-private/apk/`) | CONFIRMED |

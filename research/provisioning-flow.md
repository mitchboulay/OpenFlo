# Provisioning flow

## Mechanism: SoftAP over plain HTTP

| Claim | Status | Evidence |
|---|---|---|
| No BLE involved | CONFIRMED | Manifest declares no Bluetooth permission or feature |
| The device opens its own hotspot `iFLO device` (WPA/WPA2-PSK, ch 1) on power-up | CONFIRMED | Pixel Wi-Fi scan 14:51Z, BSSID `68:67:25:xx:xx:02` |
| The app joins that hotspot programmatically | CONFIRMED | `react-native-wifi-reborn` (Expo plugin in `app.config`), bundle symbols `connectToProtectedSSIDOnce`, `connectToHotspot`, `disconnectFromSSID`, `invalidSSIDPrefix`, `CHANGE_WIFI_STATE` + location permissions |
| The app then speaks HTTP to `192.168.4.1:80` (the default Espressif hotspot address) | CONFIRMED (connection attempts) | PCAPdroid file 1: TCP SYNs to `192.168.4.1:80` at 14:53:54, 14:54:30 and 14:54:53Z |
| The handoff is cleartext HTTP | LIKELY | Port 80 plus `usesCleartextTraffic=true`. No payload captured (see below) |
| The app refuses to pair while any VPN is active | CONFIRMED | "Check VPN Status" screen. Bundle symbols `react-native-vpn-detect`, `checkIsVpnConnected`, `vpnStateDidChange` |
| The hotspot password is hard-coded in the app or derived from a device property | UNKNOWN | Not yet found in the Hermes string table. Needs a Hermes disassembler |
| HTTP paths and payload of the handoff (SSID, PSK, account/cloud token?) | UNKNOWN | Not captured. Mission 004 static analysis |

**Blind spot:** PCAPdroid's VPN routed the hotspot-bound SYNs into a tunnel the hotspot couldn't answer, which is also why the app blocks VPNs. With PCAPdroid stopped, the phone ↔ iFLO exchange over the iFLO's own hotspot wasn't observable from any vantage point we have. The gateway only sees traffic once the iFLO joins OpenFLO.

## Observed sequence (UTC, 2026-10-26)

See `event-timeline.md` for the full timeline.

1. Batteries in. The device advertises `iFLO device` (seen 14:51).
2. The app (on OpenFLO, then on the home Wi-Fi after the hotspot step) signs the user in through Firebase and contacts `app.iflo.com` / `backend.iflo.com`.
3. The app joins the hotspot and attempts HTTP to `192.168.4.1:80`. The handoff completes once the VPN is off (~14:55–14:56; not captured).
4. **14:56:36:** the device joins OpenFLO as hostname `espressif` (setup firmware), lease 192.168.30.80, and announces mDNS `_iflo._tcp` on port 80.
5. **14:56:40–14:56:44:** four HTTPS connections to `backend.iflo.com` (TLS fingerprint A), then **one 1.39 MB download over 32 s** (14:56:44–14:57:16).
6. **14:57:27:** the device re-joins with hostname `iFlo` and a different TLS fingerprint (B). It now also advertises `ESP32-WebServer._http._tcp` on port 80. The download was LIKELY a firmware image applied by OTA during setup.
7. 14:57:23: the app (home Wi-Fi, via the LAN resolver) queries `backend.iflo.com`. It LIKELY polls the cloud for the device coming online. The app reports pairing success.
8. 14:57:29–14:58:21: the device makes HTTPS calls every ~5–8 s, then goes silent.
9. **~15:00:44:** cartridge QR scanned. The app contacts `app.iflo.com` + `backend.iflo.com` (PCAPdroid file 2). The device wakes at **15:01:42** and polls again (15:01:42–15:04:45, ~2–23 s apart), covering cartridge confirmation and physical install.
10. Setup complete. Dispense and schedule were offered and **not used**. From 15:04:45 the device sends nothing (no ARP), so its Wi-Fi is LIKELY powered down.

## Implications

- The device learns its Wi-Fi credentials, and LIKELY its cloud binding, from a local plain-HTTP exchange. A local provisioning tool could repeat that exchange without the vendor app, once the endpoint and any token in it are known from the app code.
- Firmware update happens silently during setup. Later firmware may change behaviour, so keep WAN control in mind (Mission 004 decision).

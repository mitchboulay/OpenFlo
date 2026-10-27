# Event timeline: first contact (2026-10-26, UTC)

Clock sources: the gateway (the gateway container, UTC, NTP via the host), PCAPdroid (phone clock), Pi-hole (UTC). Operator-reported times are approximate.

| Time (UTC) | Source | Event |
|---|---|---|
| 14:10–14:24 | gateway | Phase 0: capture script fixed and retested (9 sessions clean), test sessions deleted |
| 14:44:07 | gateway | Revalidation: Pixel on OpenFLO (192.168.30.67), DNS logging, internet, isolation counter 12 → 21 |
| 14:44:15 | gateway | **Capture `first-provision` started.** Recording verified (27 pkts / 8 s) |
| 14:44:28 | gateway | T0 marker before power-on |
| 14:46:10 | PCAPdroid | PCAPdroid session 1 starts (all apps, no TLS decryption) |
| ~14:46–14:51 | operator | Batteries inserted (power-on) |
| 14:47:09–14:47:16 | gateway DNS | App start: Firebase Installations/Remote Config/Crashlytics/Analytics, Sentry, LiveChat, `app.iflo.com` (14:47:10), `backend.iflo.com` (14:47:16) |
| 14:51:17 | Pixel scan | Device hotspot `iFLO device` visible, BSSID `68:67:25:xx:xx:02`, ch 1, −28 dBm |
| ~14:52 | operator | **Checkpoint 2: pairing approved** |
| 14:53:54–14:54:56 | PCAPdroid | App → `192.168.4.1:80` SYNs (3 attempts) through the VPN, unanswered |
| ~14:54 | operator | App: "Check VPN Status – VPN must be turned off". PCAPdroid stopped (session 1 ends 14:54:56) |
| 14:54:59 | gateway DNS | App resolves `backend.iflo.com` |
| ~14:55–14:56 | (not captured) | App ↔ device HTTP handoff over the device's hotspot; operator selects OpenFLO |
| 14:56:36 | gateway DHCP | **Device joins OpenFLO**: `68:67:25:xx:xx:01`, hostname `espressif`, lease 192.168.30.80 |
| 14:56:40 | gateway | DNS `backend.iflo.com`. mDNS announce `_iflo._tcp` :80 |
| 14:56:40–14:56:44 | gateway | 4 short HTTPS connections (TLS fingerprint A) |
| 14:56:44–14:57:16 | gateway | **1.39 MB download** over one HTTPS connection (LIKELY firmware; **confirmed 3.0.64** — see post-analysis note) |
| 14:56:45 | gateway | NTP `pool.ntp.org` |
| 14:57:23 | Pi-hole | App (phone now on the home Wi-Fi) queries `backend.iflo.com` |
| 14:57:27 | gateway DHCP | **Device re-joins, hostname `iFlo`** (post-update firmware) |
| 14:57:28 | gateway | mDNS adds `ESP32-WebServer._http._tcp` :80, TXT `board=esp32` |
| 14:57:29 | gateway | DNS `google.com`, `backend.iflo.com`. HTTPS polling begins (fingerprint B) |
| ~14:57–14:58 | operator | App shows **paired successfully** |
| 14:58:21 | gateway | Last connection of burst 1 (9 connections, 5–8 s apart) |
| 14:58:25 | PCAPdroid | PCAPdroid session 2 starts (operator restarted it) |
| 14:58:26 / 14:58:50 | PCAPdroid, Pi-hole | App → `backend.iflo.com` / `app.iflo.com` |
| ~15:00 | operator | **Checkpoint 3: cartridge approved** |
| 15:00:44–15:00:46 | PCAPdroid, Pi-hole | **Cartridge QR scan**: app → `app.iflo.com`, `backend.iflo.com` |
| 15:01:41–15:01:42 | gateway | Device wakes: DNS `google.com`, `backend.iflo.com`, NTP. HTTPS burst 2 begins |
| ~15:02 | operator | App: cartridge confirmed, asks to install cartridge. Phone still on the home Wi-Fi |
| 15:02:30 | gateway | Device polling (11 connections by 15:04:19) |
| 15:03:04 | gateway | Pixel back on OpenFLO |
| ~15:03–15:04 | operator | Cartridge physically installed |
| 15:04:45 | gateway | **Last device frame.** Silent afterwards (no ARP/DHCP) |
| ~15:05 | operator | App: setup complete. Dispense / schedule offered; **not used** |
| ~15:06 | operator | App exited |
| 15:07:21 | analyst | Snapshot of the gateway session copied to `~/openflo-private/captures/` |
| 15:07:32 | PCAPdroid | Session 2 ends (pulled over ADB) |
| ongoing | gateway | Capture continues as the long-term baseline (same session, hourly files) |

## Post-analysis confirmation (2026-10-26)

The 1.39 MB transfer at 14:56:44–14:57:16 was the stock **v3.0.64** update.
The vendor image is 1,309,376 bytes; the difference is consistent with
TLS/record overhead. Its `esp_app_desc` version matches the post-update `/dev_info`
value (`firmwareVersion: 3.0.64`).

Evidence: `artifacts/firmware/iflo-3.0.64.bin`, SHA-256
`3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2`; see
`research/firmware-3.0.64-acquisition.md`.

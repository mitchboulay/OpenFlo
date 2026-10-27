# Protocol analysis

Evidence: gateway session `20261026T144415Z_first-provision` (still running as the baseline; snapshot `~/openflo-private/captures/first-provision-snapshot-20261026T150721Z.tar`), the dnsmasq log slice, PCAPdroid files `PCAPdroid_26_Oct_10_46_10.pcap` and `PCAPdroid_26_Oct_10_58_25.pcap` (`~/openflo-private/phone/`), the Pi-hole query log (read-only), and static reads of APK 4.4.0. Nothing was decrypted. Every conclusion is labelled.

## Answers

| Question | Answer | Status |
|---|---|---|
| Device MAC / IP | `68:67:25:xx:xx:01` / 192.168.30.80 (lab DHCP) | CONFIRMED |
| Manufacturer / chipset | Espressif ESP32 | CONFIRMED |
| DNS hostnames used by the device | `backend.iflo.com`, `pool.ntp.org`, `google.com` | CONFIRMED |
| Destinations / ports | 34.120.139.126:443/TCP; NTP servers :123/UDP; mDNS | CONFIRMED |
| Application protocol | HTTPS (TLS 1.2, no ALPN) | CONFIRMED |
| HTTP/1.1 request–response over TLS (REST-style) | Short-lived connections, one TLS handshake each, ~1.3–1.7 KB up / ~5.7–6.5 KB down, closed within ~1 s, no keep-alive | LIKELY |
| MQTT / WebSocket / CoAP / plaintext | None observed | CONFIRMED (for this session) |
| TLS version / handshake | TLS 1.2 only, no SNI, server picks ECDHE-RSA-AES128-GCM-SHA256. Two client fingerprints, before and after the update | CONFIRMED |
| Who initiates | **The device, always.** Zero inbound SYNs to the device from WAN or LAN in the whole session | CONFIRMED |
| Push vs poll | **Polled.** The device only talks while awake, in bursts of requests 2–23 s apart. The cloud never connects in. Commands/config LIKELY ride on poll responses | CONFIRMED (no inbound path) / LIKELY (payload role) |
| Heartbeat / wake interval | Awake bursts: 14:57:29–14:58:21, 15:01:42–15:04:45. Gap of 201 s between them, possibly triggered by the cartridge-scan interaction (15:00:44), not a timer. Long-term sleep interval: not yet observed | UNKNOWN (needs baseline) |
| Sleep behaviour | After 15:04:45, no frames at all (no ARP, no DHCP renew, neighbour entry expired), so Wi-Fi is off between wakes | LIKELY |
| Firmware update during setup | 1.39 MB single-stream download at 14:56:44–14:57:16, then rejoin with a new hostname, new TLS stack and new mDNS services | LIKELY OTA |
| Does the app talk directly to the device? | Only during setup, over the device's own hotspot (`192.168.4.1:80`). On OpenFLO the app never contacted 192.168.30.80. The app ↔ device relationship after setup runs through `backend.iflo.com` | CONFIRMED |
| Local server on the device | Advertised: `_iflo._tcp` and `_http._tcp` (`ESP32-WebServer`) on port 80, TXT `name`, `id`, `type=STANDART`, `board=esp32`, plus `u=`/`p=` keys (values redacted). Never contacted by us or the app | CONFIRMED advertised / UNKNOWN function |
| Needs the cloud for ordinary operation? | Setup, cartridge validation and schedule configuration all route through the cloud/app. Whether a configured device dispenses on its local schedule with WAN blocked is untested | LIKELY for config / UNKNOWN for dispensing |

## Correlation: app action → device traffic

| App / operator action (source) | Device response (gateway) |
|---|---|
| Hotspot handoff, ~14:55–14:56 (inferred; not captured) | 14:56:36 joins OpenFLO, setup calls + firmware download |
| App polls `backend.iflo.com` 14:57:23 (Pi-hole) | Device back online 14:57:27–29 after reboot. App shows "paired" |
| Cartridge QR scan, app → `app.iflo.com`/`backend.iflo.com` 15:00:44–46 (PCAPdroid) | Device wakes 15:01:42 (+56 s) and polls. The wake trigger may be the operator handling the device or inserting the cartridge, not the cloud (the cloud has no inbound path) |
| Cartridge physically inserted (~15:02–15:04, operator) | Burst 15:03:33–15:04:45 |
| Exit app ~15:06 | Device already silent since 15:04:45 |

## What would change these conclusions

- A 24–48 h baseline shows the timer-driven wake interval and what a scheduled dispense looks like on the wire.
- Hermes disassembly of the app shows the setup HTTP endpoints and fields, and LIKELY the REST paths on `backend.iflo.com`, and confirms or refutes "commands ride on poll responses".

# Firmware 3.0.64 acquisition and image analysis

Date: 2026-10-26. Status: **COMPLETE** — official stock image acquired, verified
and stored locally. No device was flashed or reconfigured during this work.

## Executive summary

The stock iFLO firmware v3.0.64, previously treated as unavailable, has been
obtained from the vendor's production firmware API using an authenticated
consumer web session, downloaded from the vendor GCS bucket, and verified
against its ESP-IDF application descriptor.

| Property | Value |
|---|---|
| File | `artifacts/firmware/iflo-3.0.64.bin` |
| Size | 1,309,376 bytes |
| SHA-256 | `3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2` |
| Version string | `20251201_3.0.64` |
| Project | `iFlo` |
| Target | ESP32-S2 (`chip_id=2`), 8 segments, entry `0x40025284` |
| Framework | ESP-IDF `v5.3.2-dirty` |
| Built | 2026-02-09 18:32:28 |
| Image type | App-only image, flashed at `0x10000` |

This also confirms that the 1.39 MB HTTPS transfer observed at 14:56:44 in the
first-provision capture was the stock firmware update, not an unrelated
download.

## 1. Acquisition path

The firmware API is authenticated; it is not a public download page.

### 1.1 Web app, not the Hermes bundle

`app.iflo.com` is a readable Webpack bundle and exposes the same backend
contract as the mobile app. Its `config.js` sets:

```js
apiUrl: "https://backend.iflo.com"
apiPrefix: "/api/v1/"
firmwareApiUrl: "http://192.168.4.1"
cloudStaticBucketUrl: "https://storage.googleapis.com/iflo-static"
```

The web session is stored in `localStorage` under `__SESSION_DATA_KEY__` as
`{"accessToken":"…"}`. The API client sends it as **`x-access-token`**, not
`Authorization: Bearer` (CONFIRMED from the bundle's request builder).

### 1.2 Endpoint behaviour

With a logged-in consumer session:

| Request | Result |
|---|---|
| `GET /api/v1/firmwares` | `200` — `{"data":{"firmwares":[]},"meta":{"total":42,"filteredCount":0}}` |
| `GET /api/v1/firmwares/global-url` | `200` — current global image |

`meta.total = 42` is likely the unfiltered firmware-record count (INFERRED);
the list is empty because no device/version filters were supplied. The
`global-url` endpoint is the one that returns the current image.

Response:

```json
{
  "url": "https://storage.googleapis.com/<vendor-bucket>/<object>.bin",
  "version": "3.0.64"
}
```

The GCS object itself is readable without authentication once the URL is known
(`HTTP 200`, `application/octet-stream`, 1,309,376 bytes). The bucket is not
discoverable by name; the API is the index. The session token was used only for
the API call and is not stored in this repository.

## 2. Image verification

`esp_app_desc` at file offset `0x20`:

| Field | Value |
|---|---|
| Magic | `0xABCD5432` |
| Project | `iFlo` |
| Version | `20251201_3.0.64` |
| Build date/time | `Feb  9 2026 18:32:28` |
| IDF version | `v5.3.2-dirty` |
| Secure version | `0` |

ESP image header:

| Field | Value |
|---|---|
| Magic | `0xE9` |
| Segments | `8` |
| SPI mode / speed-size | `0x02` / `0x2F` |
| Entry point | `0x40025284` |
| Chip ID | `2` (**ESP32-S2**) |
| WP pin | `0xEE` |
| Min chip rev | `0` |
| SHA-256 appended | `1` |

### Segments

| # | Load address | Length | File offset |
|---|---|---|---|
| 0 | `0x3f000020` | 358,260 | `0x20` |
| 1 | `0x3ff9e060` | 4 | `0x5779c` |
| 2 | `0x3ffc4720` | 15,924 | `0x577a8` |
| 3 | `0x40024000` | 18,996 | `0x5b5e4` |
| 4 | `0x40080020` | 867,544 | `0x60020` |
| 5 | `0x40028a34` | 48,364 | `0x133d00` |
| 6 | `0x40070000` | 96 | `0x13f9f4` |
| 7 | `0x50001000` | 64 | `0x13fa5c` |

The image is **not** a full flash dump: it contains no bootloader, partition
table or NVS. Writing it to a device means writing at `0x10000` behind the
device's existing bootloader and partition table.

## 3. What the image contains

### 3.1 Embedded local web UI

The stock image embeds the device's SoftAP web application in rodata:

| Page | Purpose |
|---|---|
| `/index.html` | Wi-Fi scan, credential entry, `POST /config` provisioning |
| `/settings.html` | Device info, reboot, factory reset, manual dispense, No-App Mode |
| `/ota.html` | Local firmware upload, current version display |

Device endpoints referenced by the embedded JavaScript:

- `GET /dev_info`
- `POST /dev_actions`
- `POST /scan_wifi`
- `POST /config`
- `POST /ota`
- `GET /resetdefault`
- `GET /reboot`
- `GET /newauthpass?newpass=…`

The local OTA page enforces a **2,097,152-byte** upload limit and expects a
`.bin` file with a binary MIME type.

### 3.2 Cloud and OTA strings

Notable strings in the image (observed, not yet traced to functions):

- `https://backend.iflo.com`
- `Set_OTA_file_ulr` (sic)
- `SAPI_device_info`, `Stop_sync_mode`
- `Firmware update fail! This device does not support firmware versions below 2.20.5 !`
- `Firmware update fail! Current level is same as loaded!`
- `Firmware not fit partition`
- `ESP_HTTPS_OTA_*` event/error family
- `EE_OTA_CANCEL_CAUSE_*` (`LOW_BATTERY`, `LOW_WIFI_LEVEL`,
  `IMAGE_IS_CORRUPTED`, `VERSION_UNSUPPORTED`, `TIMEOUT`, …)

These indicate the stock firmware performs **HTTPS OTA**, has a version floor
(2.20.5), checks partition fit, and reports OTA cancellation causes. They are
direct evidence for the update path already inferred from the capture.

## 4. Correlation with existing evidence

| Prior observation | Confirmation |
|---|---|
| 14:56:44–14:57:16: 1.39 MB HTTPS download from `backend.iflo.com` during provisioning (`event-timeline.md`) | Stock image is 1,309,376 bytes; the difference is consistent with TLS/record overhead. Confirmed firmware download. |
| Post-update DHCP hostname changes to `iFlo`; mDNS adds `ESP32-WebServer._http._tcp` | ESP-IDF app with embedded web server; consistent with the image. |
| `/dev_info` reports `firmwareVersion: 3.0.64` | Matches `esp_app_desc` version. |
| SoC identified as ESP32 family from mDNS/OUI | Image header gives `chip_id=2` (**ESP32-S2**), and the device is a 4 MB ESP32-S2-SOLO. |
| App stores the API URL via Firebase Remote Config / provisioning | Image contains `https://backend.iflo.com`; provisioning web page receives `apiUrl` and posts it as `SERVER_CREDENTIALS.host`. |

## 5. What this unlocks

The stock image turns several previously black-box questions into static
analysis tasks. The most valuable are:

1. **TLS validation.** Inspect `esp_tls` / `esp_http_client` configuration and
   the embedded CA bundle. This answers the highest-impact unknown in
   `original-firmware-feasibility.md` (does the device validate
   `backend.iflo.com`?).
2. **Cloud polling protocol.** Recover URL paths, HTTP methods, headers and
   JSON keys from rodata and Xtensa disassembly. This replaces the DNS/TLS-only
   observations in `protocol-analysis.md` and `cloud-endpoints.md`.
3. **Scheduling and No-App Mode.** Locate the schedule state machine and the
   `noAppMode` handling to determine whether No-App Mode can provide local
   scheduling (`mission-006-proposal.md`, Experiment 1).
4. **OTA policy.** Identify the version floor, partition-fit checks, image
   validation and whether signatures are verified.
5. **Version inventory.** Query `/firmwares` with the correct device filters to
   enumerate the 42 records and retrieve older/newer images for comparison.

## 6. Limitations and unknowns

- **App-only image.** Bootloader, partition table and NVS are not included. A
  full flash dump is still the only way to inspect those.
- **No runtime testing.** Nothing was flashed, and no POST was sent to the
  device.
- **No TLS decryption.** The API call was authenticated at the HTTP layer; the
  device's own cloud traffic was not decrypted.
- **Raw image is not ELF.** It must be mapped by segment into an Xtensa-aware
  disassembler; generic ELF tools and REA's generic `open_binary` path reject
  it.
- **Authenticated acquisition.** The image is not a public download; the API
  requires a consumer session. Do not redistribute the binary.
- **Version semantics.** `20251201_3.0.64` looks like a release/branch date
  prefix (2025-12-01) while the build date is 2026-02-09. The exact meaning is
  not documented.

## 7. Artifact inventory

| Path | Size | SHA-256 |
|---|---:|---|
| `artifacts/firmware/iflo-3.0.64.bin` | 1,309,376 | `3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2` |
| `artifacts/firmware/iflo-esphome-2026.9.1.factory.bin` | 988,448 | `b7fae3d52f00c96624272dc2ef85262ca24e1a40c044ec8dae74eaf689980872` |
| `artifacts/apk/base.apk` | 31,216,876 | `f4966c80e9ad8a3cdfa4d9bf67b8b5203d1cd4287983dca2c481215bd6d51ef6` |
| `artifacts/apk/split_config.arm64_v8a.apk` | 16,762,956 | `7396862a88a66818a0785bce6cb400eb68a6ed81b5fbe284084e3b9a747f663f` |
| `artifacts/captures/PCAPdroid_26_Oct_10_46_10.pcap` | 35,254,137 | `a83a14fcab090c59557e65bb38291e6b0945f2e47e5705b0660a3638f711a506` |

`SHA256SUMS` in each artifact subdirectory is the tracked integrity manifest.
The binaries are ignored by `.gitignore`; see `artifacts/README.md`.

## 8. Reproduction

1. Sign in to `https://app.iflo.com` with the iFLO account (phone + OTP).
2. Read `localStorage["__SESSION_DATA_KEY__"].accessToken` in the page context.
3. Request the current image:
   ```bash
   curl -s https://backend.iflo.com/api/v1/firmwares/global-url \
     -H "x-access-token: $IFLO_TOKEN"
   ```
4. Parse `data.url` / `data.version`, download the object, and verify:
   ```bash
   shasum -a 256 iflo-3.0.64.bin
   ```
5. Verify the descriptor independently by reading the `esp_app_desc` magic
   `0xABCD5432` at offset `0x20`.

The token is account material. Do not commit it, log it, or paste
it into a ticket.

## 9. Recommended next steps

| Priority | Task | Why |
|---|---|---|
| 1 | Map the eight segments into Ghidra with an Xtensa module | Unlocks function-level analysis of the stock firmware |
| 2 | Locate `esp_tls` / `esp_http_client` configuration and CA bundle | Answers TLS-validation unknown for cloud replacement |
| 3 | Extract HTTP paths and JSON keys used by the cloud poll | Reconstruct the polling protocol |
| 4 | Analyze schedule + No-App Mode logic | Determines whether local scheduling is possible without cloud replacement |
| 5 | Query `/firmwares` with correct filters | Enumerate the 42 records; obtain comparison versions |
| 6 | Keep the stock image read-only and device state unchanged | Preserve the existing lab baseline |

## 10. Cross-references

- `research/original-firmware-feasibility.md` — cloud-independence paths, now
  statically answerable in part.
- `research/app-api-analysis.md` — mobile/web API surface; firmware endpoint
  added.
- `research/cloud-endpoints.md` — host inventory; firmware bucket added.
- `research/event-timeline.md` — first-provision timeline; firmware download
  confirmation appended.
- `research/device-identification.md` — SoC/firmware facts updated from the
  image header.
- `research/local-http-interface.md` — local API from the device's perspective.
- `research/firmware-security-audit.md` — community ESPHome replacement, for
  comparison with the stock image.

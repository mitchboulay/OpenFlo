# Artifacts

Local copies of the evidence used in this investigation. **Vendor firmware, the vendor app and packet captures are never committed** (`../.gitignore`). Only this README and `SHA256SUMS` are tracked. Obtain the files from the sources below, then verify them with `cd artifacts && shasum -a 256 -c SHA256SUMS`.

## Firmware

| File | Size | SHA-256 | Source |
|---|---:|---|---|
| `firmware/iflo-3.0.64.bin` | 1,309,376 | `3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2` | The vendor's own update service (see below) |
| `firmware/iflo-esphome-2026.9.1.factory.bin` | 988,448 | `b7fae3d52f00c96624272dc2ef85262ca24e1a40c044ec8dae74eaf689980872` | Community ESPHome build, `demitryk1/SmartHome/iFLO` |

The vendor app's account API has a firmware endpoint (`/api/v1/firmwares/global-url`) that, for a signed-in owner, returns a short-lived download location for the current image; the device itself fetches the same image during an OTA update, so it can also be recorded from your own device's update traffic. No direct download link is published here. Verify any copy you obtain against the SHA-256 above.

The official image is a standard ESP-IDF app image (ESP32-S2, 8 segments, entry
`0x40025284`), version `20251201_3.0.64`, built 2026-02-09 18:32:28 with IDF
`v5.3.2-dirty`. See `../research/firmware-3.0.64-acquisition.md`.

## Android package

`com.iflo.app` 4.4.0 (versionCode 47), pulled from an Android phone over ADB.

| File | Size | SHA-256 |
|---|---:|---|
| `apk/base.apk` | 31,216,876 | `f4966c80e9ad8a3cdfa4d9bf67b8b5203d1cd4287983dca2c481215bd6d51ef6` |
| `apk/split_config.arm64_v8a.apk` | 16,762,956 | `7396862a88a66818a0785bce6cb400eb68a6ed81b5fbe284084e3b9a747f663f` |
| `apk/split_config.en.apk` | 41,369 | `1aa36ed5664b56f9caae5242b9cdc740c622d640c931ac2f8ef804a9abe2d558` |
| `apk/split_config.es.apk` | 29,081 | `9697aea18d63d97ea7e5dcd1cf4fc3a49e52fe47fb79339a1f5a226160ab9640` |
| `apk/split_config.xxhdpi.apk` | 579,744 | `948ac56b18989572d91e1c43061e5a0d76c38621efb642ec9718b12f70adf308` |

These duplicate the canonical private copy at `~/openflo-private/apk/`.

## Derived analysis artifacts

`tools/make_xtensa_elf.py` generates `firmware/iflo-3.0.64.elf` from the app
image for Ghidra/REA. It is derived vendor firmware and is ignored by
`.gitignore`; regenerate it when needed. See
`../research/rea-firmware-analysis.md` and
`../research/rea-xtensa-workaround.md`.

## Capture

| File | Size | SHA-256 | Notes |
|---|---:|---|---|
| `captures/PCAPdroid_26_Oct_10_46_10.pcap` | 35,254,137 | `a83a14fcab090c59557e65bb38291e6b0945f2e47e5705b0660a3638f711a506` | PCAPdroid, 2026-10-26 10:46 local; TLS-only, includes `backend.iflo.com` and `storage.googleapis.com` |

This duplicates the canonical private copy at
`~/openflo-private/phone/PCAPdroid/`.

The second PCAPdroid file from the same session was not retained. The phone
reported ~19 MB, but the pull produced a 1.1 GB file, so the copy was not
trusted.

## Handling

- The official firmware and APK are vendor artifacts. Keep this directory
  private; do not redistribute them.
- `SHA256SUMS` in each subdirectory is the tracked integrity manifest.
- The binaries are ignored by `../.gitignore`, matching the existing
  `~/openflo-private/` convention.

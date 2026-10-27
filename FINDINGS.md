# Findings — iFLO firmware 3.0.64

The stock iFLO **3.0.64** image has been acquired and verified. The full
write-up is [`research/firmware-3.0.64-acquisition.md`](research/firmware-3.0.64-acquisition.md).

## Result

| Property | Value |
|---|---|
| File | `artifacts/firmware/iflo-3.0.64.bin` (not distributed; see [artifacts/README.md](artifacts/README.md)) |
| Size | 1,309,376 bytes |
| SHA-256 | `3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2` |
| Version | `20251201_3.0.64` |
| Target | ESP32-S2 (`chip_id=2`) |
| Framework | ESP-IDF `v5.3.2-dirty`, built 2026-02-09 18:32:28 |
| Image type | App-only, flashed at `0x10000` |

This confirms the 1.39 MB HTTPS transfer during first provisioning was the
stock firmware update.

## How it was obtained

1. Logged in to `https://app.iflo.com`.
2. Read the session token from `localStorage["__SESSION_DATA_KEY__"].accessToken`.
3. Called `GET https://backend.iflo.com/api/v1/firmwares/global-url` with
   `x-access-token`.
4. The API returned version `3.0.64` and a `storage.googleapis.com` object URL,
   which downloaded without auth once known.

The token is not stored in this repository.

## Artifacts

See [`artifacts/README.md`](artifacts/README.md) for sizes and hashes.

- `artifacts/firmware/iflo-3.0.64.bin` — official stock image
- `artifacts/firmware/iflo-esphome-2026.9.1.factory.bin` — community ESPHome build
- `artifacts/apk/` — `com.iflo.app` 4.4.0 base + splits
- `artifacts/captures/PCAPdroid_26_Oct_10_46_10.pcap` — phone capture

Binaries are local-only and excluded by [`.gitignore`](.gitignore); the
`SHA256SUMS` manifests are tracked.

## Related research updates

- `research/app-api-analysis.md` — firmware API, `x-access-token` header
- `research/cloud-endpoints.md` — firmware bucket and object
- `research/original-firmware-feasibility.md` — TLS/protocol questions now
  statically answerable
- `research/device-identification.md` — SoC/firmware facts corrected
- `research/event-timeline.md` — provisioning download confirmed as 3.0.64
- `research/rea-firmware-analysis.md` — TLS/API/OTA findings
- `research/rea-xtensa-workaround.md` — REA + Ghidra Xtensa setup

## REA results (2026-10-26)

Static analysis with REA 6.4.0 + Ghidra 12.2 is complete:

- TLS validation is **ON** via `esp-x509-crt-bundle`; self-signed local servers
  will fail. A CA-trusted host is required for cloud replacement.
- API base path is **`/device-api/v2/`**; endpoints: `register`,
  `update-device`, `get-fw`, `get-bottle`, `get-schedule`, `healthcheck`,
  `send-events`, `create-qc-report`.
- Requests are **POST JSON** with `x-device-id` (or `x-device-ott` for
  registration); no Bearer token.
- Host is configurable via `https-host-address`; default is
  `https://backend.iflo.com`.
- OTA uses `esp_https_ota` with the same CA bundle and
  `data.url.redirectLocation`.

Full write-up: [`research/rea-firmware-analysis.md`](research/rea-firmware-analysis.md).

## Mission 007 (2026-10-26)

Protocol reconstruction and backend emulator complete (static + mock):

- [`research/device-cloud-protocol.md`](research/device-cloud-protocol.md)
- [`research/device-sync-state-machine.md`](research/device-sync-state-machine.md)
- [`research/device-scheduling-protocol.md`](research/device-scheduling-protocol.md)
- [`research/openflo-backend-deployment.md`](research/openflo-backend-deployment.md)
- [`research/backend-migration-runbook.md`](research/backend-migration-runbook.md)
- [`research/controller-backend-integration.md`](research/controller-backend-integration.md)
- [`research/mission-008-proposal.md`](research/mission-008-proposal.md)
- [backend/](backend/) — FastAPI emulator, 21 tests passing

No physical-device configuration changed. Full report:
[`research/mission-007.md`](research/mission-007.md).

## Next steps

- Review and approve the Mission 008 proposal.
- Validate the reconstructed protocol and schedule schema on the bench.
- Resolve remaining gaps: `send-events` schema, bottle `config`, exact version
  floor, and TLS SNI/hostname-validation behavior.

# REA / Ghidra analysis — iFLO 3.0.64

Date: 2026-10-26. Status: **STATIC ANALYSIS COMPLETE** for the protocol, TLS and
OTA paths. No runtime testing was performed.

Target: `artifacts/firmware/iflo-3.0.64.elf` (ELF wrapper of
`iflo-3.0.64.bin`, SHA-256
`3b1df98aaf2afd69aed17bb5836672a1737ad1a88d9947f9738e607f515a40f2`).
Toolchain: REA 6.4.0 (local Xtensa workaround) + Ghidra 12.2,
language `Xtensa:LE:32:default`. Ghidra auto-analysis: **6,391 functions**,
**3,695 strings**.

## Executive summary

| Question | Finding | Confidence |
|---|---|---|
| Does the device validate the cloud TLS certificate? | **Yes.** `esp_http_client_config_t.crt_bundle_attach` is `esp-x509-crt-bundle`; the OTA path uses the same callback. | CONFIRMED (static) |
| What is the cloud API base path? | **`/device-api/v2/`** appended to the configured host. | CONFIRMED |
| What is the default host? | **`https://backend.iflo.com`**; overridable via config key `https-host-address`. | CONFIRMED |
| What endpoints exist? | `register`, `update-device`, `get-bottle`, `get-schedule`, `get-fw`, `healthcheck`, `send-events`, `create-qc-report`. | CONFIRMED |
| How is the device authenticated? | `x-device-ott` for registration; `x-device-id` on normal calls. No Bearer token. Basic-auth support exists in the HTTP library but is not configured by these calls. | CONFIRMED (static) |
| How does firmware update work? | `update-device`/`get-fw` return `data.url.redirectLocation`; the device stores it and calls `esp_https_ota` with the CA-bundle callback. | CONFIRMED (static) |
| Is No-App Mode implemented? | The `update-device` telemetry currently sends `noAppMode: 0`; schedule settings live in SPIFFS `schedule.txt`. Exact NAM behavior remains unresolved. | PARTIAL |

The practical consequence: **a local cloud replacement must present a
CA-trusted TLS certificate for the configured host.** A self-signed certificate
or a DNS override to an untrusted local server will be rejected. Using a host
you control with a public CA certificate (e.g. Let's Encrypt) is the viable
path.

## 1. Toolchain and admission workaround

REA 6.4.0 rejects `EM_XTENSA` (`e_machine = 94`) in
`dist/domain/binaryTarget.js` before Ghidra is reached
([morluto/rea#3483](https://github.com/morluto/rea/issues/3483)).
Ghidra 12.2 already ships `Ghidra/Processors/Xtensa`, so the workaround is:

1. Wrap the ESP-IDF image as ELF32 with one `PT_LOAD` per segment
   (`tools/make_xtensa_elf.py`).
2. Copy REA and admit `case 94` (`tools/patch_rea_xtensa.py`).
3. Patch the local copy's Ghidra release gate from `12.1.4` to `12.2`
   (`dist/ghidra/GhidraInstallationPolicy.js`; the installed 12.2 bridge passed
   all other checks, including the native decompiler and JDK 25).
4. Force `REA_GHIDRA_LANGUAGE_ID=Xtensa:LE:32:default`.

See `research/rea-xtensa-workaround.md` for the exact steps and caveats.

`rea inspect` succeeded with 6,391 procedures and 3,695 strings. All addresses
below are Ghidra VAs in the wrapped image.

## 2. Host selection and URL construction

### `FUN_40092ec0` — HTTPS client init

```c
uVar1 = FUN_400300d4();
FUN_4002fffc(3,"https_client",...,"https_client");
iVar2 = FUN_4009a5e0();
if (iVar2 == 0) {
    pcVar3 = (char *)FUN_400959a0("https-host-address");
} else {
    pcVar3 = "https://backend.iflo.com";
}
(*(code *)&SUB_40007cfc)(&DAT_3ffccb58, pcVar3);
FUN_4014d6d8(FUN_40092dfc, "https_task", 0x1000, 0, 5, ...);
```

- `DAT_3ffccb58` is the active base host.
- `https-host-address` is read through the `FS_manager` lookup
  (`FUN_400959a0`), i.e. the SPIFFS configuration store, not a compile-time
  constant.
- `FUN_40092f20` is the setter: it stores `https-host-address`, logs it, and
  updates `DAT_3ffccb58`.

### `FUN_40092f50` / `FUN_400942c0` — full URL

```c
FUN_40092f50(path);          // snprintf("%s%s", host, path) into 0x3ffcca98
...
FUN_40127800(buf, "/%s%s", "device-api/v2/", endpoint);
```

- Format string is `%s%s` (`0x3f00a1d0`), so the host must include the scheme.
- `FUN_400942c0` prepends `device-api/v2/` to the endpoint name.
- Example: host `https://backend.iflo.com` + `/device-api/v2/update-device`.

## 3. Request wrapper and auth

### `FUN_40092f80` — queue an HTTPS request

```c
if (DAT_3ffccb58 == '\0') return 1;
...
FUN_40092f50(path);
_DAT_3ffcc290 = FUN_400c9674(&DAT_3ffc4bb8);   // esp_http_client_init
FUN_400c8c54(client, "Accept", "*/*");
FUN_400c8c54(client, "Content-Type", "application/json");
FUN_400c8c54(client, "Accept-Encoding", "gzip, deflate, br");
FUN_400c8c54(client, header_name, header_value); // x-device-id / x-device-ott
if (body_len > 1) FUN_400c9dd4(client, body, body_len);
DAT_3ffcc28d = 1;                              // wake https_task
```

- Method argument is `1` for every caller (`HTTP_METHOD_POST` in ESP-IDF).
- Body is JSON; `Accept`/`Content-Type`/`Accept-Encoding` are fixed.
- The per-call header is the device identity:
  - `x-device-ott` on registration (one-time provisioning token).
  - `x-device-id` on normal API calls.
- No `Authorization`/Bearer header is set by this wrapper. `FUN_400c8c6c` is the
  ESP-IDF Basic-auth helper path; the config struct's username/password fields
  are zero, so it is not active for these requests.

## 4. TLS verification

`FUN_400c9674` (`esp_http_client_init`) copies the config at `0x3ffc4bb8`.
Field `+0x78` is `0x400abed4`, passed to the client's TLS setup. Decompiling it:

```c
int FUN_400abed4(int param_1) {
  if ((_DAT_3ffd7618 == 0) &&
      (iVar1 = FUN_400abda8(&DAT_3f039e20, 0x108de), iVar1 != 0)) { ... }
  if (param_1 != 0) {
    FUN_4013ddb8(param_1, &DAT_3f039c88, 0);
    FUN_4013dd88(param_1, FUN_400abcac, 0);
  }
  return 0;
}
```

The log tag is **`esp-x509-crt-bundle`** (`0x3f0126bc`). This is the ESP-IDF
CA-bundle attach routine: the client is configured with the built-in trust
anchors, and certificate verification stays enabled.

**OpenFLO implication:** a local HTTPS server must use a certificate chaining to
a CA in the ESP-IDF bundle. Self-signed certificates will fail the handshake.
If you control `https-host-address`, point it at a public DNS name you control
with a valid CA certificate; DNS override alone is not enough.

## 5. Device API surface

The command table at `0x40081800`/`0x40081900` and the `FUN_400942c0` callers
give the endpoint map. All are `POST` with JSON, under
`/device-api/v2/`.

| Endpoint | Handler | Request body | Notes |
|---|---|---|---|
| `/device-api/v2/register` | `FUN_40093f50` | `{"deviceId": "..."}` | Header `x-device-ott`. 200 = registered; 422 + `code`/`message` (e.g. `NOT_UNIQUE`, `NOT_FOUND`). |
| `/device-api/v2/update-device` | `FUN_40094c80` | telemetry object (below) | Header `x-device-id`. Central poll; returns schedule/settings/OTA state. |
| `/device-api/v2/get-fw` | `FUN_40094560` | `{"firmwareVersion": "...", "deviceId": "..."}` | Returns `actualFirmwareVersion` and `data.url.redirectLocation`. |
| `/device-api/v2/get-bottle` | `FUN_400949bc` | empty | Response parsed by `FUN_40094750`; 422 path handled. |
| `/device-api/v2/get-schedule` | `FUN_40094b00` | empty | Response parsed by `FUN_40097504`; stored in `schedule.txt`. |
| `/device-api/v2/healthcheck` | `FUN_4009446c` | `{"deviceId": "..."}` | Health probe. |
| `/device-api/v2/send-events` | `FUN_40095300` | event JSON | Event upload. |
| `/device-api/v2/create-qc-report` | `FUN_400942e8` | device/QC info | QC report. |

### `update-device` request

`FUN_40094c80` builds a cJSON object and adds:

`batteryLevel`, `firmwareVersion`, `connectionLevel`, `localIpAddress`,
`bottleSensorStatus`, `networkName`, `extPowerState`, `isProVersion`,
`ramUsed`, `ramTotal`, `ramUsedPercent`, `HeapFailureCount`, `deviceType`,
`pingQuality`, `pingLatency`, `pingFailureCount`, `dnsFailureCount`,
`noAppMode` (currently literal `0`), and the `nw:%ld/nd:%ld` network counters.

It then calls `FUN_400942c0("update-device", json)` and waits up to
150 × 100 ms for the response.

### `update-device` response fields

The parser reads `data` and handles:

- `extPowerState` — updates external-power state and may emit
  `SE_EXT_POWER_CONNECTED` / `SE_EXT_POWER_DISCONNECTED`.
- `remoteDispense.isActive` + `remoteDispense.nonce` — remote dispense request.
- `isScheduleSynced` — if false, triggers schedule refresh
  (`FUN_40094c70`, `FUN_40094740`, `FUN_4009aef8`); if true, stops sync mode.
- `isSettingsSynced` — if false, refreshes settings.
- `isWifiUpdated` — clears the WiFi-updated flag.
- `isUpToDate` — if false, sets the OTA-pending flag (`FUN_40099c90`), reads
  `data.url.redirectLocation`, and calls `FUN_40099ca0(url)`.
- `code`/`message` errors, including `INVALID_DEVICE_ID`.

## 6. OTA path

1. `update-device` or `get-fw` supplies `data.url.redirectLocation`.
2. `FUN_40099ca0` copies it into a 0x200-byte global (`DAT_3ffd6b00`) with
   `snprintf("%s")`.
3. `FUN_40099458` prechecks `ota-low-bat`, `ota-low-wifi`, and a non-empty URL.
4. `FUN_40099184` builds an `esp_https_ota_config_t` on the stack:

```c
apuStack_1d0[0] = &DAT_3ffd6b00;  // url
uStack_184      = 5000;           // timeout_ms
uStack_16c      = 0x800;          // buffer_size
uStack_15e      = 1;              // keep-alive/flag
pcStack_158     = FUN_400abed4;   // crt_bundle_attach
```

5. Calls `esp_https_ota_begin` (`FUN_400cce98`),
   `esp_https_ota_get_img_desc` (`FUN_400cd19c`),
   version checks (`FUN_4009904c`, `FUN_400990e8`),
   `esp_https_ota_perform` loop (`FUN_400cd244`),
   `esp_https_ota_finish` / `esp_https_ota_abort` (`FUN_400cd470` /
   `FUN_400cd498`).

Version checks observed:

- `FUN_4009904c` compares the image version string (`image_desc + 0x10`) with
  the running version. Same version → flag `DAT_3ffd6d01 = 1`,
  `_DAT_3ffd6afc = 300`, return -1. This is the
  `"Current level is same as loaded!"` path.
- `FUN_400990e8` applies a device-type-specific check for types 2/3
  (MINI/SEPTIC) using `FUN_4013c5cc(..., 0x51402)`; the exact threshold mapping
  is unresolved.
- The string `Firmware update fail! This device does not support firmware
  versions below 2.20.5 !` exists in the image; the exact branch was not
  isolated.

No custom signature check is visible in the OTA config. `esp_https_ota` performs
its standard image/chip validation; whether secure boot is fused on the device
is unknown.

## 7. Scheduling, sync and No-App Mode

- `schedule.txt`, `config.txt`, `events.txt`, `lost_disp.txt` are SPIFFS files
  (`/spiffs/`).
- `schedule-sync-time` and `fast-sync-time` are configuration keys.
- `get-schedule` response is parsed by `FUN_40097504` and persisted.
- `isScheduleSynced` false triggers the schedule refresh path; true calls
  `Stop_sync_mode`-style logic.
- `isSettingsSynced` false triggers `FUN_400988bc`.
- `noAppMode` is sent as `0` in the `update-device` body in this build. The
  settings page exposes a No-App Mode toggle, but the telemetry value is
  hard-coded 0 in `FUN_40094c80`; the cloud may set it through another path.
  **Do not conclude NAM is fully unavailable without further tracing.**

## 8. Implications for OpenFLO

1. **Cloud replacement is protocol-feasible.** The device polls
   `POST <host>/device-api/v2/update-device` with a JSON telemetry body and
   `x-device-id`; the response can carry schedule, settings, remote-dispense and
   OTA directives.
2. **TLS is the hard gate, not the protocol.** A local replacement needs a
   CA-trusted certificate for the configured host. Self-signed + DNS override
   will fail. A public host you control is the practical route.
3. **Provisioning host is a full URL.** `https-host-address` is used with
   `%s%s`; set it to `https://<your-host>` (scheme included).
4. **Device identity is header-based.** `x-device-id` is sent on every normal
   call; `x-device-ott` is the registration one-time token. There is no Bearer
   token to mint.
5. **OTA can be self-hosted** if the image URL points at a CA-trusted host and
   the image passes the descriptor/version checks. The same CA bundle is used.

## 9. Residual unknowns

- Exact version-floor numeric mapping (`0x51402` in `FUN_400990e8`).
- Whether secure boot / signed OTA is fused (not answerable from the app image).
- Full schedule JSON schema and `get-schedule` response fields.
- Whether `noAppMode` can be enabled through the cloud/settings path.
- Dynamic confirmation of the reconstructed protocol (no device traffic was
  generated in this analysis).

## 10. Evidence index

| Item | Address / value |
|---|---|
| HTTPS init / host selection | `FUN_40092ec0` (`0x40092ec0`) |
| Host setter | `FUN_40092f20` (`0x40092f20`) |
| URL formatter | `FUN_40092f50` (`0x40092f50`), format `%s%s` at `0x3f00a1d0` |
| Request wrapper | `FUN_40092f80` (`0x40092f80`) |
| API path builder | `FUN_400942c0` (`0x400942c0`) |
| Register | `FUN_40093f50` (`0x40093f50`) |
| Update-device | `FUN_40094c80` (`0x40094c80`) |
| Get-fw | `FUN_40094560` (`0x40094560`) |
| Get-bottle | `FUN_400949bc` (`0x400949bc`) |
| Get-schedule | `FUN_40094b00` (`0x40094b00`) |
| Healthcheck | `FUN_4009446c` (`0x4009446c`) |
| Send-events | `FUN_40095300` (`0x40095300`) |
| Create-QC-report | `FUN_400942e8` (`0x400942e8`) |
| CA-bundle attach | `FUN_400abed4` (`0x400abed4`), tag `esp-x509-crt-bundle` |
| TLS/HTTP config | `0x3ffc4bb8`, `crt_bundle_attach` at `+0x78` |
| HTTP init | `FUN_400c9674` (`0x400c9674`) |
| OTA URL setter | `FUN_40099ca0` (`0x40099ca0`) |
| OTA precheck | `FUN_40099458` (`0x40099458`) |
| OTA perform | `FUN_40099184` (`0x40099184`) |
| OTA version/same-version | `FUN_4009904c` (`0x4009904c`) |
| OTA device-type check | `FUN_400990e8` (`0x400990e8`) |
| API base string | `device-api/v2/` at `0x3f00b340` |
| Default host string | `https://backend.iflo.com` at `0x3f00a114` |
| Host config key | `https-host-address` at `0x3f00a130` |

## 11. Reproduce

```bash
python3 tools/make_xtensa_elf.py \
  artifacts/firmware/iflo-3.0.64.bin \
  artifacts/firmware/iflo-3.0.64.elf
python3 tools/patch_rea_xtensa.py

export PATH=/opt/homebrew/bin:$PATH
export GHIDRA_INSTALL_DIR="$(brew --prefix ghidra)/libexec"
export JAVA_HOME="$(brew --prefix openjdk@25)/libexec/openjdk.jdk/Contents/Home"
export REA_GHIDRA_LANGUAGE_ID="Xtensa:LE:32:default"
export REA_GHIDRA_COMPILER_SPEC_ID="default"

node /tmp/rea-xtensa/scripts/rea.mjs inspect \
  artifacts/firmware/iflo-3.0.64.elf --provider ghidra --format json
```

The local REA copy also needs the `SUPPORTED_GHIDRA_VERSION = "12.2"` change in
`dist/ghidra/GhidraInstallationPolicy.js` for Ghidra 12.2; the workaround doc
records it. This is a local patch, not an upstream Xtensa lane.

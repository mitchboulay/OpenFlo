# Device synchronization state machine — iFLO 3.0.64

Date: 2026-10-26. Static reconstruction from the official image. No device
traffic was generated or redirected. Diagrams are evidence-derived, not runtime
observations.

## 1. Actors and flags

| Flag / value | Meaning | Evidence |
|---|---|---|
| `DAT_3ffccc71` | registered/provisioning gate | `FUN_40093f50`, `FUN_40094c80` |
| `DAT_3ffccc72`, `_73`, `_74` | sync/retry counters and state | `FUN_40094c80` |
| `DAT_3ffcc28c` | HTTPS client ready | `FUN_40092ec0` |
| `DAT_3ffcc28d` | request scheduled | `FUN_40092f80` |
| `DAT_3ffcc28f` | request busy | `FUN_40092f80` |
| `_DAT_3ffcc290` | active HTTP client handle | `FUN_40092f80`, `FUN_40092dfc` |
| `DAT_3ffccb58` | active host string | `FUN_40092ec0`, `FUN_40092f50` |
| `DAT_3ffd6d03` | OTA pending | `FUN_40099c90`, `FUN_4009956c` |
| `DAT_3ffd6b00` | OTA URL buffer (0x200) | `FUN_40099ca0`, `FUN_40099184` |
| `DAT_3ffd6d11` | host-mode flag | `FUN_4009a5e0`, `FUN_40092ec0` |
| `fast-sync-time` | fast-sync interval | `FUN_4009af88`, `FUN_4008f350` |
| `schedule-sync-time` | schedule sync interval | `FUN_40096b3c`, `FUN_40097048` |
| `last-dispense` | duplicate suppression | `FUN_40096d4c`, `FUN_40097048` |

## 2. Successful update-device cycle

```mermaid
sequenceDiagram
    participant D as iFLO device
    participant H as HTTPS worker
    participant B as OpenFLO backend
    D->>H: wake / sync request
    H->>H: wait for idle slot (15 tries)
    H->>B: POST /device-api/v2/update-device
    Note right of H: headers: x-device-id, Content-Type JSON
    B-->>H: 200 {"data":{...}}
    H->>H: parse cJSON; store status/body
    H->>D: process data fields
    alt remoteDispense active
        D->>D: dispense type 4 (nonce dedup)
    end
    alt isScheduleSynced=false
        D->>B: POST /device-api/v2/get-schedule
        B-->>D: schedule array
        D->>D: store schedule.txt, set loaded flag
    end
    alt isUpToDate=false and url present
        D->>D: set OTA URL + pending flag
    end
    D->>D: compute next wake; sleep
```

## 3. Schedule-sync branch

`FUN_40094c80` handles `isScheduleSynced`:

- `false`:
  - `FUN_40094c70` and `FUN_40094740` are called (schedule/bottle refresh
    helpers).
  - `FUN_4009aef8` stops fast sync.
  - Later, `get-schedule` is executed by the schedule/event flow
    (`FUN_40094b00`), parsed by `FUN_40097504`, and stored.
- `true`:
  - `FUN_4009afcc` checks fast-sync state; `FUN_4009af58` may restart the
    fast-sync timer.
  - Logs `No changes go to force sleep`.

## 4. Failure / malformed response

```mermaid
sequenceDiagram
    participant D as iFLO device
    participant B as OpenFLO backend
    D->>B: POST /update-device
    alt HTTP error / timeout
        B--xD: no response / non-200
        D->>D: log error; cleanup (FUN_40093074)
        D->>D: return to sleep; retry next wake
    else malformed JSON
        B-->>D: 200 non-JSON
        D->>D: cJSON parse fails; log; cleanup
        D->>D: return to sleep; retry next wake
    end
```

Observed finite waits:

- 5 s HTTP timeout (client config).
- 15 s response wait (150 × 100 ms).
- 15-slot busy wait before queueing.

No unbounded busy-loop was observed in the decompiled paths. Exact retry/backoff
across wakes is INFERRED, not runtime-tested.

## 5. Sleep transition

- `FUN_4008f350` sets the next wake value:
  - uses `FUN_40096da4()` (next schedule wake) when non-zero;
  - otherwise uses `fast-sync-time`.
- `FUN_4008fa3c` adjusts the 16-bit sleep timer; `FUN_4008faac` reads it.
- `FUN_4009aec0` starts fast sync; `FUN_4009aef8` stops it; `FUN_4009afcc`
  checks the fast-sync bit/timer.
- `FUN_40096da4` computes the nearest schedule delta and sets normal/exact-time
  flags; `FUN_4009aef8` / `FUN_4009aec0` adjust the sync mode.

The final `esp_deep_sleep_start` call site was not isolated in this pass. The
timer computation and sync-mode control are confirmed; the last jump into the
ESP-IDF sleep function remains a stated gap.

## 6. Fields that can cause actions

| Field | Action | Safe emulator behavior |
|---|---|---|
| `remoteDispense.isActive` | motor dispense (type 4) | **omit entirely** |
| `remoteDispense.nonce` | duplicate suppression | **omit entirely** |
| `isUpToDate=false` + `url.redirectLocation` | OTA download | return `isUpToDate:true`, no `url` |
| `isScheduleSynced=false` | fetch schedule | only if scheduling enabled |
| `isSettingsSynced=false` | float/settings reset | omit |
| `isWifiUpdated=true` | clear WiFi flag | omit |
| `extPowerState` | power-state update/events | omit |

## 7. Duplicate prevention

- Remote dispense: `FUN_4008e388` stores the nonce and only triggers if it
  differs from the previous nonce.
- Schedule dispense: `FUN_40096d4c` compares the schedule timestamp with
  `last-dispense`; equal or older entries are skipped.
- After a schedule fires, the in-memory entry is cleared and `last-dispense` is
  updated.
- Event upload has retry/state counters but the exact idempotency key is
  UNKNOWN.

## 8. Emulator-safe policy

1. Always return `isUpToDate: true`.
2. Never return `remoteDispense`.
3. Never return `url` or `data.url`.
4. Omit `isSettingsSynced`, `isWifiUpdated`, `extPowerState`.
5. Return `isScheduleSynced` only when scheduling is deliberately enabled; the
   default schedule is empty.
6. Return 501 for `/get-schedule` and `/get-bottle` in safe mode rather than
   inventing a response.

This keeps the device in the normal telemetry/sleep loop without motor, OTA, or
configuration side effects.

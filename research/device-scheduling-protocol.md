# Device scheduling protocol — iFLO 3.0.64

Date: 2026-10-26. Static reconstruction. No schedule was activated on a device.

## 1. Two representations

The firmware has two related schedule representations:

### Cloud `get-schedule` response

`FUN_40097504` parses a root object and selects:

- `data` for normal cloud polling;
- `schedule` for the alternate/local mode.

Each item is an object:

| Field | Type | Class | Notes |
|---|---|---|---|
| `timestamp` | number | CONFIRMED_STATIC | epoch seconds; stored in a 64-bit pair |
| `doseCount` | number | CONFIRMED_STATIC | stored as a byte; action path returns 1 or 2 |
| `cmd` | number | CONFIRMED_STATIC | optional; 0 = normal window, 1 = exact-time window |

Maximum **33 entries** (`0x21`). Missing/invalid items are skipped. Entries are
cleared before parsing and re-added through `FUN_400960b4`; the loaded flag
`DAT_40081d24` is set.

### Local `schedule.txt` representation

`FUN_400960b4` appends a different object shape:

```json
{"type": "schedule", "time": 1760000000, "data": 1, "cmd": 0}
```

- `time` is a numeric timestamp derived from the parsed timestamp.
- `data` is the dose count.
- `cmd` is the command/window mode.
- `FUN_40095f34` writes the JSON to `schedule.txt` (SPIFFS `/spiffs/`).
- `FUN_40095bc8` loads `schedule.txt` and parses it into the schedule object.
- The root container is the cJSON array/object produced by the schedule
  manager; the exact wrapper is INFERRED as an array because
  `FUN_400960b4` appends items with `FUN_400a32f0`.

**Do not assume the community ESPHome schedule format applies.** This is the
vendor firmware format.

## 2. Action state machine

`FUN_40097048` is the due-schedule selector. It:

1. Reads current time (`FUN_400923c8`), `shift-time`, `schedule-sync-time`, and
   `last-dispense`.
2. Computes a normal window around now: `[now - window, now + window]`.
3. Iterates up to 33 entries.
4. Skips entries already handled (`FUN_40096d4c`: `last-dispense >= timestamp`).
5. For `cmd == 0` (normal):
   - if `timestamp` is inside the normal window, fire.
6. For `cmd == 1` (exact-time):
   - uses a second window beginning at `now + 2 * iVar2` (`iVar2` from
     `FUN_4008faa0`; likely shift/sync margin, INFERRED) and fires if the
     timestamp is inside it.
7. On fire:
   - writes `doseCount` to the output byte;
   - updates `last-dispense = schedule-sync-time + timestamp`;
   - clears the in-memory entry;
   - returns 1.

`FUN_400976a8` is the periodic schedule-control tick:

- returns early if time is not synced (`FUN_4008e194` bit 0), the host mode is
  wrong (`FUN_4009a5e0`), or schedule is unavailable;
- refreshes schedule/bottle state when the sync interval elapses;
- checks bottle/float/power conditions;
- calls `FUN_40097048`;
- if it fires, triggers a scheduled dispense (`FUN_4008e370`, dose count 1) or
  a boosted/two-dose path (`FUN_4008e37c`, dose count 2);
- adjusts the sleep timer after firing.

Window modifiers:

| Condition | Effect | Evidence |
|---|---|---|
| external power | window = 200 (larger) | `FUN_40098a94` in `FUN_40097048` |
| offline mode | window = 10 | `FUN_4009aa08` |
| No-App Mode flag | window = 10 | `FUN_4009b12c` |
| normal | `uVar4 = shift-time` | `FUN_40095830("shift-time")` |

The exact mapping of the three mode helpers to offline/NAM/test is INFERRED from
log strings and call sites; all are treated as window modifiers.

## 3. Next wake computation

`FUN_40096da4`:

- reads current time, `shift-time`, `fast-sync-time`, and mode flags;
- iterates schedule entries and finds the nearest future timestamp;
- sets normal/exact-time flags (`PTR_DAT_40081cb0` / `PTR_DAT_40081cb4`);
- calls `FUN_4009aef8` (stop fast sync) or `FUN_4009aec0` (start fast sync);
- returns the delta used by `FUN_4008f350` for the sleep timer.

`FUN_4008f350` sets the next wake to `FUN_40096da4()` or `fast-sync-time`;
`FUN_4008fa3c` adjusts the sleep value; `FUN_4008faac` reads it.

## 4. Time, offline and persistence

- Schedule execution requires a valid time (`FUN_4008e194` bit 0); NTP is the
  normal time source.
- `schedule.txt` is written to SPIFFS and reloaded at boot, so schedules are
  expected to survive power loss (INFERRED from file-based persistence; not
  power-cycle tested).
- Once stored, the action path runs locally; it does **not** need a cloud
  request at the moment of dispensing.
- If the backend is unavailable, the stored schedule still runs when time is
  valid. `isScheduleSynced=false` only controls whether the device refreshes
  the schedule from the cloud.
- `last-dispense` persists and prevents replay of an already-fired timestamp.

## 5. Stored vs activated

**Stored** means the entry exists in the in-memory array and `schedule.txt`.
**Activated** means `FUN_40097048` selected it, the window matched, duplicate
checks passed, and `FUN_400976a8` triggered a dispense. A stored entry does not
dispense immediately unless its timestamp is inside the active window.

## 6. Safety-relevant observations

- A cloud response can set a timestamp close to now and `cmd`/`doseCount`,
  causing a dispense on the next schedule tick.
- `remoteDispense` is a separate immediate path and does not need a schedule.
- A malformed schedule response can clear the in-memory array; whether it
  clears `schedule.txt` depends on the write path and is not fully traced.
- The emulator defaults to **no schedule endpoint** (501). If scheduling is
  enabled, it returns only explicitly provisioned, future-dated entries and
  never activates one itself.

## 7. Unknowns

- Exact `shift-time` and `schedule-sync-time` defaults and units.
- Exact `cmd=1` window formula (`iVar2` source).
- Local `schedule.txt` root wrapper (array vs object) and atomicity.
- `doseCount` semantics beyond 1/2.
- Timezone: timestamps are epoch seconds; local timezone handling is not
  explicit in the parser.
- Missed-schedule behavior after long power loss (likely skipped if
  `last-dispense` is newer).

## 8. Safe schedule-test plan (later mission)

1. Use the emulator, never the live device, for schema tests.
2. Register a mock device; enable scheduling.
3. Return an empty `data` list; verify the emulator stores no schedule and the
   response has no OTA/remote fields.
4. Add one future entry (`timestamp = now + 1 day`, `doseCount = 1`, `cmd = 0`);
   verify the emulator returns it and the sync flag advances.
5. Only after explicit approval, test one physical schedule with the device on
   an isolated bench, a towel/drain path, and a rollback host ready.

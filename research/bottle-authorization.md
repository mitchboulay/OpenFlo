# Bottle authorization — iFLO 3.0.64

Date: 2026-10-26. Static firmware reconstruction plus the existing authorized
capture data. No device configuration was changed.

## 1. Bottom line

The iFLO does **not** authenticate the bottle locally. There is no RFID, NFC,
1-Wire or cryptographic tag reader in the bottle path. GPIO13 is a simple
seat switch (`INPUT_PULLUP`, inverted). The device asks the cloud for a bottle
record and treats the cloud's answer as the authorization:

- `/get-bottle` **200** with `dispenseLeft > 0` → the device sets
  `bttl-vald=1`, state `OK`, and enables dispensing.
- `/get-bottle` **200** with `dispenseLeft = 0` → no validation; the bottle is
  treated as empty.
- Error code `BOTTLE_INSTALLED_NOT_AUTHORIZED` → state `UNCO`
  (unconfirmed/unauthorized), `bttl-vald=0`, no dispensing.
- `bottleId` and `dispenseTime` are parsed and **discarded**. The `bttl-id`
  config key is present in the key table but is not read or written by the
  bottle code.

So a self-hosted backend can authorize any physically inserted bottle by
serving a valid bottle record. The bottle's identity is not checked on the
device.

Scope: this is for a device you own, with your own bottle and backend. It is
not a recipe for counterfeiting vendor consumables or bypassing another party's
billing.

## 2. Hardware and sensing

| Item | Finding | Evidence |
|---|---|---|
| Bottle sensor | GPIO13, `INPUT_PULLUP`, inverted switch | `research/hardware-compatibility.md`, `research/upstream-esphome-review.md` |
| Insert/eject events | `EJECT` / `INJECT` table at `0x3f022dd8` | `FUN_4009192c` |
| Tag reader | none found | no RFID/NFC/1-Wire strings or calls in the bottle path |
| Bottle identity | cloud `bottleId`, ignored by the firmware | `FUN_40094750` |

The switch only tells the firmware that a bottle is seated. The local
`bottleSensorStatus` telemetry is derived from the bottle **state** (OK / MISS /
EMPT / UNCO), not from a tag ID.

### 2.1 Vendor app flow

The vendor app scans a QR code on the cartridge and sends it to the cloud,
which validates it server-side and returns the bottle record to the device
(`research/app-api-analysis.md`). The device never sees the QR code or the
bottle ID; it only receives `dispenseLeft`, `dispenseNumber` and `config`.

A self-hosted backend can skip the QR validation entirely and serve its own
record. For a DIY bottle, no QR code is needed — the device only checks the
GPIO13 switch and the cloud record.

## 3. Local state machine

The bottle state is one byte at `0x3ffc4ba9` (`FUN_40091c38`). The state table
at `0x3f022de8` contains four 16-byte entries:

| State | Raw name | Meaning | Local HTTP mapping |
|---:|---|---|---|
| 0 | `OK` | bottle valid / available | `OK` |
| 1 | `MISS` | no bottle / not inserted | `MISSING` |
| 2 | `EMPT` | bottle empty (all doses used) | `EMPTY` |
| 3 | `UNCO` | unauthorized / unconfirmed | `UNCONFIRMED` |

Related storage:

| Name | Address / key | Meaning |
|---|---|---|
| physical bottle state | `0x3ffc4ba8` | `0` ejected, `1` inserted, `0xff` unknown |
| validated flag | `0x3ffcb055` | RAM flag set after validation |
| info-issue flag | `0x3ffcb056` | bottle info pending / issue |
| `bttl-vald` | config key `0x3f008f08` | persisted authorization flag |
| `max-doses` | config key `0x3f008d80` | total capacity from `dispenseNumber` |
| `used-dose-cnt` | config key `0x3f008db8` | `dispenseNumber - dispenseLeft` |
| `bttl-id` | config key `0x3f00f39c` | present but unused |
| `disp-timings` | config key `0x3f0059a0` | per-dose pump timings built from `config` |

The firmware keys use hyphens (`bttl-vald`, `max-doses`, `used-dose-cnt`);
older notes sometimes write them with underscores. The hyphenated form is the
one in the key table.

### 3.1 `FUN_4009192c` — bottle control (insert/eject)

`FUN_4009192c(param)` is called on the GPIO13 event: `0` = eject, `1` = inject,
`2` = OK.

- Eject (`0`): clears the active timer to the full window, calls
  `FUN_40091644(1)` (MISS), and (in No-App Mode) writes `bttl-vald=0`,
  `max-doses=0`, `used-dose-cnt=0`.
- Inject (`1`): if not in demo mode and not already validated, calls
  `FUN_40094c70()` (request sync) and then `FUN_40091644(3)` (UNCO) until a
  valid cloud record arrives. If already validated, calls `FUN_40091644(0)`.
  In No-App Mode, an unvalidated insert goes through `FUN_4009b0c0` instead
  (self-authorization).
- `2`: logs `OK` and treats the bottle as available.

### 3.2 `FUN_40091644(state)` — state transition

| New state | Preconditions / action |
|---|---|
| `0` OK | Physical state must be `1` (inserted) **and** `max_doses > used_dose_cnt`. Otherwise it falls back to `1` (MISS) or `2` (EMPT). |
| `1` MISS | Waits for time sync; if the bottle is empty or demo mode is on, clears `bttl-vald`. Emits event 6. |
| `2` EMPT | Clears the schedule, saves state, emits event 7 if an issue was pending. |
| `3` UNCO | Clears the schedule, emits event 5, writes `bttl-vald=0`, clears validated/issue flags. |

`FUN_40091628()` is the empty test: it returns true when
`max_doses <= used_dose_cnt`.

### 3.3 `FUN_4009183c` — validation

Called after a 200 bottle response when `dispenseLeft != 0`:

```c
if (physical_state == 0 && !offline_mode) {
    log("Bottle is not validated. Bottle is not inserted");
    return;
}
if (max_doses <= used_dose_cnt) {
    log("Bottle is empty");
    return;
}
if (!validated) {
    FUN_40091644(0);          /* state OK */
    validated = 1;
    issue = 1;
    set("bttl-vald", 1);      /* <-- authorization */
    ...
}
```

So the three authorization conditions are:

1. The bottle is physically inserted (unless offline mode is on).
2. `dispenseNumber > dispenseLeft` (at least one dose remains).
3. `dispenseLeft > 0` (otherwise the caller never reaches this function).

### 3.4 `FUN_40091a6c` — full reset

Clears the validated flag, issue flag, `bttl-vald`, `max-doses`,
`used-dose-cnt`, sets the physical state to `0xff`, and re-runs
`FUN_4009192c` with the last eject state.

### 3.5 Physical bottle identity

There is no identity check. The device tracks a **dose count**, not a physical
container:

- Ejecting a partially used bottle calls `FUN_40091644(1)` (MISS), but that
  path only clears `bttl-vald` / `validated` when the bottle is empty
  (`max_doses <= used_dose_cnt`) or demo mode is on.
- Reinserting a different bottle while `validated` is still 1 makes
  `FUN_4009192c(1)` call `FUN_40091644(0)` (OK) without waiting for a new cloud
  record.
- The dose counters carry over, so the replacement bottle inherits the previous
  remaining-dose count until the count is exhausted or a reset/UNCO path runs.

This is a software heuristic, not a secure per-bottle authorization. It means a
self-hosted backend only has to authorize the **device's dose count** once; the
physical container can be swapped as long as it closes the GPIO13 switch.

## 4. Cloud `/get-bottle`

`FUN_400949bc` sends `POST /device-api/v2/get-bottle` with an empty body and
the normal device headers. It waits up to 15 s (150 × 100 ms). The response
parser is `FUN_40094750(body, root)` where `root=0` selects `data` and `root=1`
selects `bottle`. The cloud path uses `root=0`; the `bottle` root belongs to the
alternate/primary API path.

### 4.1 Required fields

`FUN_40094750(body, 0)` reads `data.dispenseLeft`, `data.dispenseNumber` and a
**root-level** `config`. The `config` lookup uses the root object, not the
`data` object; a `config` placed inside `data` is ignored on the cloud path.
(The `bottle` alternate root uses `bottle.config`.)

| Field | Path | Type | Required | Use |
|---|---|---|---|---|
| `dispenseLeft` | `data` | number | **yes** | remaining doses; `>0` is the authorization bit |
| `dispenseNumber` | `data` | number | **yes** | total capacity; written to `max-doses` |
| `config` | **root** | array | **yes** | per-dose valve/pump timing map (100 ms units; index = used dose count) |
| `dispenseTime` | `data` | number | no | parsed, discarded |
| `bottleId` | `data` | string | no | parsed, discarded |
| `isNonScheduledDispense` | `data` | bool | no | device type 3 only |

The parser rejects the response if `dispenseLeft`, `dispenseNumber` or
`config` is missing.

### 4.2 What the parser does

```c
data  = root["data"];
used  = (data.dispenseNumber - data.dispenseLeft) & 0xffff;
max   = data.dispenseNumber;
apply_config(root["config"]);   /* builds "disp-timings" */
if (data.dispenseLeft != 0)
    FUN_4009183c();             /* validate -> bttl-vald=1 if max > used */
```

`FUN_4008e0ec(config)` iterates the children of `config`; each child must have
`index` (0..32) and `dispenseTime`. It writes a 16-bit timing into the
dispenser array, indexed by the **used dose count** (0 = first dose), and
appends to the `disp-timings` string. `dispenseTime` is in **100 ms units**
(20 = 2.0 s). An empty `config` object is accepted by the null check but leaves
the string buffer uninitialized, so supply a contiguous table from index 0.

The firmware's built-in defaults are a safe starting point:

| Hardware rev | Actuator | Default timings (100 ms units) | Seconds |
|---:|---|---|---|
| 3 | valve | `[65, 70, 73, 80, 98, 260]` | 6.5, 7.0, 7.3, 8.0, 9.8, 26.0 |
| 4 | motor | `[47, 47, 47, 47, 47, 100]` | 4.7 × 5, 10.0 |

`disp-timings` is persisted as a `;`-prefixed string (`;65;70;…`), reloaded by
position at boot, and ignored unless it starts with `;`. Parsing stops at the
first zero, so do not leave gaps in the table. It is not on the
restore-to-default wipe list; vendor-written timings may persist until replaced.

### 4.3 Error path

If `data`/`bottle` is absent, the parser reads `fields.code` and
`fields.message`:

| Code | Effect |
|---|---|
| `BOTTLE_INSTALLED_NOT_AUTHORIZED` | if the current state is `OK`, call `FUN_40091644(3)` → `UNCO`, `bttl-vald=0` |
| `INVALID_DEVICE_ID` | `FUN_40097e50()` → full restore-to-default + restart. **Never send this to a device you do not intend to deprovision.** |
| other / missing `fields` | logged only; no state change |

HTTP status handling (`FUN_400949bc`):

| Status | Effect |
|---|---|
| 200 | parse `data` |
| 422 | parse the body, then `FUN_40091d6c()` clears the bottle-sync flag |
| 501 / other | log; the sync flag stays set and the device retries |

## 5. Authorization truth table

| Response | Bottle state | `bttl-vald` | Dispense allowed |
|---|---|---|---|
| 200, `dispenseLeft > 0`, `dispenseNumber >= dispenseLeft`, bottle inserted | `OK` | `1` | yes |
| 200, `dispenseLeft = 0` | no new validation; next state check sees empty | unchanged until the state check clears it | no |
| 200, `dispenseNumber < dispenseLeft` | no new validation (16-bit underflow → empty) | unchanged until the state check clears it | no |
| 422 `BOTTLE_INSTALLED_NOT_AUTHORIZED` | unchanged | unchanged | no |
| 200 error `BOTTLE_INSTALLED_NOT_AUTHORIZED` | `UNCO` | `0` | no |
| 200 error `INVALID_DEVICE_ID` | factory reset | wiped | no |
| No-App Mode, bottle inserted | `OK` | `1` | yes (6 doses) |

Not shown: a partially used bottle can be ejected and a different container
inserted while `validated=1`; the new container inherits the remaining count.
The device never knows the container changed. See §3.5.

## 6. How to provide and authorize your own bottle

### 6.1 Recommended: serve a valid `/get-bottle` record

Physically, any container that closes the GPIO13 switch when seated is detected
as a bottle. On the backend, return a bottle record with at least one dose
remaining:

```json
{
  "data": {
    "dispenseLeft": 6,
    "dispenseNumber": 6
  },
  "config": [
    {"index": 0, "dispenseTime": 65},
    {"index": 1, "dispenseTime": 70},
    {"index": 2, "dispenseTime": 73},
    {"index": 3, "dispenseTime": 80},
    {"index": 4, "dispenseTime": 98},
    {"index": 5, "dispenseTime": 260}
  ]
}
```

`dispenseTime` is in 100 ms units: 65 = 6.5 s, 260 = 26.0 s. These are the
firmware's built-in valve defaults, a starting point — not a calibration for
your liquid. See
[`flow-and-dispense-calibration.md`](flow-and-dispense-calibration.md).

The device will:

1. compute `used = 6 - 6 = 0`, `max = 6`;
2. apply the valve/pump timings;
3. call `FUN_4009183c()` because `dispenseLeft != 0`;
4. set `bttl-vald=1`, state `OK`, `max-doses=6`, `used-dose-cnt=0`.

For a partially used bottle, keep `config` at the root:

```json
{"data": {"dispenseLeft": 3, "dispenseNumber": 6}, "config": [...]}
```

This yields `used=3`, `max=6`, still authorized.

Supply one `config` entry for each dose index you intend to dispense. The
indices are 0..32; the firmware stores a 16-bit pump time per index.

**`config` is not optional for real dispensing.** It is the per-dose pump
timing map. The authorization itself only needs `dispenseLeft > 0`, but the
pump will use whatever timings are in `disp-timings` / the dispenser array.
Do not guess the timing for a real dispense; use a known-good bottle record or
measure the pump.

### 6.2 No-App Mode (no cloud)

`FUN_4009b0c0` runs when No-App Mode is enabled and a bottle is inserted. It
sets `used-dose-cnt=0`, `max-doses=6`, calls `FUN_4009183c()` (which sets
`bttl-vald=1`) and then `FUN_40091644(0)`. In other words, No-App Mode
self-authorizes the inserted bottle with a hardcoded 6 doses.

Trade-offs: No-App Mode changes schedule/cloud behavior and is a different
operating mode. It is useful as a fallback, but not the same as normal mode
with a self-hosted backend.

### 6.3 What does **not** work

| Attempt | Result |
|---|---|
| `update-device` `data.config` with `bttl-vald` / `bttl-id` / `max-doses` | ignored: `FUN_400984d4` does not process bottle keys |
| Local HTTP `/dev_actions` | only `manualDispense`, `reboot`, `restoreToDefault` |
| Local HTTP `/config` | provisioning only (`TOKEN`, `SERVER_CREDENTIALS`, `WIFI_CONFIG`) |
| Spoofing a bottle tag | there is no tag reader; GPIO13 is a switch |
| Sending `bottleId` | parsed and discarded; not used for authorization |

Directly writing NVS/flash or patching the `bttl-vald` key is possible in
principle but is out of scope, fragile, and unnecessary when the cloud path
already works.

## 7. Backend implementation notes

The current backend implements this path:

- `dispensing_enabled` defaults to false; a locked device gets 422
  `BOTTLE_INSTALLED_NOT_AUTHORIZED` (the firmware's `UNCO` path).
- Enabling it via `PATCH /admin/devices/{id}/controls` returns 200 with
  `data.dispenseLeft = data.dispenseNumber = 100` and the root-level `config`
  table.
- The table is the firmware default `FIRMWARE_DEFAULT_DISPENSE_TIMINGS =
  (65, 70, 73, 80, 98, 260)`, not a liquid-specific calibration. It is a code
  constant on purpose: wrong timings change the dose size.
- The same array is also sent inside `data` for tolerance; the firmware reads
  the root copy on the cloud path.

Keep the safe default: disabled → 422; enabling requires an explicit operator
action. `dispense_left=0` is an explicitly empty bottle, not an authorization.

Do not return `INVALID_DEVICE_ID` from any bottle path.

The open item for flow takeover is a per-liquid/per-bottle timing profile with
bounds, not an arbitrary timing field. See
[`flow-and-dispense-calibration.md`](flow-and-dispense-calibration.md).

## 8. Unknowns

- Exact vendor calibration values for `config[].dispenseTime` (the firmware
  unit is 100 ms; the vendor's per-liquid values are empirical).
- Whether an empty `config` is safe on every firmware path (the parser writes
  an uninitialized `disp-timings` buffer when there are no children).
- Whether `dispenseNumber` is always total capacity or sometimes remaining
  capacity in the vendor backend. The firmware treats it as total capacity.
- Whether `bttl-id` is used by a future firmware path; in 3.0.64 it is only a
  key-table entry.
- Whether the vendor backend binds the bottle record to the device or to a
  bottle ID; the device does not enforce either binding.
- Exact behavior when `dispenseLeft` exceeds `dispenseNumber` (the 16-bit
  subtraction underflows and the bottle is treated as empty).

## 9. Evidence

| Function | Role |
|---|---|
| `FUN_400949bc` | `/get-bottle` request and HTTP status handling |
| `FUN_40094750` | bottle response parser |
| `FUN_40091644` | bottle state transitions |
| `FUN_4009183c` | validation / `bttl-vald=1` |
| `FUN_4009192c` | GPIO13 insert/eject control |
| `FUN_40091a6c` | full bottle reset |
| `FUN_400915d4` | writes `used-dose-cnt` |
| `FUN_40091598` | writes `max-doses` |
| `FUN_40091628` | empty test (`max <= used`) |
| `FUN_4008e0ec` | applies `config` / `disp-timings` |
| `FUN_4009b0c0` | No-App Mode self-authorization |
| `FUN_40091c38` | bottle state getter |
| `FUN_40091c24` | physical bottle state getter |

## 10. Reconciliation with the decompile (2026-10-26)

- **`config` location.** On the cloud path, `FUN_400949bc` calls
  `FUN_40094750(body, 0)`. For `param_2 == 0` the parser reads
  `cJSON_GetObjectItem(root, "config")`, i.e. the **top level** of the response.
  `data` supplies only `dispenseLeft` / `dispenseNumber` (plus the ignored
  `dispenseTime` / `bottleId`). The earlier examples that nested `config` inside
  `data` have been corrected; the backend sends the same array at the root and
  inside `data` for tolerance.
- **Timing values.** Use the firmware's own table, not a guess. The
  device-type-0 dispenser struct (`0x3ffc49b8`, slots at `+0x4c`) initializes to
  `[65, 70, 73, 80, 98, 260]`, which is the same table `FUN_4008df30` hard-codes for
  type 3 (type 4 uses `[47, 47, 47, 47, 47, 100]`). Units are **100 ms**
  (resolved from the dispense loop period and the `%ld.%ld` log; see
  [`flow-and-dispense-calibration.md`](flow-and-dispense-calibration.md)).
  `disp-timings` is persisted as `";t0;t1;…"` (`%c%d` with `;`) and reloaded **by
  position** by `FUN_4008de88`. It is ignored unless it starts with `;`, and
  parsing stops at the first zero. So send a contiguous table from index 0.
  `disp-timings` is not on the restore-to-default wipe list, so vendor-written
  timings may persist until replaced.
- **Side effects checked.** `FUN_4009183c` also calls `FUN_4008eb44` (LED
  indication flags only) and `FUN_40097900(0x14)` (arms the schedule manager).
  No motor or valve call was found in the validation path.
- **Implemented** (`backend/app/services/synchronization.py`): off by default.
  A locked device gets 422 `BOTTLE_INSTALLED_NOT_AUTHORIZED` from the operator
  interlock; enable dispensing with
  `PATCH /admin/devices/{id}/controls {"dispensing_enabled": true}`. Counters
  are topped up to `DOSE_COUNTER_CEILING=100`, so the device does not lock
  itself out as empty. The timing table is the firmware default and is a code
  constant, not configurable.

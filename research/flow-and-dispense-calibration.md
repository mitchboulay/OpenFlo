# Flow and dispense calibration — iFLO 3.0.64

Date: 2026-10-26. Static firmware reconstruction. No dispense was performed and
no device configuration was changed.

## 1. Bottom line

The iFLO does **not measure or regulate flow**. It opens a motorized valve (or
runs a motor, depending on the hardware variant) for a calibrated time:

```text
volume ≈ flow_rate(liquid, head, orifice, temperature) × open_time
```

There is no flow sensor, encoder, load cell or pressure sensor in the dispense
path. The only feedback is the bottle dose/issue state and the low-battery / flood aborts. (Correction, R-1:
there is no valve position feedback either; `FUN_40098b1c` times its own pulse. See `valve-homing-on-wake.md`.) The liquid-specific part
is the cloud's per-dose `dispenseTime` table; the firmware has no concept of
"liquid type".

So yes: the same open time gives a different volume for a different liquid.
The vendor compensates with a calibrated timing table, not with closed-loop
control. We can take that over by serving our own `config` timings.

## 2. Actuator: valve or motor

`FUN_4008d98c()` selects the actuator from bits 3..4 of the dispenser state:

| Selector | Path | Feedback |
|---:|---|---|
| 0 | `FUN_40092074` — H-bridge outputs 8/9 (GPIO9/GPIO10) | none |
| 1 | `FUN_40098b64` — motorized valve | open/closed position only |
| other | fail | — |

### 2.1 Valve path

`FUN_40098b64(1)` opens the valve; `FUN_40098b64(0)` closes it. The routine
pulses the H-bridge and waits up to ~700 ms for `FUN_40098b1c()` to report the
end position:

- `0x400` → closed (`0`)
- `0x200` → open (`1`)
- anything else → `3` (fault)

`FUN_40098b1c()` reads a position value, not a flow value. The valve travel
time is logged as `Valve time = %d` and is used only to detect a stuck valve.
Failures raise `EE_VALVE_OPENING_FAILED` / `EE_VALVE_CLOSING_FAILED`.

`dispenseTime` starts only after the valve reports fully open. The opening and
closing travel still passes liquid, so the delivered volume includes a small
travel contribution. The vendor calibration absorbs it; when calibrating,
measure the whole dispense, not just the timed open interval.

### 2.2 Motor path

`FUN_40092074(1)` sets logic output 8 = 0 and output 9 = 1; `FUN_40092074(0)`
sets both to 0. This is the H-bridge forward/stop path. It has no feedback.

Both paths are **open-loop**: the firmware starts the actuator, waits, and
stops it after a fixed time.

## 3. The dispense loop

`FUN_4008db0c()` is the dispense routine:

1. Check the low-battery cutoff (`FUN_4008d9fc`, `disp-low-bat`).
2. Check that a dose is available (`FUN_40091d1c`).
3. Select the timing entry for the current dose.
4. Open the valve / start the motor (`FUN_4008d98c`).
5. Loop every 10 ticks (100 ms):
   - decrement the remaining time;
   - abort if the bottle becomes empty, the info-issue flag is set, or
     `Is_flood_now()` is true.
6. Close the valve / stop the motor.
7. Extend the awake window by `dose timer + 5 s` and log
   `Dispense [ COMPLETE ]`.

### 3.1 Timing units

The dispense loop uses `vTaskDelay(10)`. The tick is 10 ms, so one iteration is
**100 ms**. The `dispenseTime` value is therefore in **100 ms units**:

- `dispenseTime = 20` → 2.0 s open time
- `dispenseTime = 50` → 5.0 s
- maximum 65535 → 6553.5 s

The log confirms the split:

```text
[ START ] with dose time = %ld.%ld
```

The two values are `time / 10` (seconds) and `time % 10` (tenths). The earlier
`Dispense by valve [ time=%ldsec ... ]` line prints the raw 100 ms count and
labels it `sec`; that label is misleading. The `%ld.%ld` line and the loop
period are the authoritative units.

### 3.2 Which timing entry is used

`FUN_4008e0ec()` stores each `config` entry at:

```text
array[index]  where index = 0..32
```

`FUN_4008db0c()` computes:

```text
used = max_doses - remaining_doses
time = array[used]
```

So `config[0]` is the first dose, `config[1]` the second, and so on. The vendor
can vary the time per dose (for example, to compensate for falling head
pressure as the bottle empties). If `config[used]` is missing or zero, the
dispense is zero-length or fails.

### 3.3 Built-in timing tables and persistence

`FUN_4008df30` sets the actuator type and default table from the hardware
revision:

| Hardware rev | Actuator | Default table (100 ms units) | Seconds |
|---:|---|---|---|
| 3 | valve | `[65, 70, 73, 80, 98, 260]` | 6.5, 7.0, 7.3, 8.0, 9.8, 26.0 |
| 4 | motor | `[47, 47, 47, 47, 47, 100]` | 4.7 × 5, 10.0 |

The defaults are copied only when the unit is not in No-App/demo mode. After
that, `FUN_4008df30` reads the persisted `disp-timings` string and
`FUN_4008de88` parses it by position. The string must start with `;` (for
example `;65;70;73;80;98;260`); parsing stops at the first zero. A gap in the
table therefore truncates the profile.

`disp-timings` is not on the restore-to-default wipe list, so vendor-written
timings may persist until replaced. A `/get-bottle` `config` rewrites both the
array and the persisted string.

### 3.4 Interpreting the default table

The valve table rises from 6.5 s to 9.8 s over the first five doses, then jumps
to 26.0 s for the last. If the cartridge is 36 oz / 6 doses (6 oz ≈ 177 mL,
per the upstream ESPHome model), that shape is consistent with a gravity valve
slowing as the bottle empties: roughly 27 mL/s early and 7 mL/s at the end.

This is an **inference from the bottle size**, not a measurement. The firmware
contains no volume or flow constant; the only numbers are the timings.

## 4. What actually determines the volume

| Factor | Controlled by firmware? | Effect |
|---|---|---|
| Valve open time / motor run time | **Yes**, `config[used].dispenseTime` | primary volume control |
| Liquid viscosity | No | changes flow rate for the same time |
| Bottle head height / fill level | No | flow slows as the bottle empties |
| Valve orifice / tubing | No | fixed by hardware |
| Temperature | No | changes viscosity |
| Battery voltage | Partly (low-battery cutoff only) | motor path speed; valve path mostly unaffected once open |
| Valve health / partial opening | No (no valve feedback at all, R-1) | restricted flow |
| Foaming / aeration | No | volume error |

There is no temperature, viscosity, density or liquid-type compensation in the
dispense code. Search of the image found no `flow`, `ml`, `volume`, `viscosity`
or `liquid` handling in the dispenser path.

## 5. How to take over the calibration

### 5.1 Software takeover (stock firmware)

The only supported control is the `/get-bottle` `config` table. Serve your own
per-dose timings:

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

`config` is a **root-level sibling of `data`** on the cloud path; a copy inside
`data` is ignored. The values above are the firmware's built-in valve defaults,
not a liquid calibration (see §3.3). The device will use whatever table you
send.

These are the firmware defaults; treat them as a starting point, not a liquid
calibration. To calibrate:

1. Measure the delivered volume for a known open time with your liquid,
   bottle, tubing and valve.
2. Compute `Q = volume / time` (mL/s).
3. For a target volume `V`, set
   `dispenseTime = V / Q / 0.1` (rounded to an integer).
4. Repeat at low fill and at the expected temperature; use a per-dose profile
   if the flow changes as the bottle empties.

Because the loop is open-loop, treat the result as a calibration, not a
measurement. Accuracy depends on viscosity, temperature, head height and valve
wear.

**Backend caveat:** the current OpenFLO backend sends a 6-entry timing table
and tops the dose counter to 100. The firmware indexes the table by used dose
count; if more than 6 doses occur between two `get-bottle` syncs, it can index
past the table and read zero. Keep the table contiguous for the maximum doses
between syncs, or top up the counter more often. The firmware also refuses to
dispense if the used count exceeds 32.

### 5.2 Per-liquid profiles

The firmware has no liquid-type field. The backend owns that mapping:

- store a calibration profile per liquid (and optionally per bottle geometry);
- select the profile when the bottle record is authorized;
- serve the corresponding `config` array.

The vendor app's cartridge QR / liquid selection is the likely place where the
vendor chooses the profile; the device only sees the resulting timings. The
device will simply use whatever timings it receives. This is the cleanest
takeover point.

### 5.3 Closed-loop control (requires hardware/firmware changes)

The stock firmware has no flow input. To regulate flow rather than time it, you
would need to add a sensor and custom firmware:

- a Hall-effect turbine flow sensor on a spare GPIO, or
- a load cell / gravimetric measurement, or
- motor current/encoder feedback for the pump variant.

None of these are supported by 3.0.64. The spare logic inputs (GPIO18/19/20)
are used by the stock logic-input layer, and no flow-sensor driver exists in
the image. Treat this as a separate hardware/firmware project, not a backend
setting.

## 6. Safety and failure behavior

- **Low battery:** `FUN_4008d9fc` compares the battery level with `disp-low-bat`
  and cancels/refuses the dispense when below the threshold (unless external
  power is present).
- **Flood/float:** the loop aborts when `Is_flood_now()` is true and logs
  `[ INTERRUPTED ]`.
- **Valve fault:** failure to reach the open/closed position within ~700 ms
  raises `EE_VALVE_OPENING_FAILED` / `EE_VALVE_CLOSING_FAILED` and aborts.
- **Bottle empty / issue:** the loop aborts if the bottle becomes empty or the
  info-issue flag is set.
- **No flow verification:** a partially blocked valve or an empty liquid
  reservoir is not detected by the dispense loop. The only signals are the
  bottle dose count and the valve position.

Do not guess timings for a real dispense. A timing that is too long can
overflow the target; a timing that is too short under-doses. Calibrate on a
bench with a safe liquid and a measured catch vessel.

## 7. Evidence

| Function | Role |
|---|---|
| `FUN_4008db0c` | dispense loop, timing and abort checks |
| `FUN_4008d98c` | select valve vs motor, start actuator |
| `FUN_40098b64` | motorized valve open/close |
| `FUN_40098b1c` | timed valve drive pulse; reads the GPIO *output* register, not a sensor (corrected by `valve-homing-on-wake.md`) |
| `FUN_40092074` | H-bridge motor output |
| `FUN_4008d9fc` | low-battery cutoff |
| `FUN_4008e0ec` | apply `config` → per-dose timing array |
| `FUN_40091d1c` | remaining doses (`max - used`) |
| `FUN_40091d10` | max doses |
| `FUN_40091584` | milliseconds → ticks (200 ms = 20 ticks) |
| `FUN_40091564` | seconds → ticks (1 s = 100 ticks) |

Strings: `Dispense by valve`, `[ START ] with dose time = %ld.%ld`,
`Valve_control`, `Valve time = %d`, `EE_VALVE_OPENING_FAILED`,
`EE_VALVE_CLOSING_FAILED`, `Dispense [ COMPLETE ]`.

## 8. Implemented in OpenFLO (2026-10-26)

- **Actuator for this unit: valve (CONFIRMED_STATIC + runtime).** At boot
  `FUN_40097fdc` reads hardware strap pins GPIO18/19/20 into the hardware-type
  byte (`0x3ffcf281`, read by `FUN_40097f04`). All low → type 4 (motor), PCB 0x005.
  All high → type 3 (**valve**), PCB `0x306`. This unit reports PCB `6.3.0`, so it
  takes the type-3 branch of `FUN_4008df30`: valve selector plus the
  `[65, 70, 73, 80, 98, 260]` table. (An earlier note here inferred "motor" from
  the static initializer alone. That was wrong; it ignored this boot-time
  detection.) Runtime: two remote dispenses (`SE_REMOTE_DISPENSE_OK`, code 8)
  delivered liquid with no audible motor, consistent with a gravity valve. The
  "prime" sound at boot is the valve homing.
- **One dose time, every slot.** The backend tops the dose counter up on every
  `get-bottle`, so `used` restarts at 0 and the early slots are the ones that
  run. An operator dose time (`dose_seconds`, 1–30 s, stored in firmware tenths)
  fills all 6 slots, so the slot index never changes the dose. Unset → the
  firmware table. This resolves the §5.1 caveat for the uniform case; >6 doses
  between syncs still reuse slot values, never zero.
- **`config` is sent at the root only.** The duplicate inside `data` was removed.
- **Calibration helper** on the dashboard: measure one dose at the current
  time → flow (mL/s) → target mL → dose time, clamped to 1–30 s. The change
  applies at the device's next `get-bottle`.

## 9. First measured calibration point (2026-10-26)

| Item | Value |
|---|---|
| Unit | `D8256700000A0001`, valve (type 3, PCB 6.3.0) |
| Liquid | vendor cartridge fluid, bottle as installed (partially used) |
| Command | OpenFLO remote dispense (`remoteDispense`, `SE_REMOTE_DISPENSE_OK`) |
| Dose time | 65 (6.5 s, firmware slot 0) |
| Delivered | **181 mL** (operator measurement, includes valve travel) |
| Flow | **≈ 27.8 mL/s** |

This matches the §3.4 inference (≈ 27 mL/s early; slot 0 ≈ 6 oz / 177 mL). Gravity
flow falls as the bottle empties (the firmware's last slot is 26 s, about 4× slower),
so a single-point calibration over-delivers on a full bottle and under-delivers
near empty. Re-measure at the chosen dose time and fill level.

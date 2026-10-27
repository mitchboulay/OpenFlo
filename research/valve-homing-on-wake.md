# Valve actuation on wake — iFLO 3.0.64

Date: 2026-10-26. Research item R3.1 (R-1 in
the management requirements). Static analysis only,
plus the passive observation in `research/sleep-wake-control.md` §11. No device
interaction.

**Verdict:** on every boot, including every RTC timer wake, the firmware sends
one **close-direction** pulse of about 0.5–0.6 s to the valve H-bridge. No wake
or boot path ever commands the valve open. **Recommended
`homing_ml_per_wake = 0`.**

Evidence classes: **[SC]** static-confirmed (seen in code), **[SI]**
static-inferred, **[OB]** observed (prior hardware notes).

## Method

The analysis used Ghidra 12.2 headless (`Xtensa:LE:32:default`) on the ELF
wrapper from `tools/make_xtensa_elf.py`, as described in
`research/rea-xtensa-workaround.md`. A small decompile/xref post-script was
used, and the project lived in a scratch directory outside the repo. Function
names are Ghidra-generated. A raw-byte scan of `iflo-3.0.64.bin` found **no**
32-bit literal of `0x40098b64`, `0x4008d98c`, `0x4008d9c8` or `0x4008db0c`, so
none of these functions is reached through a function pointer. The direct call
xrefs below are therefore the complete caller set. **[SC]**

## 1. Call path: wake cause → valve

On the ESP32-S2, a deep-sleep wake is a reset, so every wake cause (timer,
button, bottle, ULP, power-up) runs `app_main` from the top. The wake cause is
only consulted later, in `FUN_4008f600` (see `sleep-wake-control.md` §2). The
valve call is **not** conditional on the wake cause. **[SC]**

```
app_main  FUN_4008cc20
  ├─ FUN_4008d7a4            register logic outputs (8 → GPIO9, 9 → GPIO10)
  ├─ io_task FUN_4008cbf8    created; output handler every vTaskDelay(10) = 100 ms
  ├─ FUN_40098aec            "Valve_control" init; sets ready flag 0x3ffcf2d8 = 1
  └─ FUN_4008df30 @4008cd23  Dispenser init (type 3 → selector = valve)
       └─ FUN_4008d9c8 @4008dff1   actuator "stop", unconditional
            └─ FUN_40098b64(0)     valve CLOSE
```

| Function | Callers (complete) | Role |
|---|---|---|
| `FUN_40098b64` | `FUN_4008d98c` (arg 1), `FUN_4008d9c8` (arg 0) | valve drive |
| `FUN_4008d98c` (open/start) | `FUN_4008db0c` only | dispense loop |
| `FUN_4008d9c8` (close/stop) | `FUN_4008db0c` ×3, `FUN_4008df30` ×1 | dispense end/abort, boot init |
| `FUN_4008db0c` (dispense) | `FUN_4008dd14` only | dispenser-task request handler |

The only open path is `FUN_4008dd14 → FUN_4008db0c → FUN_4008d98c →
FUN_40098b64(1)`. It runs only when a dispense request is queued (button,
schedule, remote dispense). Every such request increments the dose count and
emits SE events, and none of that was seen at the 23:02:11 wake. **[SC]** code /
**[OB]** events.

The rest of `FUN_4008df30` touches no actuator. Its recovery loop for an
interrupted dispense (`started_disp_cnt`) calls only `FUN_400968d0` (event) and
`FUN_40091904` (dose-counter increment). **[SC]**

Correction to `sleep-wake-control.md` §11: `FUN_4008d4e0` and `FUN_4008d5cc` are
`logic_inputs` callbacks for the button and bottle events. They are not the
boot valve path, which is `FUN_4008df30 → FUN_4008d9c8`.

## 2. What the routine drives

`FUN_40098b64` (annotated; close branch, open branch mirrored):

```c
if (arg > 1)            { log("Valve action is wrong"); return 0; }
if (!*(u8*)0x3ffcf2d8)  { log("Valve is not ready");    return 0; } // set by FUN_40098aec
*(u8*)0x3ffcf2d9 = arg;  *(u8*)0x3ffcf2d7 = 1;
if (arg == 0) {                      /* CLOSE */
    out_set(8, 0);                   // GPIO9  low            FUN_4008d32c
    out_pulse(9, 1, 5);              // GPIO10 high, 1 pulse, on = 5 handler ticks  FUN_4008d278
    delay_ms(2);                     // FUN_40091584: ms/10 ticks -> 0
    for (n = 70; readback() == 0 && n; n--) delay_ms(10);    // <= 700 ms
    log("Valve time = %d", 70 - n);
    if (n > 30) {                    // finished in < 40 polls (< 400 ms)
        log("Valve is fail. Retry");
        event(0x19);                 // FUN_40096b24
        out_set(8, 0); out_pulse(9, 1, 5);   // no-op if the pulse is still active
    }
} else {                             /* OPEN: GPIO9 pulse, GPIO10 low, event 0x18 */ }
log("Action [ %s ]", "Close" | "Open");
```

| Item | Value | Class |
|---|---|---|
| Close drive | GPIO9 = 0, GPIO10 = 1 (active-high, `FUN_4008d1dc(8,9,0)` / `(9,10,0)`) | [SC] |
| Open drive | GPIO9 = 1, GPIO10 = 0 | [SC] |
| Order | GPIO9 released first, then GPIO10 pulsed | [SC] |
| Pulse width | on-time 5 × 100 ms handler ticks (`FUN_4008d394` in io_task), ≈ **0.5–0.6 s** with tick phase | [SC] structure, [SI] exact width |
| Pulse end | `FUN_4008d394` drops the pin and clears the mode when the countdown hits 0 with pulse count 0 | [SC] |
| Poll | every 10 ms (1 tick), max 70 polls = 700 ms | [SC] |
| Same as dispense-end close | yes; it is the same call | [SC] |

**There is no end-stop or position feedback.** `FUN_40098b1c` reads
`*(u32*)0x3f404004`, which is ESP32-S2 `GPIO_OUT_REG` (GPIO base `0x3f404000` +
4), the **output latch**, not `GPIO_IN_REG` (+0x3c). It returns 0 when the latch
equals exactly `0x400` (only GPIO10 driven), 1 when it equals `0x200` (only GPIO9
driven), and otherwise 3, logged as `[ VALVE_IDLE ] Valve_current_out_state()`.
The loop therefore times the firmware's own pulse and nothing more. "Valve
time" is the pulse length; it is not the valve's travel time. **[SC]**

This corrects `flow-and-dispense-calibration.md` §2.1 and §7, which call
`FUN_40098b1c` "valve position feedback (`0x400` closed / `0x200` open)". The
valve path is open-loop, like the motor path. The `dispenseTime` countdown
starts when the ~0.5 s open pulse ends, not when the valve reports open.

The comparison is exact over GPIO0–31, so any other high output in that bank
reads as 3. GPIO2 (logic output 7) is driven low earlier in `app_main`, and
GPIO15 (output 5) is a candidate. In that case the loop exits at once, logs
`Valve time = 0`, raises event `0x19`, and the retry is a no-op because the
pulse mode is already set (`FUN_4008d278` returns early). The physical pulse
still runs its full ~0.5 s. Either way, the actuation is close-direction only.
**[SC]** logic; [SI] that it happens on this unit. Event `0x19`/`0x18` most
likely corresponds to `EE_VALVE_CLOSING_FAILED`/`EE_VALVE_OPENING_FAILED`
**[SI]**.

## 3. Verdict

| Claim | Class |
|---|---|
| Every boot/wake drives the valve exactly once, in the close direction (GPIO10 pulse ≈ 0.5 s); a retry can only re-assert the same direction | [SC] |
| No boot/wake path calls `FUN_40098b64(1)`; open happens only inside `FUN_4008db0c` | [SC] |
| No end-stop or position input is read | [SC] |
| The valve is a latching, polarity-reversed actuator (timed H-bridge pulse, no hold current); with the valve already closed, a close pulse moves nothing that passes liquid, and the heard sound is the actuator re-seating | [SI] |
| Wake sound at 23:02:11, no liquid, no dispense event, count unchanged; same sound at boot | [OB] |

**The valve only seeks closed.** Liquid cannot flow because of the wake pulse.

## 4. Volume per wake

**0 mL.** No open command is issued, so the open-time × 27.8 mL/s model does not
apply. **[SC]** for the command, **[OB]** for "no liquid".

## 5. Battery cost per wake

The cost is one H-bridge pulse of about 0.5–0.6 s. The coil or motor current is
unknown because the board has not been probed.

| Assumed valve current | Charge per wake |
|---|---|
| 0.2 A | ≈ 0.03 mAh |
| 0.5 A (central) | ≈ **0.08 mAh** |
| 1.0 A | ≈ 0.17 mAh |

For comparison, the Wi-Fi part of a wake (30–180 s at 100–200 mA,
`power-management-analysis.md`) costs about 1–10 mAh. That puts the valve pulse
at roughly **1–5 % of a wake's cost**. It adds no awake time, because it runs
inside the boot sequence before the active window starts. **[SI]**

| Wake interval | Valve cost per day (central) |
|---|---|
| 48 h (`fast-sync-time` default) | ≈ 0.04 mAh |
| 900 s (Testing preset, as observed) | ≈ 7.7 mAh (96 wakes) |

At the default interval this is negligible. On a 900 s Testing cadence it is
real but still smaller than the Wi-Fi cost of the same wakes.

## 6. Recommendation

`homing_ml_per_wake = 0`. Keep the reserved term in
`backend/app/services/dosing.py` at its default of 0. Do not subtract a homing
volume from the bottle.

## 7. Measurement protocol

Not required, because the static volume is 0. If the operator wants to confirm
it cheaply, use the same setup the full protocol would: Testing preset, a dry
weighed cup under the outlet, 10 timer wakes, no dispense queued, and
`/get-schedule` empty. Weigh the cup to 0.1 g and record any EE events.
Expected result: 0.0 g. Any non-zero mass would point to valve seepage, not the
wake routine.

## 8. Unknowns and cheapest next steps

- Valve current and type (latching solenoid or limit-switched motor valve).
  These set the battery figure only. Next step: a scope or current probe on the
  valve leads during a boot.
- Whether GPIO15 is high at boot, which would cause `Valve time = 0` and a
  spurious event `0x19` on every wake. Next step: check the captured device
  event log for `0x19` on wake.
- The exact pulse width within 500–600 ms (tick phase). It does not affect the
  verdict.

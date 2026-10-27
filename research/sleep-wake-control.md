# Sleep / wake control — iFLO 3.0.64

Date: 2026-10-26. Static firmware reconstruction plus existing authorized
capture data. No device configuration was changed.

## 1. Main loop

`FUN_4008cc20` (`app_main`) starts the sleep task and then loops forever:

```c
do {
    vTaskDelay(100);      // 1 s at the ESP-IDF default 100 Hz tick
    FUN_4008f7fc();       // sleep decision / entry
    FUN_40090ee8();       // I/O / housekeeping tick
    FUN_400976a8();       // schedule control tick
} while (true);
```

The sleep handler runs about once per second. It stays awake while work is
pending or the active-time counter is non-zero; otherwise it computes the next
wake, programs the RTC timer and GPIO wake sources, stops Wi-Fi, and enters deep
sleep.

## 2. Wake sources

`FUN_4008f040` registers the wake-event table at boot. Each entry stores an
event ID, a 32-bit wake key, a name, a pin and a callback. The wake key is a
bit flag, not a GPIO number:

| Event | Source | Pin | Wake key | Evidence |
|---|---|---|---|---|
| 0 | Power-up | reset / power | `0x80000000` | `FUN_4008f040` |
| 1 | RTC timer | timer | `0x40000000` | `FUN_4008f040` |
| 2 | User button | GPIO6 | `0x10000000` | `FUN_4008f040` |
| 3 | *reserved* | — | `0x08000000` | `FUN_4008f600` (cause 5 only; **never registered**) |
| 4 | Bottle eject | GPIO13 | `0x20000000` | `FUN_4008f040`, flag `1` |
| 5 | Float switch | GPIO7 | `0x04000000` | `FUN_4008f040` |
| 6 | External power | GPIO16 | `0x04000000` | `FUN_4008f040` |

Events 5 and 6 deliberately share the same key. `FUN_4008f56c` matches on
`(event_key, wake_key)` and returns the **first** match, which is event 6
(External power). The float-switch entry is therefore only distinguishable by
its stored pin/name before lookup, or by reading the GPIO state after wake.

`FUN_4008f600` maps the wake cause to an entry. The cause value comes from
`FUN_400b02a4`, a small custom decoder over the RTC wakeup-state register, not
a direct `esp_sleep_get_wakeup_cause()` call:

| Cause | RTC source | Log text | Event selected |
|---|---|---|---|
| 2 | EXT0 | `Wake up from ext0` | 4, bottle eject |
| 3 | EXT1 | `Wake up from ext1` | 2, user button (pin from `FUN_4008f408`/ext1 status) |
| 4 | timer | `Wake up from timer...` | 1, RTC timer |
| 5 | touchpad | — | 3 (`0x08000000`); no entry exists, so the lookup returns `0xffffffff` |
| 6 | ULP | `Wake up from ULP` | shared `0x04000000` → 6, external power / float |
| other | undefined | `esp_sleep_get_wakeup_cause() = %d` | 0, power-up |

Cause 5 is the ESP32-S2 touchpad cause. This board has no touch hardware, so
event 3 is effectively dead code. ULP is cause 6. `FUN_4008f744` only programs
the two GPIO entries whose key is `0x10000000` (user button) or `0x20000000`
(bottle eject) as RTC GPIO wake sources; the `0x04000000` float/external-power
entry is not programmed there, which is consistent with the ULP monitoring those
inputs. `FUN_4008f47c` stores each event/pin and builds the wake mask.

## 3. Sleep decision

The decision is one function with two entry points: `0x4008f7fc` (called every
main-loop tick) checks the gates, drains pending work and arms the RTC timer;
`0x4008f7d0` is the shared tail that stops Wi-Fi and enters deep sleep. The
effective logic is:

```c
/* 0x4008f7fc */
if (host_mode            /* FUN_4009a5e0, 0x3ffd6d11 */
 || status_bit0          /* FUN_4008e194, 0x3ffc49b8 bit 0 */
 || pending_flag_a       /* FUN_40099cb8, 0x3ffd6d04/05 */
 || pending_flag_b       /* FUN_40093edc, 0x3ffccbdc */
 || (wifi_busy && !force_sleep)   /* FUN_40090254, 0x3ffca5f4 bits 8..13 */
 || (ext_power && !force_sleep))  /* FUN_40098a94, 0x3ffcf2d6 */
    return;                         /* stay awake */

if (active_timer != 0) {            /* DAT_40080dec, 16-bit seconds */
    active_timer--;
    if (!force_sleep && active_timer != 0)
        return;                     /* still in the awake window */
}

log("Time left go to sleep");
drain_dispenser_queues();           /* bounded waits, max 20 x 200 ms */
send_system_event(0x11);
next = next_schedule_wake();        /* FUN_40096da4 */
if (next == 0) next = get("fast-sync-time");
force_sleep = 1;                    /* DAT_40080dfc */
wait_for_tasks(/* 5 x 1 tick */);
arm_rtc_timer(next, 0);             /* FUN_4008f324 -> FUN_400affa0 */
/* fall through to 0x4008f7d0 */
program_gpio_wake();                /* FUN_4008f744 */
stop_wifi();                        /* FUN_400f8e78 */
log("Go sleep...");
final_sleep_call();                 /* 0x4012a4c0, symbol stripped */
```

| Check | Meaning | Evidence |
|---|---|---|
| `FUN_4009a5e0()` | host-mode flag at `0x3ffd6d11`; non-zero blocks sleep | `FUN_4009a5e0` |
| `FUN_4008e194()` bit 0 | status bit at `0x3ffc49b8` used by time/schedule/HTTPS paths | `FUN_4008e194` |
| `FUN_40099cb8()` | true if either pending flag at `0x3ffd6d04` / `0x3ffd6d05` | `FUN_40099cb8` |
| `FUN_40093edc()` | pending flag at `0x3ffccbdc` | `FUN_40093edc` |
| `FUN_40090254()` | 6-bit Wi-Fi/connection state at `0x3ffca5f4` bits 8..13 | `FUN_40090254` |
| `FUN_40098a94()` | external-power-present flag at `0x3ffcf2d6` | `FUN_40098a94` |
| active-time counter | 16-bit seconds at `0x3ffc4aaa`; decrements once per tick | `DAT_40080dec` |
| `force_sleep` flag | at `0x3ffca431`; bypasses the active-timer and Wi-Fi/power returns | `DAT_40080dfc` |
| pending queues | `FUN_40096530`, `FUN_400946f4`, `FUN_400952d8`, `FUN_40095ad8` | bounded waits |

The last two gates are the important ones for remote control: `force_sleep`
makes the device ignore both the remaining active time and the Wi-Fi/external
power holds. It is set by `FUN_4008f350`, which is called from the fast-sync
path (`FUN_4009af58`) and by `FUN_4009ade4` after its countdown reaches zero.


## 4. Timers and defaults

| Setting | Meaning | Default / behavior | Evidence |
|---|---|---|---|
| `act-time-ap` | active window when `registred=0` | 16-bit seconds; observed provisioning burst ≈52 s | `FUN_4008f298`; capture |
| `act-time-sta` | active window when `registred=1` | 16-bit seconds; observed post-registration burst ≈183 s | `FUN_4008f298`; capture |
| demo-mode bonus | adds 1815 s (30.25 min) to the active window | `act-time-* + 0x717` when `FUN_4009aa08()` bit 0 (demo mode) | `FUN_4008f298`, `FUN_4009a814` |
| `fast-sync-time` | next wake when no schedule | default 172,800 s (48 h) if value **≤** `2 × shift-time` **or** value is 0 | `FUN_4009af88`, `DAT_400823a0` |
| `schedule-sync-time` | schedule refresh interval | compared with 86,399 s (24 h − 1) | `FUN_400976a8`, `DAT_40081d5c` |
| `shift-time` | schedule pre-wake lead and minimum guard | schedule wakes `2 × shift-time` early; also the `fast-sync-time` floor | `FUN_40096da4`, `FUN_4009af88` |
| offline/NAM wake | long fallback intervals | base 2,592,000 s (30 d); no matching schedule → 1,209,600 s (14 d) | `FUN_40096da4`, `DAT_40081cd4/8` |

`FUN_4008f324(n, 0)` arms the RTC timer as `n × 1,000,000` microseconds
(`DAT_40080824 = 1,000,000`), so every schedule/fast-sync value above is in
seconds and the log line `Enabling timer wakeup, %lus` is accurate.

`FUN_4008f298` loads the active time from the config store at boot. The 52 s and
183 s observed bursts align with `act-time-ap` (unprovisioned) and
`act-time-sta` (registered); the exact stored values were not dumped, so this
correlation is **INFERRED**.

`FUN_4008fa3c(n)` adds `n` seconds to the active timer **only if it is
currently non-zero**; `n = 0` resets it to the full boot value. `FUN_4008fa7c(n)`
sets it directly. Callers include dispensing, bottle validation, NTP sync,
local HTTP requests, cloud API responses and power/battery handling, so almost
every meaningful activity extends the awake window. `FUN_4008f350` sets the
next wake and the force-sleep flag; `FUN_4008f324` enables the RTC timer.

### Fast-sync mode (the force-sleep mechanism)

Fast-sync is a small state struct at `0x3ffd6d18` (`DAT_40082358`):

| Field | Meaning |
|---|---|
| byte 0 bit 0 | fast-sync active |
| byte 0 bit 2 | fast-sync satisfied / disabled |
| byte 1 | countdown in seconds |
| +4 | `fast-sync-time` value in seconds |

Behaviour:

- `FUN_4009ae28` (boot) loads `fast-sync-time` into +4. If registered, not
  offline/demo/test, the pending flag is 1 and bit 2 is clear, it sets bit 0,
  sets the countdown to 30 and registers a 1 s callback.
- `FUN_4009ade4` (the 1 s callback) decrements byte 1 while bit 0 is set and
  bit 2 is clear. When it reaches 0 it logs `Fast sync mode` and calls
  `FUN_4008f350()` — **force sleep now**.
- `FUN_4009af58` skips the countdown and calls `FUN_4008f350()` immediately if
  bit 2 is clear. This is the `FORCE SLEEP` path.
- `FUN_4009aec0` enables fast-sync (bit 0, pending flag = 1).
- `FUN_4009aef8` marks it satisfied (bit 2), clears bit 0, zeroes the countdown
  and resets the active timer to the full window.
- `FUN_4009afcc` returns true when the fast-sync pending flag is set and bit 2
  (satisfied/disabled) is clear; it does not test bit 0 directly.

`FUN_4008f350()` then does the actual work: `next = next_schedule_wake(); if
(next == 0) next = get("fast-sync-time"); force_sleep = 1; log("Go to sleep on
%lu sec")`. The next main-loop iteration therefore sleeps regardless of the
remaining active time.


## 5. What the backend can control

`FUN_40094c80` calls `FUN_400984d4` on the `data` object. `FUN_400984d4` reads a
`config` object and `FUN_4009849c` writes each key to the config store
(`FUN_40095880` numeric / `FUN_400959d4` string).

Supported `data.config` keys:

| Key | Effect |
|---|---|
| `fast-sync-time` | no-schedule wake interval (seconds; must be **>** 2×shift-time and non-zero) |
| `schedule-sync-time` | how often the device refreshes the schedule |
| `shift-time` | schedule pre-wake lead and `fast-sync-time` floor |
| `act-time-ap` | unprovisioned active window (16-bit seconds) |
| `act-time-sta` | registered active window (16-bit seconds) |
| `bat-min`, `bat-max`, `bat-low`, `bat-crit` | battery thresholds |
| `disp-low-bat` | dispense low-battery threshold |
| `float-en` | float switch enable |
| `ota-low-bat`, `ota-low-wifi` | OTA preconditions |
| `wifi-updated` | Wi-Fi-updated flag |
| `pro-device`, `device-type` | feature/type flags |

The `update-device` response also carries action fields that directly steer
sleep:

| Field | Effect |
|---|---|
| `isScheduleSynced: false` | device fetches `/get-schedule`; returned `timestamp` entries become wake targets |
| `isScheduleSynced: true` | if `FUN_400964f4()` is 0 and `FUN_4009afcc()` is true (fast-sync pending, not satisfied), calls `FUN_4009af58()` → **force sleep on the next tick** |
| `isSettingsSynced: false` | calls `FUN_400988bc()` (settings refresh) |
| `isUpToDate` | selects OTA/no-OTA path |
| `extPowerState` | updates external-power state; may emit system events `0x85`/`0x86` |
| `remoteDispense` | nonce/active flag for remote dispense |

So the only server-side "sleep now" command is `isScheduleSynced: true` while
the device is already in fast-sync mode. `FUN_40096da4` finds the nearest future
schedule and `FUN_4008f350`/`FUN_4008f324` program the timer.

### Schedule pre-wake detail

`FUN_40096da4` does not simply wake at the next timestamp. For each of up to 33
schedule entries, with `delta = timestamp - now` and `shift = shift-time`:

- If `delta < 2 × shift`, return `delta` (wake at the event).
- Else if `delta < fast_sync_time + 2 × shift`, return `delta - 2 × shift`
  (wake **early** by two shift periods) and set the schedule-active flags.
- Otherwise return the base interval (`fast-sync-time`, or 30 days in
  offline/NAM mode).

If no entry matches and the device is offline or in NAM mode, the fallback is
14 days. This is why a schedule can look like an early wake: the device wakes
`2 × shift-time` before the dispense time, syncs, then waits for the event.


## 6. What can force a wake — and what can force sleep

Wake sources that work from deep sleep:

| Method | Works while asleep? | Notes |
|---|---|---|
| Front button (GPIO6) | **Yes** | EXT1 wake; short press may dispense |
| Bottle insert/eject (GPIO13) | **Yes** | EXT0 wake |
| Float switch (GPIO7) | **Yes** | shares the ULP/external-power wake key; ULP monitors it |
| External power (GPIO16) | **Yes** | shares the ULP/float wake key; ULP monitors it |
| Power cycle / reset | **Yes** | power-up event |
| RTC timer | Only if already programmed | schedule or `fast-sync-time` |
| Local HTTP `/dev_info` | **No** | Wi-Fi is off during sleep |
| Cloud/backend request | **No** | device initiates; no inbound path |
| `update-device` config | **Only at next wake** | cannot wake a sleeping device |

There is no network "wake now" path. The device has no persistent Wi-Fi
connection while asleep. The float switch and external-power inputs are watched
by the ULP coprocessor, which wakes the main CPU with cause 6 (ULP); the app
then resolves the shared wake key to the external-power/float event. The ULP
link is **INFERRED** from the shared key, the `ULP_control` strings and
`esp_sleep_enable_ulp_wakeup()`; the ULP program blob itself was not decompiled.

What can force sleep while the device is awake:

| Trigger | Mechanism |
|---|---|
| Active timer reaches 0 | normal path in `FUN_4008f7fc` |
| `force_sleep` flag set | `FUN_4008f350`; bypasses active timer and Wi-Fi/power holds |
| Fast-sync countdown reaches 0 | `FUN_4009ade4` calls `FUN_4008f350` after 30 s |
| `isScheduleSynced: true` while fast-sync active | `FUN_4009af58` calls `FUN_4008f350` immediately |
| Host/OTA/provisioning gates clear | once all gates return 0 |
| Wi-Fi/cloud work drains | bounded queue waits finish |
| Shorten `act-time-*` | takes effect on the next boot/active-window load |

`force_sleep` does not cut power instantly; it takes effect on the next 1 s main
loop iteration, after the device drains its queues and arms the next wake.


## 7. How to schedule or lengthen/shorten wake behavior

### Schedule a wake

1. Backend returns `data.config` if timer changes are needed.
2. Backend returns `isScheduleSynced=false` on `update-device`.
3. Device calls `get-schedule`; return an array of:
   `{"timestamp": <epoch seconds>, "doseCount": 1|2, "cmd": 0|1}` (max 33).
4. `FUN_40096da4` selects the nearest future timestamp. If it is within
   `2 × shift-time`, the device wakes `2 × shift-time` early, syncs, then waits
   for the event; otherwise the RTC timer wakes it at the event.

**Warning:** a schedule entry is a *dispense* schedule. Do not use it as a
wake-only mechanism unless dispensing is intended and approved. For a
non-dispensing wake, use `fast-sync-time` or a physical wake source.

### Force sleep now (while the device is awake)

The only server-side immediate sleep lever is the `isScheduleSynced` field:

1. `FUN_4009afcc()` must be true (fast-sync pending flag set, bit 2 clear)
   and `FUN_400964f4()` must be 0.
2. Return `isScheduleSynced: true` in the `update-device` response.
3. The handler calls `FUN_4009af58()` → `FUN_4008f350()`, which sets the
   `force_sleep` flag and logs `Go to sleep on <n> sec`.
4. On the next 1 s main-loop tick, the device drains queues, arms the next
   wake, stops Wi-Fi and sleeps, even if active time remains.

Caveats: this only works while the device is already awake and has an open
HTTP request; it cannot reach a sleeping device. If fast-sync is not active,
`isScheduleSynced: true` just marks the schedule as synced and does **not**
force sleep. The fast-sync countdown path (30 s after activation) produces the
same result without a server response.

### Change the no-schedule wake interval

Set `data.config.fast-sync-time` to the desired interval in seconds. The
firmware rejects values ≤ `2 × shift-time` and 0, substituting the 172,800 s
default. This only takes effect after the device receives the response; it does
not wake a sleeping unit.

### Extend the awake window for local polling

Set `data.config.act-time-ap` / `act-time-sta` (seconds, 16-bit). The device
stays awake for that long after a wake, allowing the local controller to poll
`/dev_info`. Increasing it increases battery use. Demo mode adds 1815 s. The
stored value is applied when the active window is next loaded (boot/reset); it
does not extend a window that is already running.


### Refresh schedule more often

Set `data.config.schedule-sync-time`. The schedule tick compares elapsed time
against 86,399 s before fetching a new schedule.

## 8. Observed patterns

From `research/mission-006.md` and `research/event-timeline.md`:

| Session | Duration | Gap before next |
|---|---:|---:|
| 1 | 107 s | 3.3 min |
| 2 | 189 s | 28.9 min |
| 3 | 187 s | 26.8 min |
| 4 | 33 s | 3.3 min |
| 5 | 56 s | 60+ min |

Earlier first-provision captures: 52 s and 183 s bursts, 201 s gap, then 27+
minutes of silence.

Interpretation:

- 52 s and 183 s match the AP/STA active windows (`act-time-ap` vs
  `act-time-sta`) **INFERRED**.
- 107–189 s bursts are consistent with the active window plus activity kicks
  (NTP, cloud API, local HTTP, bottle validation) via `FUN_4008fa3c(n)`.
- The 26.8/28.9 min gaps are consistent with a schedule pre-wake of
  `2 × shift-time` (30 min if `shift-time = 900 s`), followed by a short active
  burst. This is a **code-derived hypothesis**, not yet confirmed against the
  stored `shift-time`.
- The 3.3 min gaps look like retry/backoff or setup traffic, not the steady
  idle interval.
- The true idle wake interval is **not yet measured**. The 48 h fast-sync default
  suggests long idle sleeps, but the config may have been overridden.
- While asleep there are no ARP/DHCP frames; Wi-Fi is off.

## 9. Unknowns

- Exact names of the `FUN_4009a5e0` / `FUN_4008e194` / `FUN_40099cb8` /
  `FUN_40093edc` / `FUN_40090254` gate flags (addresses are known; semantic
  labels are still inferred).
- Exact stored `act-time-ap` / `act-time-sta` values.
- Exact `shift-time` default and the resulting minimum `fast-sync-time`.
- Whether `update-device` config persists across power loss (FS write suggests
  yes; not power-cycle tested).
- Final ESP-IDF sleep symbol at `0x4012a4c0`.
- Exact selection of the 14 d vs 30 d offline/NAM constants (the branches are
  known; the mode-flag names are not fully confirmed).
- Whether `Set_sync_time` / `offline_settings` exposes a local time-sync path.
- What enables fast-sync remotely, if anything, beyond schedule proximity and
  the boot-time pending flag.
- Whether the ULP records which of the two shared pins (GPIO7 float / GPIO16
  external power) woke the device, or the app reads GPIO state after wake.


## 10. Safe experiment plan (later mission)

1. Capture 24–48 h of baseline wake/sleep with no app or cloud interaction.
2. Record wake cause (timer/GPIO/power) and duration.
3. Only on a bench device, set a benign `act-time-sta` change and measure wake
   duration; no schedule, no dispense.
4. Only with explicit approval, test `fast-sync-time` shortening and observe
   battery/wake frequency.
5. Do not use schedule entries for wake-only testing; they can dispense.

## 11. Observation: valve actuation on timer wake (2026-10-26)

At 23:02:11 UTC the lab device (valve, type 3) woke on its RTC timer (900 s
after the previous wake; no SE/EE wake-cause events) and the operator heard a
short "priming" sound. No liquid came out, no dispense event was reported, the
dispense count was unchanged, and no remote dispense was queued. This is the
same sound heard at boot after the reset. Working hypothesis (INFERRED,
untraced): the motorized valve's position check/homing on wake (`FUN_40098b1c`
open/closed feedback; boot path `FUN_4008d4e0`/`FUN_4008d5cc`). It is harmless,
and at the 48 h check-in interval it occurs at most every 48 h. Research item:
trace the wake-time valve routine to confirm, and measure its battery cost.

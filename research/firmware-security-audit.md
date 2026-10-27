# Firmware security audit — upstream ESPHome iFLO replacement

Source: `demitryk1/SmartHome/iFLO/ESP_Home_Builder_iflo.yaml` (commit `b730d9c`, 2026-10-17).
Audit date: 2026-10-26. Auditor: static analysis only. No firmware was flashed or executed.

Repository has **no LICENSE file**. All code is reference material only until licensing is clarified.

---

## Issue 1 — No deep sleep

**Severity:** Critical

**Evidence:**
```yaml
wifi:
  power_save_mode: HIGH
  fast_connect: true
```

No `deep_sleep:` component anywhere in the YAML. `power_save_mode: HIGH` is WiFi DTIM-based power saving (the radio listens less frequently while associated). It does not put the ESP32-S2 into deep sleep.

**Failure scenario:** The ESP32-S2 draws ~20-40 mA while idling with WiFi active. On 4xAA alkaline batteries (~2500 mAh usable at the ~3.3V regulator dropout), expected runtime is 60-125 hours (2.5-5 days). The author confirms "batteries only last 2 days." The original firmware achieves months of battery life by powering WiFi off entirely between wake windows (confirmed: no frames observed between bursts in our captures).

**Recommended mitigation:** Implement ESP-IDF deep sleep with RTC timer wake. ESPHome's `deep_sleep:` component supports this, but requires careful integration with the dispensing scheduler — the device must wake, check whether a dispense is due, execute if needed, then return to sleep. This is the single largest gap between the replacement and original firmware.

---

## Issue 2 — Motor activation on startup

**Severity:** Medium

**Evidence:**
```yaml
on_boot:
  priority: 600
  then:
    - switch.turn_off: motor_in1
    - switch.turn_on: motor_in2
    - delay: 250ms
    - switch.turn_off: motor_in1
    - switch.turn_off: motor_in2
```

Motor GPIO switches are configured with `restore_mode: ALWAYS_OFF`, which means the GPIO framework drives them low before `on_boot` runs. The `on_boot` sequence then drives IN2 high for 250ms — an intentional reverse-brake pulse to ensure the motor is in a known stopped state.

**Failure scenario:** On every boot (including unexpected power glitches, watchdog resets, or OTA reboots), the motor receives a 250ms reverse pulse. If the H-bridge outputs are floating or in an undefined state before the GPIO framework initializes (the hardware power-on interval before firmware takes control), the motor could twitch unpredictably. On the ESP32-S2, GPIO state during the bootloader phase (before app code runs) is determined by pull resistors and boot strapping — the Mixic MX08H H-bridge may interpret floating inputs as active.

**Recommended mitigation:** Add external pull-down resistors on GPIO9 and GPIO10 to ensure the H-bridge inputs are low during the hardware boot interval. In firmware, remove the 250ms reverse pulse from `on_boot` — if `ALWAYS_OFF` successfully drives both pins low, the motor is already stopped and the pulse is unnecessary.

---

## Issue 3 — Dispensing duration from string parsing

**Severity:** Medium

**Evidence:**
```cpp
int runtime_seconds = atoi(id(volume_option).c_str());
// volume_option is one of: "3 oz", "6 oz", "9 oz", "12 oz"
// atoi("6 oz") → 6
// atoi("") → 0
// atoi("oz 6") → 0
```

Used in three places: the motor run delay (`delay: !lambda`), the volume deduction (`remaining_volume -= runtime_seconds`), and the dispenses-left calculation.

**Failure scenario:** `atoi` stops at the first non-numeric character, so "6 oz" correctly yields 6. However, if the option strings are ever reordered, renamed (e.g., "6 fl oz" still works, but "Six oz" yields 0), or if the global's `restore_value` loads a corrupted string from flash, `atoi` returns 0. A zero-duration dispense still activates the motor (IN1 ON → 250ms → IN1 OFF → 0ms delay → IN2 ON → 500ms), deducts 0 oz from the volume counter, and reports success — the motor runs briefly but dispenses nothing while the count decrements.

Actually — re-reading the code: the deduction is `remaining_volume -= runtime_seconds` where runtime_seconds=0, so the volume counter does NOT decrement. But the `days_since_dispense` resets to 0 and `last_dispense` updates, so the scheduler believes a dispense occurred. The next scheduled dispense won't fire for another full interval.

**Recommended mitigation:** Parse the volume as an integer at selection time and store it in a separate `int` global. Validate that the parsed value is one of {3, 6, 9, 12} before allowing dispensing.

---

## Issue 4 — No motor timeout or watchdog

**Severity:** High

**Evidence:**
```yaml
- switch.turn_on: motor_in1
- switch.turn_off: motor_in2
- delay: 250ms
- switch.turn_off: motor_in1
- delay: !lambda |
    int runtime_seconds = atoi(id(volume_option).c_str());
    return runtime_seconds * 1000;
- switch.turn_on: motor_in2
- delay: 500ms
- switch.turn_off: motor_in2
```

The motor run duration is governed entirely by software delays. There is no hardware watchdog, no maximum-duration guard, and no interrupt-safe motor shutoff.

**Failure scenario:** If the ESPHome runtime crashes, enters a tight loop, or the script is interrupted by a higher-priority task during the motor-on delay, the motor remains energized until the ESP32 resets (watchdog timeout, typically 5-15 seconds). At 12 oz (12 seconds motor run), the maximum intended duration is already long. A stuck motor could drain the battery rapidly or, in a worst case, overpressure the dispense mechanism.

**Recommended mitigation:** Add a hardware timer or ESPHome `on_shutdown` handler that forces both motor GPIOs low. Add a maximum motor runtime check (e.g., 15 seconds) enforced by a separate watchdog script that runs independently of the dispense sequence.

---

## Issue 5 — Script restart during motor operation

**Severity:** High

**Evidence:**
```yaml
- id: dispense_sequence
  mode: restart
```

`mode: restart` means if `dispense_sequence` is called while already running, the current execution is cancelled and the script starts over from the beginning.

**Failure scenario:** If the front button is pressed during an active dispense, or if the scheduled cron and a manual dispense overlap, the running script is killed mid-motor-operation. The motor's current GPIO state (e.g., IN1=HIGH driving the pump) is NOT cleaned up by the restart — ESPHome's script restart does not execute any cleanup or "finally" block. The motor remains in its last-set state while the script restarts from the top, which begins by setting IN1 OFF → IN2 ON (brake pulse). The net effect: the motor may reverse abruptly mid-dispense, or run for a brief uncontrolled interval between the kill and the restart's first instruction.

**Recommended mitigation:** Change to `mode: queued` (runs the next invocation after the current one finishes) or `mode: single` (ignores duplicate calls while running). Add a `script.wait` or motor-off guard at the very start of the script to ensure a clean starting state regardless of how the script was entered.

---

## Issue 6 — Scheduling edge cases

**Severity:** Low

**Evidence:**
```cpp
// Month rollover:
if (target_time.month > 12) {
  target_time.month = 1;
  target_time.year += 1;
}
target_time.recalc_timestamp_utc();

// Cron trigger:
- cron: "0 0 12 * * *"
```

**Failure scenarios:**

1. **DST transitions:** The cron fires at "12:00" in the configured timezone (`America/Chicago`). On the spring-forward day, 12:00 is unambiguous. On the fall-back day, 12:00 occurs once (CDT already ended). No double-fire risk at noon. However, the `days_since_dispense` counter increments once per cron fire — if the ESP32 reboots and NTP resynchronizes across a DST boundary, the cron could fire at an unexpected wall-clock time.

2. **February edge cases:** Setting `target_time.day_of_month = 15` then `recalc_timestamp_utc()` is fine for all months. Setting `day_of_month = 1` with `month += 1` is fine. The "1st of Month" schedule does not set day 30 or 31, so February rollover is not a problem for the current schedule options. However, the "Every 30 Days" path uses timestamp arithmetic (`target_timestamp + days_left * 86400`), which correctly handles month boundaries.

3. **Counter persistence:** `days_since_dispense` has `restore_value: true` but resets to 0 on successful dispense. If the device reboots without dispensing, the counter survives. If flash wear or corruption loses the value, it resets to the `initial_value: "0"`, which would cause an immediate dispense on the next cron check if the schedule interval has technically elapsed.

**Recommended mitigation:** Store the timestamp of the last dispense (already done in `last_dispense` global) and compute `days_since_dispense` from the delta rather than incrementing a counter. This eliminates drift from missed cron fires, reboots, or counter corruption.

---

## Issue 7 — Hardcoded API encryption key

**Severity:** Critical

**Evidence:**
```yaml
api:
  encryption:
    key: "7As1Bj…(redacted; full key is public in demitryk1/SmartHome)"
```

This key is published in a public GitHub repository. It is the Noise protocol encryption key used for the ESPHome native API (Home Assistant integration). Anyone who knows this key and can reach the device on the network can issue commands, including manual dispense and factory reset.

**Failure scenario:** Any device flashed with this YAML, or any fork of it, shares the same API key. An attacker on the same WiFi network (or via the fallback AP — see Issue 11) can connect to the ESPHome native API, enumerate entities, and trigger motor commands.

**Recommended mitigation:** Generate a unique key per device. ESPHome's `api: encryption: key:` should use `!secret api_key` with a per-installation secret. The published YAML should document this as a required change.

---

## Issue 8 — OTA encryption placeholder

**Severity:** High

**Evidence:**
```yaml
ota:
  - platform: esphome
    encryption:
```

The `encryption:` key is present but has no value. In ESPHome, an empty `encryption:` under `ota:` is syntactically valid but does not enable OTA encryption — it silently falls through to no encryption.

**Failure scenario:** OTA firmware updates are accepted without authentication or encryption. Any device reachable on the network (or via the fallback AP) can be reflashed with arbitrary firmware by anyone who knows the ESPHome OTA protocol. Combined with the fallback hotspot (Issue 11), an attacker within WiFi range could reflash the device entirely.

**Recommended mitigation:** Set an explicit OTA password: `ota: password: !secret ota_password`. Or use the `safe_mode:` component to require physical button hold for OTA.

---

## Issue 9 — Bottle state persistence on power cycle

**Severity:** Low

**Evidence:**
```yaml
globals:
  - id: remaining_volume
    type: int
    restore_value: true
    initial_value: "36"
  - id: last_remaining_volume
    type: int
    restore_value: true
    initial_value: "36"
```

On bottle removal:
```cpp
id(remaining_volume) = 0;
```

On bottle insertion:
```cpp
id(remaining_volume) = id(last_remaining_volume);
```

Both globals have `restore_value: true`, which persists them to flash.

**Failure scenario:** The sequence: bottle removed → `remaining_volume` set to 0 and saved to flash → power loss before reinsertion → on reboot, `remaining_volume` restores as 0 from flash, `last_remaining_volume` restores as the pre-removal value → bottle sensor reads "installed" at boot → the boot sequence does NOT execute the `on_press` handler (it only fires on state change, not initial state) → device reports 0 remaining volume with a bottle installed.

The boot sequence does check `volume_left > 0` and sets bottle status, but it reads `remaining_volume` which is 0. The user must manually reset dispenses.

**Recommended mitigation:** On boot, if bottle sensor is ON and `remaining_volume` is 0 but `last_remaining_volume` is non-zero, restore from `last_remaining_volume`. Or: don't zero `remaining_volume` on bottle removal — instead use the bottle sensor's live state to gate dispensing.

---

## Issue 10 — No NTP fallback or validation

**Severity:** Medium

**Evidence:**
```yaml
time:
  - platform: sntp
    id: sntp_time
    timezone: "America/Chicago"
```

The cron handler checks:
```cpp
if (!time_now.is_valid() || time_now.year < 2020) return;
```

**Failure scenario:** If WiFi connects but NTP is unreachable (firewall, DNS failure, NTP server down), the ESP32's RTC starts from epoch (1970) or from the last known time if `restore_value` is configured for time (it is not here). The `year < 2020` check catches the epoch case. However, if the ESP32 RTC drifts significantly between reboots (no battery-backed RTC on the S2), or if NTP returns a wrong time (compromised server, network issue), the cron could fire at an incorrect wall-clock time. There is no secondary time source, no plausibility check, and no notification to the user that time sync has failed.

**Recommended mitigation:** Add a `on_time_sync:` handler that logs successful sync. Add a text sensor that displays "Time not synced" when `!time_now.is_valid()`. Consider adding a second NTP server pool. For dispensing, require that time has been synced at least once since boot before allowing scheduled (not manual) dispenses.

---

## Issue 11 — WiFi fallback hotspot with known credentials

**Severity:** High

**Evidence:**
```yaml
wifi:
  ap:
    ssid: iflo Fallback Hotspot
    password: iflo1234
```

Combined with:
```yaml
web_server:
  port: 80
  version: 3
  auth:
    username: iflo
    password: !secret test__web_password
```

**Failure scenario:** If the configured WiFi network is unavailable (router reboot, SSID change, range issues), the device creates an access point with a known SSID and password published in the GitHub repo. Anyone within WiFi range can connect to this AP, access the web UI (whose password may also be known — see Issue 12), and trigger motor commands, change WiFi credentials, or upload firmware (via OTA, Issue 8).

The SSID name "iflo Fallback Hotspot" identifies the device type to anyone scanning, making targeted attacks trivial.

**Recommended mitigation:** Use `!secret` for the AP password. Disable the web server when in AP mode (or restrict it to WiFi configuration only). Consider disabling the fallback AP entirely for battery-powered deployments where the device should simply retry the configured network.

---

## Issue 12 — Test credential naming

**Severity:** Low

**Evidence:**
```yaml
web_server:
  auth:
    username: iflo
    password: !secret test__web_password
```

**Failure scenario:** The `test__` prefix convention typically indicates a development/testing credential. While the actual password is in the secrets file (not the YAML), the naming pattern suggests it may be a weak or default test password that was not changed for production deployment. The README confirms the web credentials are `iflo` / `iflo1234`, and the secret name suggests this was the intent.

If the web password is `iflo1234` (matching the README), it is trivially guessable by anyone who finds the GitHub repo.

**Recommended mitigation:** Use a strong, unique password. Rename the secret to remove the `test__` prefix to signal production intent. Document that the web password MUST be changed from the example in the README.

---

## Summary

| # | Issue | Severity | Category |
|---|---|---|---|
| 1 | No deep sleep | Critical | Power |
| 7 | Hardcoded API key | Critical | Security |
| 4 | No motor timeout | High | Safety |
| 5 | Script restart during motor operation | High | Safety |
| 8 | OTA encryption placeholder | High | Security |
| 11 | Fallback hotspot with known credentials | High | Security |
| 2 | Motor activation on startup | Medium | Safety |
| 3 | String parsing for dispense duration | Medium | Reliability |
| 10 | No NTP fallback | Medium | Reliability |
| 6 | Scheduling edge cases | Low | Reliability |
| 9 | Bottle state on power cycle | Low | Reliability |
| 12 | Test credential naming | Low | Security |

**Overall assessment:** The upstream ESPHome firmware is a functional proof-of-concept that demonstrates the hardware can be locally controlled. It is not production-ready. The two critical issues (no deep sleep rendering battery operation impractical, and a published API key) would need to be resolved before any deployment. The motor safety issues (no timeout, restart-during-operation) represent physical risks that the original firmware likely handles at the hardware timer level.

# Upstream ESPHome implementation review

Source: https://github.com/demitryk1/SmartHome/tree/main/iFLO

Repository: `demitryk1/SmartHome`. Single commit to the `iFLO/` directory: `b730d9c` (2026-10-17, "Update ESP_Home_Builder_iflo.yaml"). No LICENSE file in the repository. **All code must be treated as reference material only — not reusable without explicit permission from the author.**

## Repository contents

| File | Purpose |
|---|---|
| `iFLO/README.md` | Installation instructions and feature overview |
| `iFLO/ESP_Home_Builder_iflo.yaml` | Complete ESPHome device configuration |
| `iFLO/iflo-firmware.factory.bin` | Pre-built ESPHome firmware image (988,448 bytes) |
| `iFLO/Pinout.png` | Annotated PCB photo with GPIO assignments and connector key |
| `iFLO/Dashboard.png` | Screenshot of the ESPHome web UI showing controls and sensors |
| `iFLO/Helping_Hands.png` | Photo of the flashing setup using helping-hands clips |

## 1. MCU variant

**ESP32-S2 SOLO**, 4 MB flash. The YAML declares:

```yaml
esp32:
  variant: ESP32S2
  flash_size: 4MB
  framework:
    type: esp-idf
```

The pinout image shows an Espressif-branded QFN package on the PCB. The ESP32-S2 is a single-core Xtensa LX7 at 240 MHz with native USB — a different chip from the plain ESP32 (dual-core LX6). This is consistent with our Mission 004 observation of `board=esp32` in the mDNS TXT record, which is the generic family name.

The author identifies it as "ESP32-S2 SOLO" in the README. The firmware binary (988 KB, starts with `0xFF` padding, contains `esphome`, `iflo`, `ESP32`, `esp-idf` strings) is a factory image that includes the bootloader and partition table, not a bare app image (a bare app image starts with magic byte `0xE9`).

## 2. GPIO assignments

From the YAML configuration cross-referenced against the pinout image:

| GPIO | Function | YAML ID | Notes |
|---|---|---|---|
| 6 | Front button (SW1) | `binary_sensor` (unnamed) | `INPUT_PULLUP`, inverted |
| 7 | 2.5mm DC jack (PIP) | — | Labeled on pinout, not used in YAML |
| 8 | Battery ADC | `battery_voltage` | ADC with 12dB attenuation |
| 9 | Motor IN1 (H-bridge) | `motor_in1` | `ALWAYS_OFF` restore mode |
| 10 | Motor IN2 (H-bridge) | `motor_in2` | `ALWAYS_OFF` restore mode |
| 13 | Bottle sensor | `bottle_sensor` | `INPUT_PULLUP`, inverted |
| 17 | Side reset button (Key1) | — | Labeled on pinout, not used in YAML |
| 39 | LED 1 — Cloud Connected | `LED1` / `LED_1` | LEDC PWM output |
| 40 | LED 2 — WiFi | `LED2` / `LED_2` | LEDC PWM output |
| 41 | LED 3 — Battery | `LED3` / `LED_3` | LEDC PWM output |
| 42 | LED 4 — Bottle | `LED4` / `LED_4` | LEDC PWM output |
| 36 (RXD0) | UART RX | — | Labeled for flashing |
| 37 (TXD0) | UART TX | — | Labeled for flashing |
| 0 | Boot mode select | — | Square pad labeled "Boot Loader" on pinout |

Additional GPIOs labeled on the pinout but not used in the YAML:

- **GPIO7**: 2.5mm DC jack, labeled "PIP (WC_5P)" — possibly external power input
- **GPIO15 (IO15)**: 5.5mm side DC jack IN_B (WC_P5) — connects to H-bridge U3
- **GPIO16 (IO16)**: 5.5mm side DC jack IN_A (WC_P5) — connects to H-bridge U3
- **GPIO17 (IO17)**: Side reset button Key1 (WC_5P)

The pinout image also shows a "Side Interface Board" with a white 5-pin connector, which connects to the side 5.5mm jack and the side reset button. These are reportedly used with the Pro model.

## 3. Motor driver implementation

Two H-bridge motor drivers identified as **Mixic MX08H-32788H** (markings partially obscured by conformal coating).

| Driver | Controlled by | Purpose |
|---|---|---|
| U1 | GPIO9 (IN1), GPIO10 (IN2) | Drives the dispensing motor |
| U3 | GPIO15 (IN_B), GPIO16 (IN_A) | Drives the 5.5mm side jack output (Pro model) |

Only U1 is used in the ESPHome YAML. U3's GPIOs (15, 16) are identified on the pinout but not configured.

The H-bridge control pattern is standard: IN1=HIGH/IN2=LOW drives the motor forward, IN1=LOW/IN2=HIGH drives reverse, both LOW = brake/coast.

## 4. Button behavior

Single front button on **GPIO6** (`INPUT_PULLUP`, inverted — active low).

| Press duration | Action |
|---|---|
| 350 ms – 3,000 ms | Execute `dispense_sequence` script |
| 5,000 ms – 10,000 ms | Execute `reset_sequence` script (resets remaining volume to 36 oz) |

Presses shorter than 350 ms or between 3–5 seconds are ignored. The ESPHome `on_click` handler defines these as discrete ranges with no overlap.

## 5. Bottle detection

**GPIO13**, `INPUT_PULLUP`, inverted. A physical switch that closes when the bottle is seated.

| Event | Behavior |
|---|---|
| Bottle inserted (`on_press`) | Restores `remaining_volume` from `last_remaining_volume`, updates UI to "Installed", turns off LED4 |
| Bottle removed (`on_release`) | Sets `remaining_volume` to 0, updates UI to "Removed", turns on LED4 |

The `last_remaining_volume` global preserves the pre-removal volume so reinserting the same bottle restores the count. This is a software heuristic — the device cannot distinguish between the same bottle being reinserted and a different bottle.

## 6. LED behavior

Four LEDs driven via LEDC PWM (monochromatic light platform):

| LED | GPIO | Meaning when ON | Blinking meaning |
|---|---|---|---|
| LED1 (Cloud) | 39 | Unit is powered on | Script running (dispense or reset) |
| LED2 (WiFi) | 40 | WiFi connected | WiFi disconnected |
| LED3 (Battery) | 41 | Battery at 20% or below | — |
| LED4 (Bottle) | 42 | Remaining dispenses = 0 or bottle removed | — |

The "fast_blinking" effect uses ESPHome's built-in `strobe` effect. All LEDs are `disabled_by_default: true`, meaning they do not appear as controllable entities in Home Assistant by default.

## 7. Battery measurement

**GPIO8** configured as an ADC input with:

```yaml
attenuation: 12dB
filters:
  - multiply: 6.00
  - sliding_window_moving_average:
      window_size: 5
      send_every: 1
```

The 6.0x multiplier compensates for a voltage divider on the PCB. With 12dB attenuation, the ESP32-S2 ADC reads 0–2.5V, so the effective measurement range is 0–15V. The battery percentage calculation maps:

- **4.00V = 0%**
- **5.35V = 100%**

This range is consistent with 4x AA batteries (nominal 6.0V fresh, ~4.0V depleted). The update interval is 60 seconds. A 5-sample sliding window average smooths the reading.

LED3 lights when battery percentage drops to 20% or below.

## 8. Dispensing sequence

The `dispense_sequence` script:

```
1. LED1 → fast blinking (visual feedback)
2. Check: bottle sensor OFF → abort ("No Bottle")
3. Check: remaining_volume < requested oz → abort ("No Fluid")
4. Status: "Dispensing..."
5. motor_in1 ON, motor_in2 OFF         (forward)
6. delay 250 ms                         (startup)
7. motor_in1 OFF                        (coast, motor spinning)
8. delay N * 1000 ms                    (run time = oz * 1s)
9. motor_in2 ON                         (reverse/brake)
10. delay 500 ms                        (braking)
11. motor_in2 OFF                       (all off)
12. Decrement remaining_volume by N oz
13. Record timestamp, reset days_since_dispense
14. Update UI
15. LED1 → solid (done)
```

The dispensing duration is `atoi(volume_option) * 1000` ms. For a 6 oz setting, the motor runs for approximately 6.75 seconds total (250 ms startup + 6000 ms run + 500 ms brake).

**Volume assumption:** 1 second of motor run = 1 fluid ounce. This is a fixed calibration with no adjustment mechanism. The author does not document how this was determined.

## 9. Scheduling implementation

Six schedule options stored in the `schedule_option` global:

| Option | Trigger rule |
|---|---|
| Off | No automatic dispensing |
| Every 7 Days | `days_since_dispense >= 7` |
| Every 14 Days | `days_since_dispense >= 14` |
| Every 30 Days | `days_since_dispense >= 30` |
| 1st of Month | `day_of_month == 1` |
| 1st & 15th of Month | `day_of_month == 1` or `day_of_month == 15` |

A daily SNTP cron fires at **noon** (`0 0 12 * * *`) and evaluates the schedule. For interval-based schedules, `days_since_dispense` increments daily at noon and triggers dispensing when the threshold is reached. For date-based schedules, the day of month is checked directly.

Time source: SNTP from `pool.ntp.org`, timezone hardcoded to `America/Chicago`.

The `calculate_next_dispense` script computes and displays the next expected dispense date in the UI.

## 10. Persistent configuration

Five ESPHome globals with `restore_value: true` (persisted to flash via the ESP32's NVS partition):

| Global | Type | Initial value | Purpose |
|---|---|---|---|
| `remaining_volume` | int | 36 | Current remaining volume in oz |
| `last_remaining_volume` | int | 36 | Volume before last bottle removal (for reinsertion restore) |
| `schedule_option` | string | "Off" | Selected schedule |
| `volume_option` | string | "6 oz" | Selected dispense amount |
| `last_dispense` | string | "Never" | Timestamp of last dispense |
| `days_since_dispense` | int | 0 | Days elapsed since last dispense |

All values survive reboots and power loss. The `reset_sequence` restores `remaining_volume` and `last_remaining_volume` to 36 (the capacity of an iFLO bottle in oz).

## 11. Authentication and local API exposure

Three interfaces, each with separate auth:

| Interface | Auth | Details |
|---|---|---|
| ESPHome web server (port 80) | HTTP Basic Auth | Username `iflo`, password from `!secret test__web_password` |
| ESPHome native API | Encryption key | `7As1Bj…(redacted; full key is public in demitryk1/SmartHome)` (hardcoded in YAML) |
| OTA updates | Encryption | Platform `esphome`, encryption enabled (key not shown) |

The ESPHome native API encryption key is committed in plaintext in the public repository. The web server password references a secrets file. The OTA encryption block is present but the key is not shown (likely also in secrets).

The web server runs ESPHome Web Server v3, which provides a Material Design dashboard with entity controls and sensor readouts.

## 12. Firmware installation and recovery

### Flashing procedure (from README)

1. Remove hose, remove two bottom screws
2. Disconnect four color-coded plugs from the PCB
3. Remove board housing (two screws, press front button to clear casing)
4. Attach USB-serial converter: VCC, GND, TXD, RXD (may need to swap TX/RX)
5. Short the bootloader pads (square pad = GPIO0 to GND)
6. In ESPHome Builder (Home Assistant): create device → advanced → import YAML
7. Plug in USB-serial converter
8. Wait ~30 seconds, remove bootloader short
9. Flash

The author reports doing this twice — once with soldered wires, once with helping-hands clips. The helping-hands approach was preferred.

### Recovery

After the initial USB flash, subsequent updates can use OTA over WiFi. If the firmware fails to boot, the USB-serial recovery path remains available by re-entering bootloader mode (GPIO0 to GND).

If WiFi credentials are wrong, the ESPHome fallback hotspot (`iflo Fallback Hotspot`, password `iflo1234`) activates, providing a captive portal for WiFi reconfiguration.

## Hardware compatibility with our device

Our device reports:
- `pcbVersion: "6.3.0"` (from `GET /dev_info`)
- `firmwareVersion: "3.0.64"`
- `board=esp32` (from mDNS TXT)
- `deviceType: 0` (Consumer HVAC)

The upstream author does not state their PCB revision. The YAML and pinout are based on their specific board, which may or may not match PCB 6.3.0. **GPIO assignments must be verified against our hardware before any firmware work.** The motor driver IC markings, connector pinouts, and ADC voltage divider ratio could differ between revisions.

## Licensing

**No LICENSE file exists in the repository.** Under default copyright law, the code is the author's intellectual property and cannot be copied, modified, or distributed without permission. For OpenFLO purposes, this implementation is reference material only. The hardware documentation (pinout, component IDs, GPIO assignments) is factual information derived from physical inspection and can be independently verified.

If OpenFLO were to adopt an ESPHome-based approach, the configuration would need to be written independently, informed by but not copied from this reference.

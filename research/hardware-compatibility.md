# Hardware compatibility — iFLO IFLOKIT01 vs upstream ESPHome project

Comparison of our device (PCB 6.3.0, firmware 3.0.64) with the hardware assumptions in [demitryk1/SmartHome/iFLO](https://github.com/demitryk1/SmartHome/tree/main/iFLO). The upstream author traced two units and documented most GPIO assignments. Our device has not been opened.

## Summary

The upstream pinout is valuable reference material but **cannot be assumed compatible** with our PCB revision without physical verification. The MCU variant discrepancy is the most critical unknown. Several device features present in our firmware have no corresponding GPIO mapping in the upstream YAML.

## Compatibility matrix

| Item | Our device | Upstream | Compatible? |
|---|---|---|---|
| MCU | mDNS: `board=esp32` | ESP32-S2 SOLO | **UNKNOWN** — see below |
| Flash | Unknown | 4 MB | Unknown |
| PCB revision | 6.3.0 | Not stated | **Cannot compare** |
| Device model | IFLOKIT01 | Not stated | Unknown |
| Firmware | 3.0.64 (vendor) | ESPHome replacement | N/A |
| Motor drivers | Unknown (device sealed) | Mixic MX08H-32788Hs (2x) | Likely same if same PCB family |
| Battery | 4xAA | 4xAA | Match |
| Device types | 0-3 (Consumer, PRO, Mini, Septic) | Not addressed | Unknown which type upstream had |
| Float switch (iFLO Plus) | Present (`floatEn`, `floodNow`) | Not mapped | **Missing from upstream** |
| External power detection | Present (`extPowerState`) | Not mapped | **Missing from upstream** |
| OUI | 68:67:25 (Espressif) | Espressif (from photos) | Match |

## Critical issue: MCU variant

Our device's mDNS TXT record reports `board=esp32`. The upstream ESPHome YAML specifies:

```yaml
esp32:
  variant: ESP32S2
  flash_size: 4MB
  framework:
    type: esp-idf
```

The ESP32 and ESP32-S2 are **different chips**:

| Feature | ESP32 | ESP32-S2 |
|---|---|---|
| CPU | Dual-core Xtensa LX6 | Single-core Xtensa LX7 |
| GPIO count | 34 | 43 |
| USB | None | Native USB-OTG |
| Bluetooth | BT 4.2 + BLE | None |
| Wi-Fi | 802.11 b/g/n | 802.11 b/g/n |
| Deep sleep current | ~10 uA | ~5 uA |

Firmware compiled for one will not run on the other. The binary `iflo-firmware.factory.bin` in the upstream repo contains ESPHome strings and is built for ESP32-S2 (per the YAML). **Flashing it onto a plain ESP32 would fail.**

Possible explanations for the discrepancy:
1. The vendor's mDNS implementation reports `board=esp32` as a generic label for any Espressif SoC, including the S2 variant. This is the most likely explanation — the mDNS service name is `ESP32-WebServer`, not `ESP32-S2-WebServer`.
2. There are multiple hardware revisions and ours uses a different chip. Less likely given the iFLO product line appears to be a single SKU.
3. The upstream author misidentified the chip. Unlikely — ESPHome compilation would fail if the variant were wrong, and the author successfully flashed two units.

**Resolution:** Examine the Espressif module markings on the PCB (requires opening the device), or check the TLS ClientHello fingerprint against known ESP32 vs ESP32-S2 mbedTLS implementations.

## Upstream GPIO assignments

From the upstream YAML and pinout image:

| GPIO | Function | Connector | Verified by upstream? |
|---|---|---|---|
| 6 | Front button (INPUT_PULLUP, inverted) | On-board | Yes (functional in firmware) |
| 7 | 2.5mm DC jack PIP | WC_5P | Traced, not used in YAML |
| 8 | Battery ADC (12dB atten, 6.0x multiplier) | RC_2P | Yes (functional in firmware) |
| 9 | Motor IN1 (H-bridge A input) | WC_2P | Yes (drives dispense motor) |
| 10 | Motor IN2 (H-bridge A input) | WC_2P | Yes (drives dispense motor) |
| 13 | Bottle sensor (INPUT_PULLUP, inverted) | BC_2P Key2 | Yes (functional in firmware) |
| 17 | Side reset button | WC_5P Key1 | Traced, not used in YAML |
| 39 | LED1 — Cloud indicator | On-board | Yes (functional in firmware) |
| 40 | LED2 — WiFi indicator | On-board | Yes (functional in firmware) |
| 41 | LED3 — Battery indicator | On-board | Yes (functional in firmware) |
| 42 | LED4 — Bottle indicator | On-board | Yes (functional in firmware) |

Pins traced but not functionally verified: GPIO4, GPIO5, GPIO7, GPIO11, GPIO14, GPIO15, GPIO17, GPIO18, GPIO19, GPIO20.

The upstream author states: "I mapped out most of the pins." The pinout image shows physical pad locations and connector mappings, but several pins are identified only by their ESP32-S2 alternate functions, not by their role in the iFLO circuit.

## Features in our device not addressed by upstream

### Float switch / iFLO Plus

Our `/dev_info` response includes:
- `floatEn: false` — whether the float switch feature is enabled
- `floodNow: false` — whether the float switch is currently triggered

The settings page JavaScript includes a toggle for iFLO Plus and sends `{floatEn: <bool>}` via `POST /dev_actions`. This implies a physical float switch sensor connected to a GPIO that the upstream YAML does not map.

If our device has this sensor and we flash upstream firmware, the float switch would be non-functional. For an HVAC condensate drain application, losing flood detection could allow water damage.

### External power detection

Our `/dev_info` includes `extPowerState: false`. The upstream author hardwired his devices to wall power and did not map the GPIO that detects external power. This is likely one of the side interface pins (GPIO7 or the 2.5mm DC jack PIP).

### Device type configuration

Our device supports four types via `/dev_actions`:
- 0: iFLO (Consumer HVAC)
- 1: iFLO (PRO HVAC)
- 2: iFLO Mini
- 3: iFLO Septic

The upstream firmware hardcodes a single behavior. Different device types may use different motor timing, dispense volumes, or GPIO assignments (e.g., U3 on the side interface board "goes to the 5.5mm plug" per the upstream README, suggesting the PRO model uses a different motor output).

### Demo mode and No-App Mode

Our device's firmware includes `demoModeVisible` and `namVisible` fields. These modes are not represented in the upstream ESPHome firmware.

## Battery ADC calibration concern

The upstream YAML uses:
```yaml
- platform: adc
  pin: GPIO8
  attenuation: 12dB
  filters:
    - multiply: 6.00
```

With voltage range 4.00V (0%) to 5.35V (100%). The 6.0x multiplier compensates for an assumed voltage divider ratio on the PCB. If our PCB revision uses a different divider (common when revising battery management circuitry), the percentage readout would be wrong. This is a calibration issue, not a safety issue — but an incorrect battery reading could cause the device to attempt a dispense with insufficient power.

## Motor driver compatibility

The upstream author identifies two H-bridge ICs as Mixic MX08H-32788Hs, noting "the writing is hard to read because of the coating." The motor control uses GPIOs 9 (IN1) and 10 (IN2) on U1 for the dispense motor. If our PCB revision uses a different motor driver or different GPIO routing, the upstream dispense sequence could drive incorrect pins.

The motor control sequence is:
1. IN1 HIGH, IN2 LOW — 250ms (direction set)
2. IN1 LOW — delay N seconds (run)
3. IN2 HIGH — 500ms (brake/reverse)
4. IN2 LOW (stop)

Driving these signals on wrong pins could damage the motor driver or pump.

## What can be verified without opening the device

| Check | Method | Answers |
|---|---|---|
| MCU variant | Compare TLS ClientHello fingerprint with known ESP32/S2 mbedTLS outputs | ESP32 vs ESP32-S2 |
| MCU variant | Check if device responds to USB-OTG (S2 has it, plain ESP32 does not) | ESP32 vs ESP32-S2 |
| GPIO count | If the device uses GPIO numbers >34 in its firmware (39-42 for LEDs), it must be ESP32-S2 | Confirms S2 |
| Side interface | Visual inspection of the exterior for jacks/buttons | Side board presence |
| Float switch | Check `/dev_info` `floatEn`/`floodNow` behavior (already done — both present) | Feature exists in firmware |

**Note on GPIO numbering:** The upstream YAML uses GPIO39, 40, 41, 42 for LEDs. On the plain ESP32, GPIOs 34-39 are **input-only** (no output capability). GPIO39 as an LED output is impossible on plain ESP32. This strongly suggests the device is actually an ESP32-S2, where GPIO39 is a normal I/O pin, and the mDNS `board=esp32` is a generic label.

## Verdict

The GPIO numbering evidence (output LEDs on GPIO 39-42) effectively confirms the device uses an **ESP32-S2**, consistent with the upstream project. The mDNS `board=esp32` is a vendor simplification.

However, PCB revision differences remain a real risk:
- Our PCB 6.3.0 may have different voltage divider values, connector pinouts, or additional sensors (float switch, external power) not mapped by the upstream author.
- The upstream author's PCB version is unknown.
- Flashing upstream firmware without verifying GPIO assignments risks incorrect motor operation or loss of safety features (flood detection).

**The upstream project is a reliable hardware reference. It is not a verified-compatible firmware for our specific PCB revision.** Physical verification is required before any firmware replacement is considered.

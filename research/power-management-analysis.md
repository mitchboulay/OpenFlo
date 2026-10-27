# Power management analysis

Battery life is a primary design constraint. The iFLO runs on 4xAA batteries and the vendor claims 12+ months of operation. Any architecture that significantly reduces battery life is a non-starter for battery-powered deployment.

> **Firmware-derived sleep/wake control (2026-10-26):** the exact wake sources,
> timers, defaults and remote config keys are reconstructed in
> [`sleep-wake-control.md`](sleep-wake-control.md). The device has no
> network-wake path; only timer/GPIO/power events can wake it.

## Hardware

| Parameter | Value | Source |
|---|---|---|
| MCU | ESP32-S2 SOLO | Upstream pinout (demitryk1/SmartHome) |
| Battery | 4xAA (nominal 6V, ~2500 mAh alkaline) | Physical observation |
| Battery ADC | GPIO8, 12dB attenuation, 6x voltage divider | Upstream YAML |
| Battery range | 4.00V = 0%, 5.35V = 100% | Upstream YAML lambda |
| Motor driver | Mixic MX08H H-bridge (x2) | Upstream README |

## ESP32-S2 power modes (Espressif datasheet)

| Mode | Typical current | What's running |
|---|---|---|
| Active (WiFi TX) | ~310 mA | CPU + radio transmitting |
| Active (WiFi RX) | ~100 mA | CPU + radio listening |
| Modem sleep | ~12 mA | CPU active, radio off |
| Light sleep | ~130 uA | CPU paused, RAM retained, fast wake |
| Deep sleep (RTC timer) | ~22 uA | RTC timer + RTC memory only |
| Deep sleep (GPIO wake) | ~22 uA | GPIO monitoring + RTC memory |
| Hibernate | ~2.5 uA | RTC timer only, no GPIO wake, no RAM |

## Original firmware behavior (observed)

From the Mission 003 gateway capture:

- WiFi is completely off between wake windows (no ARP, no DHCP renew, neighbor entry expired)
- Wake burst 1: 14:57:29 to 14:58:21 (~52 seconds)
- Wake burst 2: 15:01:42 to 15:04:45 (~183 seconds)
- Gap between bursts: ~201 seconds
- After 15:04:45: total radio silence for 27+ minutes (and counting at mission end)
- The device initiates all connections; nothing reaches inbound

This is textbook ESP32 deep-sleep battery optimization: wake, connect WiFi, poll cloud, execute any pending work, disconnect, return to deep sleep. The RTC timer handles scheduled wake-ups; GPIO likely handles the front button.

## Upstream ESPHome firmware behavior

From the ESPHome YAML:

```yaml
wifi:
  power_save_mode: HIGH
  fast_connect: true
```

`power_save_mode: HIGH` enables WiFi modem sleep (DTIM-based power saving within an active WiFi association). The radio is NOT turned off between uses; it periodically wakes to check for beacons. This is NOT deep sleep.

The YAML contains no `deep_sleep:` component. The device stays in modem-sleep mode continuously, drawing ~12 mA average (optimistic) with periodic spikes to 100-310 mA for network activity.

The upstream author reports: "batteries only last 2 days. I don't have any sort of sleep built in. I hard wired mine to be plugged in."

## Rough energy budget (datasheet-derived, not measured)

These are order-of-magnitude estimates from datasheet typical values. Actual current draw depends on firmware behavior, peripherals, regulator efficiency, and battery chemistry. They are useful for comparing architectures, not for predicting exact battery life.

### Original firmware (deep sleep between wakes)

Assumptions: 30-second wake every 4 hours (6 wakes/day), each wake averages 200 mA (mix of TX/RX/CPU).

| State | Duration/day | Current | Charge/day |
|---|---|---|---|
| Deep sleep | 23.95 h | 22 uA | 0.53 mAh |
| Wake (WiFi active) | 0.05 h (3 min) | 200 mA | 10 mAh |
| **Total** | | | **~10.5 mAh/day** |

Estimated battery life: 2500 / 10.5 = **~238 days**

This is consistent with the vendor's 12+ month claim (alkaline capacity varies; lithium AAs would exceed this).

### ESPHome with modem sleep only (upstream YAML)

Assumptions: continuous modem sleep at ~12 mA average with periodic spikes.

| State | Duration/day | Current | Charge/day |
|---|---|---|---|
| Modem sleep + activity | 24 h | ~15 mA (avg) | 360 mAh |
| **Total** | | | **~360 mAh/day** |

Estimated battery life: 2500 / 360 = **~6.9 days**

The upstream author's "2 days" suggests actual average draw is higher than the modem-sleep datasheet value, likely due to the web server, ESPHome API, SNTP polling, and sensor updates keeping the CPU more active than pure modem sleep.

### ESPHome with deep sleep (hypothetical)

If deep sleep were added to the ESPHome firmware with similar wake patterns to the original:

| State | Duration/day | Current | Charge/day |
|---|---|---|---|
| Deep sleep | 23.95 h | 22 uA | 0.53 mAh |
| Wake (WiFi active) | 0.05 h | 200 mA | 10 mAh |
| **Total** | | | **~10.5 mAh/day** |

Theoretically similar to the original firmware. But deep sleep in ESPHome has constraints:

1. **No persistent WiFi.** On each wake, ESPHome must reconnect to WiFi, re-register with Home Assistant, update sensors, and disconnect. This increases wake duration.
2. **No web server during sleep.** The local web UI and ESPHome native API are unavailable between wakes.
3. **State persistence.** ESPHome globals with `restore_value: true` use NVS flash, which survives deep sleep. Schedule timers and dispense counts would persist.
4. **Scheduled dispensing.** The RTC timer can wake the device at dispense time. The motor can run without WiFi. This is feasible.
5. **Button wake.** GPIO6 (front button) can be configured as a deep-sleep wake source on the ESP32-S2.
6. **WiFi reconnect overhead.** Fast connect helps, but DHCP + TLS + API registration still takes 2-10 seconds per wake, longer than the original firmware's optimized reconnect.

## Architecture comparison

### Option A: Original firmware + local HTTP controller

**Battery impact: NONE.**

The original firmware manages its own sleep cycle. A local controller on the gateway container can only read `/dev_info` during existing wake windows. The device's power behavior is entirely unchanged.

The controller must detect wake windows passively (via DHCP/ARP/mDNS monitoring) and issue its HTTP requests within the existing window. It cannot extend or trigger additional wakes.

### Option B: Original firmware + cloud redirect

**Battery impact: NEGLIGIBLE to SLIGHTLY NEGATIVE.**

The original firmware's sleep/wake cycle is unchanged. The device wakes on its normal schedule and polls whatever server `SERVER_CREDENTIALS.host` points to.

Potential impacts:

| Factor | Direction | Magnitude |
|---|---|---|
| Local server responds faster than remote cloud | Slightly positive | Seconds per wake |
| Local server responds slower or times out | Negative | Could extend wake window or trigger retries |
| Device retries on TLS handshake failure | Negative | Could drain battery on repeated failed wakes |
| Device enters error-retry loop on persistent failure | Significantly negative | Could prevent deep sleep entirely |

The retry behavior on connection failure is unknown and is the key risk. If the device retries aggressively when it cannot reach its configured backend, battery life could degrade substantially. This can be observed safely: block `backend.iflo.com` at the gateway DNS and measure whether the device's wake pattern changes.

### Option C: Replacement firmware (ESPHome)

**Battery impact: SEVERE without deep sleep. UNCERTAIN with deep sleep.**

Without deep sleep (the upstream YAML as-is): battery life drops from months to days. The upstream author hard-wired to wall power. This is a fundamental limitation, not a configuration oversight.

With deep sleep implemented: theoretically recoverable to original-firmware levels, but with engineering challenges:

| Challenge | Difficulty | Notes |
|---|---|---|
| Basic deep sleep with RTC wake | Low | ESPHome `deep_sleep` component supports ESP32-S2 |
| GPIO wake for front button | Low | ESP32-S2 supports RTC GPIO wake |
| State persistence across sleep | Low | ESPHome `restore_value: true` uses NVS |
| Scheduled dispense from RTC timer | Medium | Must calculate next dispense time, set RTC alarm, motor runs without WiFi |
| WiFi reconnect speed | Medium | `fast_connect: true` helps but DHCP/API registration adds seconds |
| Home Assistant availability | High | HA integration only works during wake windows; push model breaks |
| Web server availability | High | Local web UI unavailable during sleep; incompatible with always-on dashboard |
| OTA updates during sleep | Medium | Must stay awake long enough for OTA; can't update a sleeping device |

## What requires physical measurement

The following cannot be determined from software analysis alone:

1. **Actual current draw in each power state.** Datasheet values are typical, not guaranteed. Peripherals (H-bridge quiescent current, voltage divider, LEDs, bottle sensor pull-up) contribute to baseline draw and are PCB-specific.
2. **Regulator efficiency.** The 6V battery pack feeds through an on-board regulator. Its efficiency at different load levels affects all estimates.
3. **Wake duration under the original firmware.** We observed two bursts during setup, which is not representative of steady-state behavior. The idle wake interval and duration need the 24h+ baseline capture.
4. **Motor current draw.** The dispensing motor's current and duration determine the energy cost per dispense, which matters for devices on aggressive schedules.
5. **Deep-sleep baseline current.** The actual deep-sleep current with all peripherals connected may exceed the MCU-only 22 uA figure if the H-bridge driver or other components have quiescent draw.

## Conclusion

Battery life is the strongest argument for preserving the original firmware. The vendor has solved the hardest embedded power management problem — reliable deep sleep with scheduled wake, motor control, and cloud polling — and achieved 12+ months on AAs. Replicating this in ESPHome is possible but non-trivial, and the upstream implementation does not attempt it.

Options A and B preserve the original firmware's power management entirely. Option C requires significant additional engineering to reach acceptable battery life, and even then would likely fall short of the original due to ESPHome's WiFi reconnect overhead and the loss of vendor-optimized sleep transitions.

If wall power is available (the upstream author's solution), Option C's battery penalty disappears. But this changes the product from a battery-powered install-anywhere device to a wired appliance, which is a meaningful capability regression.

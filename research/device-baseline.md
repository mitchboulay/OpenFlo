# Device baseline — iFLO 3.0.64 (reconciled, Mission 008A)

Updated 2026-10-26 19:30 UTC. Passive sources only: gateway pcap
(`captures/20261026T144415Z_first-provision`), dnsmasq log, and the controller's
`/dev_info` readings until 19:16:52. No requests were sent to the device by
Mission 008A.

## 1. Identity

| Field | Value | Class |
|---|---|---|
| MAC / IP | `68:67:25:00:00:01` / `192.168.30.80` (dynamic lease, unchanged since provisioning) | CONFIRMED |
| Device ID | `D8256700000A0001` | CONFIRMED |
| Firmware / PCB | `3.0.64` / `6.3.0` | CONFIRMED |
| Type / mode | 0 (Consumer HVAC) / `Normal`, not Pro, battery-only (`extPowerState=false`) | CONFIRMED |
| Cartridge | 5 doses, bottle `OK`, flood false, float disabled | CONFIRMED (19:16:28) |

## 2. Battery

| | Value | Timestamp (UTC) | Source |
|---|---|---|---|
| **Latest** | **94 %** | **2026-10-26 19:16:28** | Controller `GET /dev_info`, last reading of wake event 1 (3,132 readings) |
| First controller reading | 100 % | 17:28:27 | Controller reading #1 |
| Earliest | 100 % | ~15:30 | Mission 003 manual `GET /dev_info` |

The Mission 008 approval request said "100 % at last observation", which was
stale (it predated the controller's readings). The baseline report's 96 % was
correct when written (18:55). The 6-point fall happened during the
controller-held wake (§4). No lifetime is extrapolated. Percentages from a few
hours of a fresh 4×AA pack say nothing reliable about lifetime.

The next battery value will come from the device's own `update-device` payload
(`batteryLevel`), not from polling, so measuring it does not keep the device awake.

## 3. Wake / sleep timeline

| # | Start | End | Duration | Trigger | Source |
|---|---|---|---|---|---|
| 1 | 14:56:35 | 14:58:22 | 107 s | Provisioning | pcap |
| 2 | 15:01:39 | 15:04:48 | 189 s | Cartridge activation (app) | pcap |
| 3 | 15:33:44 | 15:36:40 | 175 s | Unknown (timer or app) | pcap |
| 4 | 16:03:37 | ~16:04:10 | ~33 s | Unknown | dnsmasq only |
| 5 | 16:07:25 | ~16:08:21 | ~56 s | Unknown | dnsmasq only |
| 6 | 17:28:23 | 19:17:37 | **6,554 s** | Natural wake, then **held awake by the controller** | pcap + dnsmasq + controller |
| — | 19:17:37 | (asleep at 19:30) | — | — | pcap: zero device frames |

Wakes 4–5 fall in a **capture coverage gap, 15:53:40–16:44:16**. File
`openflo_20261026T154415Z.pcap` ends early and the next rotation starts at 16:44.
The cause was not investigated and the capture was not touched. The dnsmasq log
(DHCP + DNS) covers that window.

### Natural behavior (wakes 1–5 and the start of 6)

| Metric | Value | Class |
|---|---|---|
| Natural wake duration | 33–189 s (n = 5) | CONFIRMED |
| Gaps between natural wakes | 3.3, 28.9, ~27, ~3.3, ~80 min | CONFIRMED |
| Steady-state idle interval | **UNKNOWN**: the device was provisioned today; gaps vary 3–80 min and triggers are unknown | UNKNOWN |
| Wi-Fi while asleep | off: no frames of any kind | CONFIRMED |
| Connections | device-initiated only | CONFIRMED |
| DNS | A records only (36 queries, 0 AAAA) | CONFIRMED |
| Cloud sync cadence *while awake* | ~10 min (12 syncs during wake 6) | CONFIRMED (during held wake) |

**Baseline status: INSUFFICIENT for a statistical idle interval.** It is
sufficient for wake duration and for the device's network behavior.

## 4. Observer effect: controller polling held the device awake

The Mission 006 controller polls `GET /dev_info` every 2 s for as long as the
device answers. It started at 17:28:27, two seconds into wake 6, and the device
never slept again.

Intervention (19:16:52): the controller was stopped and disabled. Nothing was
sent to the device. Result: the device ran one more vendor sync at 19:17:36 and
then went silent. Zero frames from 19:17:37 onward.

**Conclusion (CONFIRMED by one controlled intervention):** local HTTP requests
keep the device awake. The 87+-minute "extended wake" in the Mission 008
baseline was caused by our instrumentation, not by post-provisioning settling or
a cloud directive.

Consequences:

1. The controller stays **stopped and disabled** until it reads once per wake
   instead of polling continuously. Phase 6 does not need it: `update-device`
   telemetry carries battery, signal and firmware.
2. Wake duration is now a clean signal again: ≤ 189 s is normal.
3. Useful for recovery: an operator can hold a wake open on purpose by polling
   `/dev_info`, which widens the rollback window (see `backend-recovery-readiness.md`).

## 5. Stop thresholds for Phase 6 (consistent set)

No statistical idle baseline exists, so these are conservative absolute limits.
They assume nothing polls the device during observation; operator rollback
actions are exempt.

| Condition | Threshold | Action |
|---|---|---|
| Continuous wake | Any wake > **10 min** (natural max 189 s; the only longer wake was operator-induced) | Rollback during that wake |
| Connection failure | **2 consecutive wakes** without a 200 `update-device` at OpenFLO (from the `lab_device_tls` counter, Caddy access log and backend protocol log) | Rollback at the next wake |
| Unexpected retry | > **5 TLS handshakes** or > **10 device-API requests** in one wake (expected: `update-device` → 422 → `register` → `update-device`, plus optional `get-fw` / `healthcheck` / `send-events`) | Rollback during that wake |
| Battery | Reported `batteryLevel` < **90 %**, or a fall of ≥ **3 points** within the observation period | Rollback at next wake |
| Motor activity | `doses` decreases, a dispense event appears in `send-events`, or audible motor | **Immediate** rollback; stop the mission |
| Firmware | `firmwareVersion` ≠ `3.0.64` | Immediate stop; do not roll back blindly (reassess) |
| Device mode | `deviceMode` ≠ `Normal`, `noAppMode` / `namVisible` changes, `isProVersion` changes | Rollback |
| No wake | No wake within **4 h** of the change | Nothing is harmed while it sleeps; keep the passive watch and roll back at the next wake if the experiment window has closed |

Observation period: up to 4 h or 3 natural wakes after the host change,
whichever comes first.

## 6. Recommendation

Before Phase 6, run the device for **24 h passively** (controller off, capture
on) to get ≥ 3 natural wakes and a first steady-state idle interval. This is not
a safety blocker (the thresholds above are absolute), but without it a "no wake
for hours" outcome in Phase 6 can't be told apart from normal sleep.

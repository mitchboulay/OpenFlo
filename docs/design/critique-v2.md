# Design critique: OpenFLO v2 prototype

Date: 2026-10-26. Source: the v2 prototype (not published). Brief: [`docs/design-brief.md`](../design-brief.md).

## Simplicity score: 4 / 5

Good, with a short list of changes. The calm voice, the honest "Waiting for device · ~4:42 PM" pattern and the volume-first dose are exactly right. The Dosing card carries too many controls, and a few settings are disguised as inline toggles.

## One-sentence test

"See that each drain line is being treated, and change how much and when it doses." **Pass.** The device header says this in one line: *"Everything's fine. Next dose Sun, Nov 1 9:00 AM ET."*

## What is already right (keep)

- **The headline replaces a dashboard.** One sentence, chosen by priority: offline, then bottle low, then level unknown, then battery low, then next dose.
- **Pending changes are named** ("Dose change 150 mL → 177 mL · Waiting for device · ~4:42 PM ET"), with the twist-the-bottle hint underneath. This is the honest async model done well.
- **Dose:** a big mL number with a stepper, three presets with the default tagged, and a limit message phrased as capability ("This liquid can dose 28–830 mL").
- **The bottle gauge has dose ticks,** so "≈ 3 doses" is visible, not just stated.
- **The Dispense confirm says when it will happen** ("…when it next checks in, around 4:42 PM").
- **Check-in options show battery bars** and the trade-off in plain words.
- **The wizard** offers "Reset at next check-in" and "I'll hold the reset button", and handles timeout and busy states.

## Issues

| # | What's wrong | Why it matters | Fix |
|---|---|---|---|
| 1 | **The Dosing card has about 9 controls:** dispensing switch, liquid picker, unit toggle, stepper, presets, new bottle, set level, dispense now, calibrate, plus the fixed-time and adjust-for-level options | Configuration count well over 3. The most important number competes with everything else. | Dosing = **Liquid · Dose · Bottle** only. The others move as described in #2–#5. |
| 2 | The **Dispensing on/off** switch sits in the Dosing card header | It's the device's safety lock, not a dosing setting. Inside Dosing, turning it off reads like "stop this dose". | Move it to the device header as a state: "Dispensing · On", with "Pause dispensing" in the device menu. When off, the headline says "Dispensing is paused." |
| 3 | **Dispense now** is buried mid-card | It's the device's one direct action. | Make it the header's primary button ("Dispense now…"); the queued, sent and dispensed tracker also shows there. |
| 4 | **Calibrate** is a separate row under Dosing | Calibration belongs to the *liquid* ("Vinegar · not calibrated"), not to the dose. | Show it on the liquid: "Vinegar · Not calibrated yet · **Calibrate**". Once calibrated, show "Measured 27.8 mL/s · Recalibrate" in the liquid's detail sheet. |
| 5 | The **mL / oz segmented toggle** lives inside the dose display | It's a preference disguised as a control, and it multiplies states. | Make it one app-wide setting (Settings → Units, defaulting from locale). Remove it from the card. |
| 6 | **"Testing (every 15 minutes)"** is shown to every user as a peer of the real options | It's an engineering mode. A homeowner choosing it drains the batteries. | Show three options. "Testing" appears only under Device → Advanced, with its warning. |
| 7 | **Seven section tabs** (Dosing, Schedule, Check-in, Battery, Wi-Fi, Info, History) | They crowd a 360 px screen, and five of them describe the device rather than its job. | Three anchors: **Dosing · Schedule · Device**. Device holds Check-in, Battery, Wi-Fi, Info and History, as collapsible groups on phone. |
| 8 | **"Valve opens about 6.4 s"** is always shown under the dose | Engineer detail in the primary display. | Show seconds only in the Advanced sheet and in the calibration result. The subline becomes "≈ 6.0 oz · about 3 weeks of liquid at your schedule". |
| 9 | Presets are labeled with raw volumes ("118 mL · 177 mL · 236 mL") | Fine for experts; meaningless for most. | Keep the volumes, add human anchors from the liquid's profile: "Light · Standard · Strong". Standard is the liquid's default. |
| 10 | The **"Prototype: twist the bottle"** demo button is in the status header | Prototype scaffolding. | NEVER ship it. The real status refreshes by polling. |
| 11 | **Missing screens** (the brief was extended after v2): first-run setup with server address and address check, sign-in, Settings (units, server address, tokens), device identity warning, retire flow, no-login banner | F2.1 and the device page can't be built faithfully without them. | Generate **v3** from the updated brief, including only these screens. They MUST reuse v2's atoms and molecules: the CheckList is the StepList with ok/warn/fail tones; Settings rows reuse the Check-in option row. |
| 12 | **No responsive breakpoints.** Layout relies on intrinsic flex-wrap (`flex: 1 1 440px` / `360px`) and an auto-fill grid. | It works, but sticky elements, sheet alignment and the 7-tab bar are untested at 360 px. | The build uses explicit Tailwind breakpoints (`sm` 640, `lg` 1024). Sheets are bottom sheets below `sm` and centered dialogs above. Verified at 360, 768 and 1280 px. |

## Hard questions

1. If Dosing showed only **liquid, dose and bottle**, would anyone miss the rest on that card, given that each moved item has an obvious new home?
2. Should **"Dispense now"** queue at all when the device is due to check in within a minute? Or should the button read "Dispense at next check-in (~4:42 PM)" to remove the word "now" entirely?
3. Does the **standard cartridge** need a liquid picker at all for users who never change liquids? Consider showing the picker only after "Change liquid…".
4. Is **"Check-in"** the word people will use? "How often it wakes" was tested in the brief; "Check-in" won, but it's still jargon to a first-time user. Confirm with the first outside user.
5. Should **schedules** default to one gentle rule ("Every Sunday at 9:00 AM") on first enable, rather than an empty editor?

## Atomic design mapping (for implementation)

| Level | Components (from v2) |
|---|---|
| **Atoms** | Button (primary / secondary / ghost / danger), IconButton, Switch, Radio, StatusDot, Badge (tone), Tick, Sparkline, ProgressBar, Input, TimeInput, DayToggle, QR, Toast |
| **Molecules** | Stepper (big number + − / +), PresetChips, LiquidChip, PendingRow, CheckinOption (radio + bars + line), BottleGauge (bar + dose ticks + line), StepDots, StepList/CheckList item, DispenseTracker (queued · sent · dispensed), ScheduleRuleRow, UpcomingRow, HistoryRow, InfoRow |
| **Organisms** | DeviceHeader (headline, check-in line, pending list, hint, primary action), DosingCard, ScheduleCard, CheckinCard, BatteryCard, WifiCard, InfoCard, HistoryCard, DeviceCard, HomeRow, UnclaimedBanner, Sheet (bottom / center), CalibrateSheet, LevelSheet, RuleSheet, WifiChangeSheet, ProvisionWizard steps |
| **Templates** | AppShell (top bar + back + content width), WizardShell (full-screen stepper), SheetShell |
| **Pages** | Homes, Home, Device, AddDevice, Setup (v3), SignIn (v3), Settings (v3) |

Rules:
- A component MUST live at exactly one level. Pages compose organisms only.
- NEVER create page-local UI.
- Tokens (color, radius, spacing, type) come from v2's CSS variables (`--accentFill`, `--border2`, `--surface`, tones, etc.) in `ui/src/styles/tokens.css`, with light and dark themes.

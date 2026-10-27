# OpenFLO — Design Brief

## What it is

OpenFLO is a self-hosted home app for iFLO dispensers. These are small, battery-powered devices that clip onto an air conditioner's condensate drain line and periodically release a cleaning liquid (the vendor's cartridge fluid, or vinegar) to keep the line from clogging. OpenFLO replaces the manufacturer's cloud and app. It runs on the homeowner's own server and is used from a phone or laptop browser on the home network.

The user is a homeowner (and later, a technician who looks after a few homes). They want to set things up once, trust that the drain lines are being treated, and only come back when something needs attention: the bottle is running low, the battery is getting weak, or they want to change how much is dispensed.

## The one thing that shapes everything

**The device is asleep almost all the time and cannot be woken from the app.** It wakes on its own timer (every few hours up to every 2 days, as the user chooses), checks in, picks up any changes, and goes back to sleep. Pressing the button on the device or twisting its bottle also wakes it.

So every change in the app is a request that the device picks up at its next check-in. The design must make this feel calm and honest, never broken:
- Show "Waiting for device · next check-in around 4:15 PM" on anything not yet delivered.
- Switch it to "Applied" once the device has picked it up.
- Never show a spinner that implies something is happening right now.
- Always tell people they can twist the bottle or press the device button to make it check in immediately.

## Design principles

- **Inevitable, not impressive.** It should feel obvious. One primary action per screen.
- **Calm.** Most of the time the right message is "Everything's fine. Next dose Sunday 9:00 AM."
- **Plain language.** Never use "sync interval", "fast-sync-time", "nonce", "SE code" or "provisioning session". Use "Checks in every 6 hours", "Dispense", "Add a device".
- **Volume first.** People think in milliliters or ounces, not valve-open seconds. Seconds exist only behind "Advanced".
- **Honest estimates.** Remaining liquid and battery life are estimates. Say so lightly ("about", "≈") and never fake precision.
- **Safe by default.** Anything that makes the device dispense on its own (schedules, dispense now) needs a clear, one-time explanation and a deliberate confirm.

Light and dark themes. Phone-first (from 360 px), and comfortable on a laptop. WCAG AA: status is never shown by color alone.

## Information architecture

```
Homes
 └─ Home (e.g. "Main house", "Lake cabin")
     ├─ Devices (cards)
     ├─ Unclaimed devices (if any)
     └─ Add device (setup wizard)
          Device
           ├─ Status header
           ├─ Dosing (liquid · dose · bottle level · dispense now · calibrate)
           ├─ Schedule
           ├─ Check-in (how often it wakes)
           ├─ Battery
           ├─ Wi-Fi
           ├─ Device info
           └─ History
```

## Screens

### 1. Homes
A list of homes. Each row shows the home name, the number of devices, and a single summary status ("All good", "1 needs attention: bottle low"). Includes an "Add home" action, and an edit option for name and time zone.

### 2. Home → Devices
Device cards, each showing:
- name ("Attic unit") and location ("Air handler, attic");
- a status label with a dot (OK / Needs attention / Offline);
- battery %;
- bottle level ("About 3 doses left");
- the next dose, or the next check-in time;
- a small "Waiting for device" badge if changes are pending.

There's a prominent **Add device** button. "Unclaimed device" cards appear when a device has connected but isn't assigned yet ("New iFLO found. Add it to this home?").

### 3. Device: Status header
Name, location, status, "Last check-in 10:42 AM · next around 4:42 PM", and a short list of pending changes ("Dose change: waiting for device"). A hint explains: "To apply now, twist the bottle or press the device's button."

### 4. Device: Dosing (the most important card; design it the way Apple would)
- **Liquid:** Standard cartridge · Vinegar · the user's own liquids · "New liquid…". Vinegar shows "Not calibrated yet" until calibrated.
- **Dose:** one large, friendly number in mL (with an oz toggle) and a −/+ stepper. Beneath it, small text: "Valve opens about 6.4 s". Show sensible presets for the liquid (the standard cartridge's default is 177 mL ≈ 6 oz).
- **Bottle level:** a simple gauge, "About 540 mL left · ≈ 3 doses · ≈ 3 weeks at your schedule". States: OK / Refill soon / Refill now / "Set the level" (when unknown). Actions: "I put in a new bottle" (full) and "Set level".
- **Dispense now:** a button with a deliberate two-step confirm. States: Queued for next check-in → Sent → Dispensed (confirmed by the device). It can be cancelled while queued.
- **Calibrate** (a sheet with 3 steps): "1. Put a measuring cup under the outlet. 2. Dispense one dose. 3. Enter how much came out." After that, the app knows the real flow for this liquid.
- **Advanced** (collapsed): "Use a fixed time instead of volume", and "Adjust for bottle level" (on by default; explained as "flow slows as the bottle empties, so the app adds a little time").
- If the requested dose is impossible (too small or too large for 1–30 s of flow), the stepper stops at the limit and explains the range ("This liquid can dose 28–830 mL").

### 5. Device: Schedule
- A **Schedules** switch. Turning it on the first time shows a one-time sheet: "Your iFLO will dispense on its own at these times."
- Rules in plain language: "Every Sunday at 9:00 AM", "Every day at 7:30 PM · double dose", "Every 2 weeks", "Once on Nov 3 at 8:00 AM".
- Add/edit sheet with the options Daily / Weekly (pick days) / Every N hours or days / Once, plus a time and an optional "Double dose".
- **Upcoming:** the next 10 doses, each labeled "Waiting for device" / "On device" / "Dispensed" / "Missed".
- When dispensing is turned off, a banner reads: "Schedules are paused while dispensing is off."

### 6. Device: Check-in
Four choices, each with a one-line consequence and a relative battery-cost indicator (for example 1 to 4 bars):

| Choice | Line |
|---|---|
| Battery saver | Checks in daily. Changes can take up to a day. |
| Balanced (recommended) | Every 6 hours. |
| Responsive | Hourly. Uses more battery. |
| Testing | Every 15 minutes. Drains the battery. Use briefly. |

### 7. Device: Battery
The current %, a 30-day sparkline, and "≈ 4 months until it needs new batteries at this check-in rate". Shows "Not enough data yet" until there are a few days of data.

### 8. Device: Wi-Fi
Network name, signal strength, and IP. One plain sentence: "Wi-Fi can only be changed at the device." **Change Wi-Fi…** opens the Add-device wizard for this device (set it up again on the new network). There is no button-press guide: the device's long presses can dispense or factory-reset it.

### 9. Device: Device info
Model (iFLO, Valve type), serial number, firmware, board version, MAC address, install date (editable), first and last seen. Fields not yet known show "—".

### 10. Device: History
Tabs for Dispenses (time, kind such as scheduled / button / remote, and ≈ mL), Events (plain-language names such as "Bottle removed", "New bottle", "Woke from button", "Battery low", "Dispense failed"), and Check-ins.

### 11. Add device (setup wizard)
A step-by-step flow that feels like pairing AirPods: one clear instruction per screen, with large visuals.
1. **Name it.** Name and location.
2. **Reset it** (only when moving an existing device): "We'll reset it the next time it wakes (around 4:42 PM). To do it now, twist the bottle." Or "I'll hold the reset button."
3. **Use your phone.** Two QR codes in sequence: (a) join the device's Wi-Fi hotspot "iFLO device"; (b) open the setup page, where you choose your home's iFLO network and enter its password. Mention clearly that a phone works best.
4. **Connecting…** Live steps with checkmarks: Joined your network → Securely connected → Registered → First check-in.
5. **Done.** "Attic unit is ready." Then go to the device.

Also design the states for an expired session ("This setup timed out. Start again."), for cancelling, and for "A setup is already in progress in this home."

### 12. First-run setup (like Jellyfin)
The first time someone opens OpenFLO, there are no screens yet, only a short setup:
1. **Create your account:** username and password. If the server is set up for single sign-on (for example Authentik), this step instead says "Sign-in is handled by Authentik" and shows a "Test sign-in" button.
2. **Server address:** "This is the address your iFLO devices will use to reach OpenFLO, from anywhere." One field, e.g. `https://openflo.example.com`, with the explanation that a device keeps this address until it's set up again.
3. **Check address:** a checklist that runs automatically. Each line is OK, warning or problem, in plain language with how to fix it:
   - "Found your server": DNS works.
   - "Devices can connect securely": TLS works without SNI.
   - "Certificate is one iFLO trusts": chain and RSA key.
   - "This server answered": reached this OpenFLO instance.
   - Cloudflare warning: "This address goes through Cloudflare. Your devices can't connect through it. Point this name straight at your server (DNS only, grey cloud)."
   - Non-standard port note.

   The user can continue with warnings. Adding a device stays blocked until the device-critical checks pass, with a link back here.
4. **Done.** "OpenFLO is ready. Add your first home."

### 13. Sign-in
A simple username and password form, or a "Sign in with Authentik" button (whichever the server uses). Wrong password and "too many attempts, wait a minute" states are needed.

### 14. Settings
- **Server address:** current address, "Check again", last check result (the same checklist).
- **Sign-in:** which method is in use (read-only, with a link to docs).
- **API tokens:** for scripts and future apps. Create (name it; the token is shown once with a copy button and the warning "You won't see this again"), list (name, created, last used), revoke.
- **About:** version, server ID.

### 15. Warnings and edge states
- **No sign-in configured:** a persistent, calm banner at the top: "No login is set. Anyone who can reach this page can control your devices." It links to how to turn sign-in on.
- **Device identity warning** (on the device page, and its card in the list): "We saw this device check in from two places at once." Shows both locations/IPs and when. Explain that remote dispensing and schedules are paused until you confirm, with buttons "It's fine (I moved it)" and "Keep paused". Tone: careful, not alarming.
- **Reset when the server can't reach the device** (devices at another location): the wizard's reset step becomes "Hold the reset button on the device for a few seconds until its light changes, then tap 'I've reset it'."
- **Retiring a device:** "Waiting for the device to clear its schedule" while pending, then "Retired". If the device never checks in, offer "Retire anyway" with the warning that it may keep dispensing on its own until its bottle is removed.

## Shared components

Status dot plus label, Pending badge ("Waiting for device · ~4:42 PM"), Switch, Stepper (large number), Bottle gauge, two-step Confirm button, bottom Sheet (on phone; centered dialog on desktop), Segmented choice (check-in presets), Sparkline, QR card, and Step list (setup progress).

## Content and tone

Friendly, short, and confident. "Dose" not "dispense volume". "Check-in" not "sync". "Bottle" not "cartridge" (except "Standard cartridge" as the liquid name). Use times in the home's time zone with a short label ("9:00 AM ET").

## Visual reference (optional)

The current lab dashboard uses a dark palette: background `#0f1117`, surface `#1a1d27`, border `#2a2d3a`, text `#e4e4e7`, dim `#71717a`, accent `#3b82f6`, plus green/yellow/red for status. The designer can keep or replace it. Light mode is required too.

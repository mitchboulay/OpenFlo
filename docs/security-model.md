# Security model

OpenFLO has two very different sides:

- **The management side** (the web app and `/api/v1`) requires a login. See [auth.md](auth.md).
- **The device side** (`/device-api/*`) can't require a login, because iFLO firmware 3.0.64 has no way to prove who it is.

This page explains what that means and what OpenFLO does about it. [SECURITY.md](../SECURITY.md) has the short version and how to report a vulnerability.

## Device identity

- **A device identifies itself only by its device ID.** There is no password, client certificate or per-device secret.
- **Device IDs are not secret.** The ID is derived from the device's Wi-Fi MAC address, a byte rearrangement of it. MAC addresses come in vendor blocks, so IDs can be guessed.
- **So a device ID can't authenticate anything.** OpenFLO treats it as a public label, not proof.

## What is protected

- **Registering a device.** A device can only register with a one-time pairing token from the Add device wizard. The token is stored only as a hash and expires after 20 minutes. Without access to your OpenFLO login, nobody can add a device to your homes.
- **Your devices' commands.** Only you can queue a dispense, change a dose or set a schedule.
- **Dispensing defaults to off.** New and claimed devices start with dispensing off. Schedules need both dispensing and schedules turned on.
- **Secrets at rest.** Passwords are argon2 hashes. Pairing and API tokens are SHA-256 hashes. The session key file is readable only by the app.
- **The container.** It runs as an unprivileged user with no Linux capabilities and a read-only root filesystem.

## What someone could still do

Anyone who can reach your server and knows (or guesses) a registered device ID can pretend to be that device. They could:

- send false readings for it (battery, Wi-Fi, bottle events), which then show in your history;
- pick up a queued **Dispense now** before your real device checks in, so the real device never receives it;
- make its sync status look wrong.

They **cannot** make your real device dispense. OpenFLO only answers the device that asks; it never pushes commands to a device.

## Abuse controls

These are **mitigations, not authentication.** They limit the damage and make impersonation visible.

### Rate limits

- 300 device requests per 5 minutes from each IP address.
- 10 requests per minute from each IP address for device IDs OpenFLO doesn't know. This slows down ID guessing.

Over the limit, the device API answers "rate limited" until the bucket refills.

### Unclaimed cap

An unknown device ID that checks in becomes an **unclaimed device**. At most `OPENFLO_UNCLAIMED_CAP` (default 10) exist at once, so a flood of fake IDs can't fill your database. Unclaimed devices get no dispenses, schedules or bottle approval until you claim them.

### No payload logging for unknown devices

OpenFLO logs request bodies only for devices it knows. An attacker can't fill your logs with arbitrary data from made-up IDs.

### Identity flags

OpenFLO raises a **Device warning** when a device looks like it might be two devices:

- **"We saw this device check in from two places at once."** The same device ID checked in from a second IP address while a check-in from another address was open, or less than 10 minutes after it ended.
- **"This device reported different hardware details than before."** Its firmware version, device type or board version changed.

### Withholding

While a warning is open, OpenFLO **withholds remote dispenses and schedules** from that device. The warning shows the addresses involved. If you moved the device or changed its network, select **It's fine (I moved it)** to resume.

## What the controls don't prevent

- **Impersonation from one address.** Someone who knows a device ID and checks in only when the real device doesn't can go unnoticed.
- **False telemetry** within the rate limits.
- **A stolen Dispense now**, if the attacker checks in before your device and no warning is raised yet.
- **Slow ID guessing** from many IP addresses.

OpenFLO does not pin devices to IP addresses. Home networks use NAT and dynamic addresses, so pinning would break real devices.

## How to reduce your risk

- **Keep a login on.** Use basic, OIDC or an auth proxy. Never use `none` on a server reachable from the internet.
- **Don't publish your server name.** The device API answers on the same name as the web app.
- **Consider LAN-only.** If all your devices are at one site, a LAN-only setup takes the device API off the internet. See [deploy.md](deploy.md#lan-only-split-dns).
- **Act on Device warnings.** Don't dismiss one you can't explain.
- **Keep OpenFLO updated.** Only the latest release gets security fixes.

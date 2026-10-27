# Changelog

All notable changes to OpenFLO are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-27

### Fixed

- **The container image now publishes for both x86-64 and ARM64.** The 0.1.0 image build timed out, so 0.1.1 is the first release with images on GHCR.

## [0.1.0] - 2026-10-27

The first release. See the [README](README.md) and [docs/](docs/) for what it does and how to deploy it.

### Added

- You can now run OpenFLO with one `docker compose up -d`: one image plus Caddy, with a device-ready TLS setup built in. HTTP-01, DNS-01 (Cloudflare) and bring-your-own certificates are supported.
- You can now finish setup in the browser: create the admin, confirm the server address, and check it the way a device connects, with a plain fix for each failing check (FR-16).
- You can now group devices into homes, each with its own time zone, and see at a glance which ones need attention (FR-1, FR-2).
- You can now add a device with only your phone, using the Add device wizard and two QR codes (FR-4).
- You can now move a device to a new network, resetting it with its button or, on your LAN, from OpenFLO itself (FR-4).
- You can now claim devices that check in without being registered (FR-5).
- You can now set the dose in mL or oz, pick a liquid, and calibrate it with one test dispense (FR-7).
- You can now see how full the bottle is, how many doses and days are left, and when to refill. Doses compensate as the bottle empties (FR-8).
- You can now queue a single **Dispense now** and follow it from queued to dispensed, behind a per-device dispensing switch (FR-6).
- You can now schedule doses daily, weekly, every few hours or once, with an optional double dose (FR-9).
- You can now choose how often a device checks in: Battery saver, Balanced, Responsive, or Testing under Advanced (FR-10).
- You can now see a 30-day battery trend and an estimate of when to replace the batteries (FR-11).
- You can now see a device's Wi-Fi network, signal and hardware details, with a guide for changing its Wi-Fi at the device (FR-3, FR-12).
- You can now see which changes are still *Waiting for device*, and when the device should next check in (FR-14).
- You can now sign in with a single admin account, OIDC (for example Authentik) or an auth proxy, and create API tokens for scripts (FR-15).
- You can now connect other clients by address: `/api/v1/server-info` and a versioned, documented API under `/api/v1` (FR-17).
- You can now back up and restore the database with one command, or turn on a daily backup.

### Security

- Your devices are guarded by per-IP rate limits, a cap on unclaimed devices, and no request-body logging for unknown devices (FR-13).
- You now get a **Device warning** when a device checks in from two places at once or reports different hardware. Remote dispenses and schedules pause until you confirm (FR-13).
- You can only register a device with a one-time pairing token from the wizard. It is stored as a hash and expires after 20 minutes (FR-4).
- OpenFLO now refuses to start with no login on a public server, with proxy sign-in but no trusted proxy address, or with incomplete OIDC settings (FR-15).
- Your browser sessions are signed, expire after 12 hours idle, and cross-site changes are refused. Sign-in allows 5 attempts per minute per IP (FR-15).
- You now run OpenFLO as an unprivileged user with no capabilities and a read-only root filesystem.
- You can now read how device identity works, and what the abuse controls do and don't prevent, in [docs/security-model.md](docs/security-model.md).

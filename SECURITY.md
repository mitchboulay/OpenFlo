# Security Policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **private vulnerability reporting**: open this repository's **Security** tab and choose **Report a vulnerability**. Please don't open a public issue for security problems.

You can expect an acknowledgement within 7 days. We'll agree on a disclosure timeline with you before anything is published.

## Supported versions

Only the latest release receives security fixes.

## The device-identity model (read this before exposing OpenFLO to the internet)

iFLO dispensers running stock firmware 3.0.64 **cannot authenticate** to OpenFLO:

- **Device IDs are public identifiers, not secrets.** A device identifies itself only by its device ID. That ID is derived from the device's Wi-Fi MAC address, so it can be guessed.
- **Registration is protected.** A device can only be *registered* with a one-time pairing token created in the OpenFLO app (stored hashed, expires after 20 minutes). Without UI access, no one can enroll a device.
- **Impersonation is possible but limited.** Someone who knows a registered device's ID can send fake telemetry or events for it, or consume a queued "dispense now" request so it never reaches the real device. They **cannot** make your real device dispense: commands only go to whoever asks for them.
- **OpenFLO limits that abuse:**
  - per-IP rate limits on the device API;
  - a cap on unclaimed devices;
  - no logging of request bodies from unknown devices;
  - **identity flags** that pause remote dispense and schedules when a device appears from two places at once or its hardware details change, until you acknowledge them.

These are mitigations, not authentication. Keep the device API on a hostname you don't publicize, and keep your OpenFLO login protected (basic auth, OIDC, or a trusted proxy). The device API is always reachable without a login because the firmware can't log in.

## Scope

In scope: the OpenFLO backend, web UI, Docker images and the shipped Caddy configuration.

Out of scope: the vendor's firmware and cloud, and third-party projects referenced in `research/`.

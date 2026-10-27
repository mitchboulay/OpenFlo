# Contributing to OpenFLO

Thanks for helping. OpenFLO is a self-hosted replacement cloud for iFLO drain-line dispensers running stock firmware, so changes can affect real devices that dose liquid. Please read the safety rules below before changing anything on the device path.

## Ground rules

- **Be kind.** This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- **Security issues go through private reporting,** not issues. See [SECURITY.md](SECURITY.md).
- **Never commit vendor firmware, vendor apps, packet captures, or secrets.** `artifacts/` holds checksums only; see `artifacts/README.md` for how to obtain the files locally.

## Device-path safety rules (non-negotiable)

The firmware reacts to some server responses in ways that can reset or drain a device. Every change to `backend/app/api/device_v2.py`, `backend/app/services/` or response models MUST keep these true, and the test suite enforces them:

1. Never send `INVALID_DEVICE_ID` or `NOT_UNIQUE` codes. The firmware factory-resets on them.
2. Never send an OTA `url`, or `isSettingsSynced: false`.
3. Error bodies carry no `fields` key, except the deliberate bottle lock. The firmware ignores error bodies without `fields`.
4. `remoteDispense` is only sent for an operator-queued request, exactly once.
5. Send `shift-time` before `fast-sync-time`. A `fast-sync-time` at or below 2 × `shift-time` silently becomes 48 hours.

Findings come from static analysis of firmware 3.0.64 plus hardware tests; the evidence is in `research/`.

## Development

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q

# UI (once ui/ exists)
cd ui && npm ci && npm test -- --run && npm run build
```

Pull requests:

- One logical change per PR, with tests. Bug fixes include a regression test.
- Describe what you verified. If you tested against real hardware, include the firmware version and what you observed.
- CI (tests, UI build, image build) MUST pass.

## License

By contributing you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).

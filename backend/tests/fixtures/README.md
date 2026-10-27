# Fixtures

These are **synthetic/static-derived** protocol fixtures, not captured vendor
responses:

- `register_device.json`, `update_device.json` — request bodies derived from
  `FUN_40093f50` and `FUN_40094c80`.
- `schedule_response.json` — response shape derived from `FUN_40097504`.
- Error envelope (`fields`, `code`, `message`): the firmware reads it regardless of HTTP status. `INVALID_DEVICE_ID` and `NOT_UNIQUE` trigger a factory reset and are blocked in `app/errors.py`.

They are deterministic and contain no real device identifiers or credentials.
Physical-device behavior remains unverified until Mission 008.

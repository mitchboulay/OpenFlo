# Backend migration and rollback runbook

Date: 2026-10-26. Status: **plan only**. No device configuration was changed.

## 1. Objective

Move the device’s cloud host from `https://backend.iflo.com` to a controlled
OpenFLO backend **without modifying firmware**, preserving sleep/dispense
behavior, with a tested rollback.

## 2. Preconditions

- OpenFLO backend deployed and reachable only from the lab VLAN.
- Publicly CA-trusted certificate for the chosen host, verified with and
  without SNI.
- Enrollment token hash configured; device registration tested with a mock.
- Gateway capture running; controller online; Mission 006 validated or at least
  observing.
- Device is on the isolated lab VLAN/SSID; operator present.
- Backups: current `/dev_info`, gateway capture, device label/ID, firmware
  hash, backend DB, certificate/key inventory, and the original host value.
- Explicit operator approval for every action that changes the device.

## 3. What is known and what is not

| Question | Status |
|---|---|
| Is the host stored as `https-host-address`? | CONFIRMED_STATIC (`FUN_40092f20`, `FUN_400959a0`) |
| Is it a full URL? | CONFIRMED_STATIC (`%s%s` in `FUN_40092f50`) |
| Can it be set by `POST /config`? | Code path exists; exact handler not fully traced (PARTIAL) |
| Does changing it affect Wi-Fi? | UNKNOWN; `SERVER_CREDENTIALS` can be sent separately in the provisioning payload, but the handler’s required combinations are not traced |
| Is a new registration token required? | Likely after host change; `FUN_40093f50` uses `x-device-ott` (INFERRED) |
| Can it be restored through the local API? | `POST /config` with the original host is the intended path; not runtime-tested |
| Does failure change wake/battery? | Not tested; likely finite retries and normal sleep (INFERRED) |
| Can rollback occur while sleeping? | The device only accepts local HTTP while awake; must wait for a wake window |
| Can a failed migration strand the device? | Possible if the new host is unreachable and the old host is not restored; physical recovery may be needed |
| Is factory reset a proven recovery? | **No.** The local API exposes reset paths, but this was not verified as restoring the original host |

## 4. Approval gates

1. **Gate A — design review:** TLS test, protocol spec, emulator tests, and this
   runbook reviewed.
2. **Gate B — mock validation:** emulator passes all tests; mock device
   registration/update/schedule safe responses.
3. **Gate C — bench test:** one device on an isolated bench, no dispense, no
   schedule, no OTA, operator present.
4. **Gate D — migration:** only after Gate C evidence is reviewed.

Mission 007 stops before Gate C.

## 5. Migration procedure (not executed)

1. Confirm the device is awake (controller wake event or local `/dev_info`).
2. Record `GET /dev_info` and the current host value from the provisioning
   payload/capture.
3. Confirm the OpenFLO backend health and certificate from the lab VLAN.
4. Send the host change through the **vendor-defined provisioning interface**
   (`POST /config` with `SERVER_CREDENTIALS.host`), not a guessed endpoint.
5. Observe the next wake:
   - `POST /device-api/v2/register` (if required) with `x-device-ott`;
   - `POST /device-api/v2/update-device` with `x-device-id`;
   - 200 response and no OTA/remote-dispense fields;
   - return to sleep.
6. Capture 2–3 natural wakes; record battery, wake duration, and errors.
7. Stop if any unexpected dispense, OTA, reboot, or repeated error occurs.

## 6. Rollback

1. Wait for the next wake window.
2. Set `SERVER_CREDENTIALS.host` back to `https://backend.iflo.com` via the
   provisioning interface.
3. Verify the device polls the original host and returns to normal sleep.
4. If the device is unreachable, use the local API only if the device is awake.
5. If no network path works, physical recovery is required: UART/flash access
   or vendor support. Do **not** claim factory reset is proven.
6. Restore any backed-up configuration and capture evidence.

## 7. Stop conditions

- Any motor activation or dispense.
- Any OTA attempt.
- Any unexpected reboot or repeated crash.
- Battery drain beyond the agreed threshold.
- TLS handshake failures on repeated wakes.
- Loss of local wake detection.
- Any sign the device is stranded.

## 8. Evidence to collect

- Backend request/response logs (redacted).
- Gateway pcap + DNS logs.
- `GET /dev_info` before/after.
- Wake timestamps and durations.
- Battery trend.
- TLS certificate chain test (with/without SNI).
- Rollback time and result.

## 9. Physical recovery

Keep the device, USB-serial adapter, boot-pad access, and the official firmware
image available. Recovery is a last resort and requires separate approval. No
flashing or device modification is authorized in Mission 007.

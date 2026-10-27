# Mission 008 proposal — controlled physical integration

Date: 2026-10-26. Status: **PROPOSAL ONLY**. Do not execute without explicit
operator approval.

## 1. Objective

Prove the OpenFLO backend path with **one** iFLO device on an isolated bench,
without dispensing, scheduling activation, or OTA.

## 2. Scope and non-goals

In scope:

- TLS connectivity to the OpenFLO endpoint.
- Registration and device identity.
- Initial `update-device` request/response.
- Safe response parsing.
- Return to deep sleep.
- Natural wake/reconnect.
- Battery-impact indicators.
- Rollback to the original backend.

Out of scope:

- Dispensing (manual, scheduled, remote, boosted).
- Schedule activation.
- OTA/firmware update.
- No-App Mode.
- Production DNS/firewall changes.

## 3. Common preconditions

- Mission 007 deliverables reviewed and accepted.
- Backend reachable only from the lab VLAN; certificate chain verified with and
  without SNI.
- Enrollment token hash configured; mock registration/update tests pass.
- Device on the isolated lab SSID/VLAN; operator present.
- Gateway capture and controller running (Mission 006 status recorded).
- Original host value and device `/dev_info` backed up.
- Rollback host value ready.
- Explicit approval for the host change.

## 4. Experiments

### E1 — TLS reachability from the lab (no device change)

- **Hypothesis:** the backend presents a chain the firmware’s CA bundle accepts.
- **Preconditions:** backend deployed privately; certificate issued.
- **Expected:** `openssl s_client` with and without SNI returns the expected
  leaf/intermediate chain; no public ingress.
- **Max duration:** 30 min.
- **Safety:** no device traffic.
- **Stop:** wrong cert, missing chain, TLS 1.2 failure.
- **Rollback:** none needed.
- **Evidence:** `openssl` output, Caddy log, firewall check.
- **Approval:** network operator.

### E2 — Host migration and registration

- **Hypothesis:** the provisioning interface accepts
  `SERVER_CREDENTIALS.host=https://<our-host>` and the device registers with
  `x-device-ott`.
- **Preconditions:** E1 passed; device awake; rollback value ready.
- **Expected:** `POST /register` with `x-device-ott`, 200; device stores
  `registred`.
- **Max duration:** one wake window (≤5 min).
- **Safety:** no Wi-Fi change; no factory reset; no dispense.
- **Stop:** wrong Wi-Fi, registration loop, repeated 4xx/5xx, unexpected reboot.
- **Rollback:** restore `https://backend.iflo.com` via provisioning; if
  unreachable, stop and use physical recovery plan.
- **Evidence:** backend logs, gateway DNS/pcap, `/dev_info`.
- **Approval:** explicit device-change approval.

### E3 — Initial update-device

- **Hypothesis:** the device sends a valid telemetry body and accepts a safe
  `{"data":{"isUpToDate":true}}` response.
- **Preconditions:** E2 passed.
- **Expected:** one `POST /update-device` with `x-device-id`; JSON body with the
  documented fields; 200; no OTA/remote fields returned.
- **Max duration:** one wake window.
- **Safety:** no control fields; backend logs redacted.
- **Stop:** any `remoteDispense`/`url` in logs, motor activity, OTA attempt.
- **Rollback:** same as E2.
- **Evidence:** redacted request/response, timing, battery.
- **Approval:** same as E2.

### E4 — Return to deep sleep

- **Hypothesis:** the device returns to sleep after a safe response.
- **Preconditions:** E3 passed.
- **Expected:** no further frames after the response; controller sees sleep;
  next wake occurs naturally.
- **Max duration:** 2 h observation.
- **Safety:** no polling from us while asleep.
- **Stop:** continuous wake/retry loop, battery drop beyond threshold.
- **Rollback:** restore original host.
- **Evidence:** pcap gaps, wake/sleep timeline, backend timestamps.

### E5 — Natural wake and reconnect

- **Hypothesis:** a second wake repeats registration/update without duplicate
  side effects.
- **Preconditions:** E4 passed.
- **Expected:** second `update-device`; same device ID; no duplicate
  registration; no control fields.
- **Max duration:** up to 24 h (or until the second wake).
- **Safety:** same.
- **Stop:** repeated registration storms, error loops.
- **Rollback:** restore original host.
- **Evidence:** two wake cycles, backend logs, battery.

### E6 — Battery-impact indicators

- **Hypothesis:** the OpenFLO path does not materially increase wake duration or
  battery drain versus the vendor path.
- **Preconditions:** baseline battery/wake data from Mission 006.
- **Expected:** wake duration within an agreed tolerance; battery trend stable.
- **Max duration:** 48 h.
- **Safety:** abort on abnormal drain or heat.
- **Stop:** battery drop > agreed threshold, repeated wake loops.
- **Rollback:** original host.
- **Evidence:** `/dev_info` battery, wake durations, backend timing.

### E7 — Rollback to the original backend

- **Hypothesis:** the original host can be restored and the device returns to
  normal vendor polling.
- **Preconditions:** E2–E6 data captured.
- **Expected:** device polls `backend.iflo.com`; no OpenFLO requests after
  rollback; normal sleep.
- **Max duration:** one wake window.
- **Safety:** no factory reset assumed; no firmware change.
- **Stop:** cannot restore host; device stranded.
- **Rollback:** physical recovery plan (separate approval).
- **Evidence:** DNS/pcap, backend absence, `/dev_info`.

## 5. Success criteria

- E1–E7 complete with no dispensing, no OTA, no schedule activation.
- Device returns to normal sleep after each cycle.
- Rollback verified.
- No unexplained error loops or battery anomalies.

## 6. Approval gates

1. Mission 007 acceptance.
2. Network/TLS review.
3. Device-change approval for E2.
4. Stop/rollback briefing before E2.

Mission 007 stops here.

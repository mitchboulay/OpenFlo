# Mission 006 proposal: Critical experiments

## Objective

Resolve the highest-impact unknowns that determine whether Option B (cloud replacement) is viable, and whether No-App Mode eliminates the need for it.

## Experiment 1 — No-App Mode behavior

**Hypothesis:** Enabling No-App Mode changes the device's operating behavior in a way that reduces or eliminates cloud dependency, possibly enabling a fixed local schedule.

**Prerequisites:**
- Device is awake (WiFi active)
- Baseline capture is still running (to observe behavior changes)
- Operator approval for configuration change

**Scope:**
1. During a wake window, send `POST /dev_actions {noAppMode: true}` from the gateway container
2. Immediately read `GET /dev_info` and observe whether new fields appear or existing fields change
3. Observe the device's subsequent behavior: wake interval, cloud polling pattern, mDNS changes
4. After observation period (minimum 2 hours), send `POST /dev_actions {noAppMode: false}` to revert

**Expected observations:**
- `/dev_info` may gain a `noAppMode: true` field
- The device may change its wake interval
- The device may stop polling `backend.iflo.com`
- The device may start a default dispense schedule
- Or: the toggle may silently fail (namVisible is false, the endpoint may reject the request)

**Success criteria:** The device accepts the command (HTTP 200) and observable behavior changes.
**Failure criteria:** HTTP error response, or no observable behavior change.

**Device risks:** Low. The toggle is a production firmware feature. Revertible via the same endpoint or factory reset.

**Rollback:** `POST /dev_actions {noAppMode: false}`, or `GET /resetdefault` for full factory reset.

**Operator approval required:** Yes — modifies device configuration.

## Experiment 2 — Manual dispense confirmation

**Hypothesis:** `POST /dev_actions {manualDispense: true, reboot: false, restoreToDefault: false}` triggers an immediate dispense cycle.

**Prerequisites:**
- Device is awake
- Bottle installed with fluid remaining
- Drain line connected or towel ready
- Operator physically present

**Scope:**
1. Read `GET /dev_info` to record current `doses` count
2. Send `POST /dev_actions {manualDispense: true, reboot: false, restoreToDefault: false}`
3. Record the HTTP response
4. Listen/watch for motor activation
5. Read `GET /dev_info` again to check if `doses` decremented

**Expected observations:**
- HTTP 200 response (possibly with JSON body)
- Audible motor activation (forward-reverse cycle)
- `doses` field decrements by 1

**Success criteria:** Motor activates, doses decrements, HTTP 200 returned.
**Failure criteria:** HTTP error, or no motor activation, or doses unchanged.

**Device risks:** Consumes one dose of cleaning fluid. The cartridge has 6 remaining. This is normal device operation.

**Rollback:** N/A — a dispense is an intentional one-time action.

**Operator approval required:** Yes — triggers dispensing.

## Experiment 3 — TLS certificate validation

**Hypothesis:** The device does or does not validate the TLS certificate when connecting to its configured backend URL.

**Prerequisites:**
- Device has been re-provisioned to point at a local server (requires Experiment 4 first), OR
- DNS override on the gateway to redirect `backend.iflo.com` to a local IP

**This experiment uses DNS override (less invasive than re-provisioning):**

**Scope:**
1. Generate a self-signed TLS certificate for `backend.iflo.com` on the gateway container
2. Start a minimal HTTPS server on the gateway container that logs incoming requests
3. Add a dnsmasq override on the gateway container: `address=/backend.iflo.com/192.168.30.1`
4. Wait for the device to wake and attempt its cloud poll
5. Observe whether the TLS handshake completes or aborts
6. If the handshake completes, log the HTTP request (method, path, headers, body)
7. Remove the DNS override after observation

**Expected observations (scenario A — validation off):**
- Device completes TLS handshake with the self-signed cert
- HTTP request is visible in the server log
- This reveals the cloud polling protocol (method, path, headers, body)

**Expected observations (scenario B — validation on, rejects self-signed):**
- Device sends ClientHello, receives ServerHello + certificate
- Device aborts the handshake (RST or no application data)
- Next step: try with a Let's Encrypt cert for a domain we control

**Expected observations (scenario C — cert pinning):**
- Same as B, but also rejects a valid CA-signed cert for a different CN
- This would block Path B entirely

**Success criteria:** We learn whether the device validates certificates.
**Failure criteria:** Device doesn't wake during the observation window.

**Device risks:** Low. DNS override is on the gateway, not the device. If the device rejects the cert, it simply retries on its next wake cycle. Normal operation resumes when the DNS override is removed.

**Rollback:** Remove the dnsmasq override. The device's next DNS resolution returns the real IP.

**Operator approval required:** Yes — temporarily intercepts DNS for the lab network.

## Experiment 4 — Cloud polling protocol capture

**Depends on:** Experiment 3 (TLS validation result).

If Experiment 3 shows the device accepts a self-signed cert, the server log from that experiment already contains the first protocol capture. This experiment extends the capture.

**Hypothesis:** The cloud polling protocol is a simple REST API with JSON payloads that can be replicated by a local server.

**Scope:**
1. Keep the DNS override and local HTTPS server running
2. Respond to the device's requests with minimal valid responses (empty JSON, or mirrored structure)
3. Capture multiple polling cycles to identify:
   - The HTTP method and path
   - Authentication headers (device token, API key)
   - Request body (device state report)
   - Expected response structure
   - How the device handles error responses
4. If possible, observe a schedule delivery by configuring a schedule in the app (which will send it to `backend.iflo.com` — currently our local server)

**Success criteria:** At least 3 complete request-response cycles captured and documented.
**Failure criteria:** Device stops polling after receiving unexpected responses.

**Rollback:** Remove DNS override. Factory reset if device enters an error state.

**Operator approval required:** Yes — extends DNS interception.

## Experiment 5 — Device wake interval measurement

**Hypothesis:** The device wakes at a predictable interval when idle (no schedule configured).

**Prerequisites:**
- Baseline capture still running
- No interference with the device

**Scope:**
1. Analyze the existing baseline capture for DHCP/ARP/DNS from the device's MAC
2. Identify all wake events and their timestamps
3. Calculate the wake interval distribution
4. Determine whether the interval is fixed, variable, or event-driven

**Expected observations:**
- A regular wake interval (e.g., every 4 hours, every 8 hours)
- Or irregular wakes driven by external events (operator interaction, app polling)

**Success criteria:** At least 3 wake events identified with timestamps.
**Failure criteria:** Fewer than 3 wakes in the capture window.

**Device risks:** None — purely passive analysis of existing capture data.

**Rollback:** N/A.

**Operator approval required:** No — read-only analysis.

## Experiment 6 — POST /config format testing

**Hypothesis:** The `POST /config` endpoint accepts the SERVER_CREDENTIALS payload independently of TOKEN and WIFI_CONFIG.

**Scope:**
1. During a wake window, send `POST /config` with only `SERVER_CREDENTIALS`:
   ```json
   {"data": [{"type": "SERVER_CREDENTIALS", "host": "https://192.168.30.1:8443"}]}
   ```
2. Observe the HTTP response
3. Read `GET /dev_info` to check if `wifiSSID` or other fields changed
4. On the next wake cycle, check if the device attempts to connect to 192.168.30.1:8443

**Success criteria:** The device accepts a partial config payload and changes its backend URL without resetting WiFi.
**Failure criteria:** HTTP error, or the device drops WiFi and enters provisioning mode.

**Device risks:** Medium. If the device requires all three config types together, sending a partial payload could put it in an unknown state. Factory reset is the recovery path.

**Rollback:** `POST /config` with original `SERVER_CREDENTIALS`, or `GET /resetdefault`.

**Operator approval required:** Yes — modifies cloud endpoint configuration.

## Priority order

| # | Experiment | Impact | Risk | Dependencies |
|---|---|---|---|---|
| 5 | Wake interval | Medium | None | None (passive) |
| 1 | No-App Mode | High | Low | Wake window |
| 2 | Manual dispense | Medium | None | Wake window + operator |
| 3 | TLS validation | Critical | Low | Wake window |
| 4 | Protocol capture | Critical | Low | Experiment 3 success |
| 6 | Config format | High | Medium | Wake window |

**Experiment 5 should be first** because it's purely passive and answers how long we have to wait between active experiments. Experiment 1 (No-App Mode) could eliminate the need for Experiments 3, 4, and 6 entirely.

# Adding devices

You add a dispenser to OpenFLO with the **Add device** wizard and your phone. You don't need a terminal or any config files.

## Before you start

- **Finish setup first.** The server address check must pass. **Add device** stays off while any of the three certificate checks fail. See [deploy.md](deploy.md#troubleshooting).
- **Pick the address for good.** The device saves the server address when it registers. Changing the address later means adding the device again.
- **Have a phone and your Wi-Fi password.** The phone joins the device's own hotspot for about a minute.
- **Create a home first.** Devices belong to a home.

### Does the device need a reset?

The device must be in setup mode, broadcasting a Wi-Fi network called `iFLO device`.

- **A device that isn't registered anywhere** starts this hotspot on its own.
- **A device registered somewhere else** (the vendor app, or another OpenFLO server) must be factory-reset first. Hold the **reset button** on the side of the device until its light changes. Don't hold the main button instead: a long press of it can start a dispense.

A factory reset wipes the device's Wi-Fi, registration and bottle state.

## The Add device wizard

Open a home and select **Add device**. Keep the wizard open in a browser on a computer or tablet, and use your phone for the device steps.

1. **Name it.** Give the device a name and, optionally, a location (for example "Air handler, attic").
2. **Join the device's Wi-Fi.** Scan the QR code with your phone's camera. It joins the `iFLO device` hotspot. Your phone leaves your home Wi-Fi for a minute; that's expected. Select **I've joined it**.
3. **Open the setup page.** Scan the second QR code on the same phone. The device's setup page opens. Choose your home Wi-Fi network, enter its password and tap **Save**. Then select **I've finished on my phone**. You can also select the copy-link button and open the link on that phone.
4. **Connecting.** The wizard shows live progress: **Found on your network**, then **Registered**. This usually takes under a minute.
5. **Done.** Set the bottle level next. Dispensing starts **off**. Turn it on from the device page once the bottle is in.

Good to know:

- **The codes work once.** The QR codes carry a one-time token. The wizard shows them only on the screen that started the setup.
- **A setup times out after 20 minutes.** Nothing changes on OpenFLO. Start again to get new codes.
- **Each home has one open wizard.** If you open **Add device** while one is running, you continue it.
- **Stopping is safe.** Select **Cancel** at any time. If the device was already reset, it waits in setup mode until you start again.

## Resetting a device you already have

To set up a device again, for example after moving it to a new Wi-Fi network, open it and choose **Move to a new network…** from the device menu (⋯), or **Change Wi-Fi…** in the Wi-Fi card. The wizard adds a **Reset it** step before the phone steps. The device keeps its name, history and settings in OpenFLO. The reset clears the device's bottle state, so set the bottle level again afterwards.

There are two ways to reset it.

### With the reset button

Hold the reset button on the device until its light changes, then select **I've reset it**. This always works, wherever the device is.

### Over your LAN

OpenFLO can send the factory reset itself when the server and the device share a network. Turn it on in `.env`, then run `docker compose up -d`:

```bash
OPENFLO_LOCAL_DEVICE_ACCESS=true
```

The **Reset it** step then offers **Reset now**. It works only while the device is awake, because it sleeps with Wi-Fi off. To wake it, twist the bottle and select **Reset now** within a minute or two.

OpenFLO sends one reset request with a short timeout and never retries it. It only connects to private LAN addresses the device reported. If the device can't be reached, the wizard says so and falls back to the reset button.

Leave this off if the server can't reach your devices' network, for example when devices are at another site.

## Changing Wi-Fi

Changing a device's network means setting it up again: **Change Wi-Fi…** in the Wi-Fi card opens the same wizard as [Resetting a device you already have](#resetting-a-device-you-already-have). Don't try to put the device into Wi-Fi mode with its buttons. A long press of the main button can start a dispense, and a long press of the reset button factory-resets it.

## Unclaimed devices

A device that checks in but isn't registered appears in a home's device list as a **New iFLO found** card, with its device ID, the address it checked in from, and when. This can happen when:

- the setup page saved Wi-Fi but registration didn't finish, or
- OpenFLO's database was lost or restored from an old backup.

Select **Add to home…** to claim it, and give it a name and location. A claimed device starts with dispensing **off**.

Until you claim it, an unclaimed device gets no dispenses, schedules or bottle approval. OpenFLO keeps at most `OPENFLO_UNCLAIMED_CAP` unclaimed devices (default 10).

If you don't recognize an unclaimed device, leave it unclaimed. See [security-model.md](security-model.md).

## Troubleshooting

**Add device is turned off, or says the address isn't verified.**
Run the address check in **Settings → Server address** and fix any failing row. See [deploy.md](deploy.md#troubleshooting).

**My phone doesn't see the `iFLO device` network.**
The device isn't in setup mode. Hold the reset button again. The hotspot only stays up for a while; if it disappeared, remove and reinsert the batteries, then reset again.

**The setup page doesn't open after joining the hotspot.**
Scan the second QR code ("Open the setup page"). Some phones drop a network without internet access; tell the phone to stay connected.

**The wizard stays on "Found on your network".**
The device reached OpenFLO but hasn't registered yet. Wait a minute. If it times out, start again with new codes.

**The wizard never gets to "Found on your network".**
The device didn't reach OpenFLO. Check that:
- the Wi-Fi password was right (the device stays in setup mode if it can't join);
- the home network can resolve the server name and reach port 443;
- for a LAN-only setup, the device's network uses the DNS server with your local record.

**"This setup timed out."**
The device didn't finish in 20 minutes. Make sure your phone saved the network, then start again.

**"Couldn't reach the device. Hold its reset button instead."**
The LAN reset couldn't reach the device. It was asleep, on another network, or `OPENFLO_LOCAL_DEVICE_ACCESS` is off. Use the reset button.

**A "Device warning" appears after setup.**
See [security-model.md](security-model.md#identity-flags). If you just moved or reset the device, select **It's fine (I moved it)**.

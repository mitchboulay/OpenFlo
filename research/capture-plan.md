# Capture plan

## Why not capture on an existing host

- **The Proxmox host and the Mac see no iFLO unicast.** The switch forwards a frame only to the port that owns the destination MAC. The iFLO's traffic would go AP → switch → UDM. Nothing passes through the Proxmox host or the Mac.
- **UDM tcpdump is ruled out.** Console SSH is closed. Turning it on means a password-auth shell on the production gateway, and the UDM gives us no clean way to later redirect DNS or intercept TLS for the device.
- **Port mirroring is ruled out.** Mirroring an AP uplink copies traffic from every SSID on that AP, and it needs a cable into a spare Proxmox NIC (`eno2`–`eno4` are unplugged). North-AP is meshed, so its traffic can't be mirrored at all. Mirroring only lets us watch; it can't block or redirect.
- **NetFlow is ruled out.** It gives flow metadata only, with no payloads or DNS names.

## Recommended: a dedicated Linux gateway on its own VLAN

Put the iFLO on a VLAN that the UDM does **not** route. A small LXC on Proxmox is that VLAN's only gateway, DHCP server and DNS server. Every packet the iFLO sends then has to pass through one interface we control, so **we see all of it by construction, not by hoping.**

```
 iFLO ──2.4 GHz "OpenFLO"──► AP (one AP group) ──trunk, VLAN 30──► USW port 2 ──► Proxmox eno1/vmbr0
                                                                                   │
                                          CT openflo-gw  net1: VLAN 30  192.168.30.1/24   ← tcpdump -i eth1, dnsmasq DHCP+DNS log
                                                         net0: untagged 192.168.1.<x>    → NAT → UDM → WAN
 Mac 192.168.1.50 ── static route 192.168.30.0/24 via 192.168.1.<x> ──► CT ──► iFLO   (Mac → iFLO allowed; iFLO → LAN dropped)
```

How each requirement is met:

| Requirement | Mechanism |
|---|---|
| Dedicated 2.4 GHz network | New SSID `OpenFLO`, 2.4 only, WPA2-PSK, PMF off, network VLAN 30, scoped to the AP group nearest the air handler |
| Isolation from production | The UDM has no interface or route on VLAN 30. The CT's forward chain drops VLAN 30 → 192.168.0.0/16 and 10.0.0.0/8. LAN devices can't reach 192.168.30.0/24 unless they add a route through the CT |
| Temporary internet | CT masquerades VLAN 30 out `net0`. To the UDM it looks like one Default-network client |
| DNS visibility | dnsmasq with `log-queries` + `log-dhcp`, upstream 1.1.1.1/9.9.9.9. **Not Pi-hole**: its blocklists could silently break iFLO telemetry and skew the baseline |
| Reliable capture | `tcpdump -i eth1 -w` inside the CT: every iFLO frame (DHCP, ARP, DNS, TLS, MQTT, NTP) crosses this interface |
| Analysis access | `sudo route add -net 192.168.30.0/24 192.168.1.<x>` on the Mac (local and temporary) plus a CT forward rule allowing Mac → VLAN 30 |
| Cut WAN later | One nftables rule in the CT (`iifname eth1 oifname eth0 drop`). The UDM, production firewall and other networks are untouched |
| Next step (Mission 003+) | The same box redirects DNS (dnsmasq `address=/<cloud-host>/192.168.30.1`), runs a local broker or HTTP stub, and can try TLS interception, all without touching production |

### Pre-flight checks (Mission 002, before the iFLO powers on)

1. A test client on `OpenFLO` (the phone, briefly, or the Mac's Wi-Fi) gets a 192.168.30.x lease from the CT. This shows the AP → switch → port 2 → vmbr0 tag path works and that the switch's DHCP snooping doesn't drop the CT's DHCP OFFERs.
2. That client resolves names (they appear in the dnsmasq log), reaches the internet, and **can't** reach the router, the Proxmox host, other LAN servers, other VLANs or the router's web UI.
3. The test client's traffic shows up in `tcpdump -i eth1`.
4. The Mac can reach the test client via the static route.

### Capture sequence for first provisioning (Mission 002)

1. Start a rotating pcap on the CT (`tcpdump -i eth1 -s0 -G 3600 -w openflo-%F-%H.pcap`) plus the dnsmasq log.
2. Start Proxyman on the Mac with the phone proxied (see mission-001.md, Proxyman section).
3. Provision the iFLO to `OpenFLO` through the app. If the app supports it, the phone stays on the home Wi-Fi so Proxyman can see it.
4. Leave it running at least 24–48 h for the baseline: boot, cartridge auth, weather/schedule fetch, heartbeats, the first dispense, and any OTA check.
5. Copy the pcaps to the Mac for Wireshark (needs installing; that's a Mission 002 decision).

## Fallback: UDM-native VLAN + UDM tcpdump

Make VLAN 30 a normal router-managed network (UDM DHCP, network isolation on) and capture with `tcpdump -i br30` over UDM SSH. This needs fewer new pieces, but it means enabling console SSH, it gives no clean path to DNS or TLS redirection, and cutting WAN means editing a production firewall rule. Use it only if the CT path fails pre-flight check 1.

## Provisioning blind spot

If the app uses **SoftAP** provisioning, the phone joins the iFLO's own temporary AP to hand over Wi-Fi credentials, and possibly a cloud token. That exchange never touches our network, so the CT can't see it. Proxyman also loses the phone, because the Mac isn't reachable from the iFLO's AP. If it uses **BLE**, it's radio-only. Either way the handoff protocol is best recovered from the **app binary** (Android APK static analysis with the REA tooling we already have), not by sniffing. The CT capture starts as soon as the iFLO joins `OpenFLO`.

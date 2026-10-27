# Mission 002: Network capture lab

Date: 2026-10-26. Status: **lab built, isolated, validated with a real client, ready for the iFLO's first connection.** All validation tests pass. The iFLO was not touched.

## Resources created

| Resource | Detail |
|---|---|
| Router network | `OpenFLO-Lab`, VLAN-only, VLAN 30 |
| SSID | `OpenFLO`, 2.4 GHz, WPA2-PSK, PMF off, one AP only |
| Secret | the lab SSID and PSK, kept in a secrets manager, not in the repo |
| LXC | the gateway container `openflo-gw`, 192.168.1.30 + 192.168.30.1, dnsmasq + nftables + tcpdump + `openflo-capture` |
| Host (automatic) | `eno1.30`, `vmbr0v30`, created by Proxmox for the tag-30 NIC. No host config files edited |
| Backup | a router configuration backup taken before the change |
| Workspace | `gateway/rootfs/etc/*`, `scripts/gateway-apply.sh`, `scripts/capture.sh`, `docs/*`, `research/*` |

## Changes to existing infrastructure

None to production policy. Existing firewall rules, DNS, DHCP, routing, SSIDs and APs other than the lab AP are untouched. The lab AP gained one 2.4 GHz SSID (now 4/4) and reprovisioned briefly, twice (create, then password change).

## Preflight findings

- VLAN 30 unused. A DHCP probe on VLAN 30 got no offer.
- The chosen CTID and 192.168.1.30 free, outside the default DHCP pool.
- The Proxmox switch port trunks all VLANs. `vmbr0` is not VLAN-aware, so Proxmox's traditional per-VLAN bridge is used.
- The nft NAT/conntrack modules weren't loaded on the host. They auto-loaded from the CT, so no host module config was needed.
- The Mac (192.168.1.50) is a dynamic lease on a private Wi-Fi MAC. It's pinned in nftables, not reserved on the router (that would be a production DHCP change).

## Deviations from the approved design

| Deviation | Reason |
|---|---|
| Disk 8 GB (planned 4 GB) | Capture headroom. The session guard stops at 3 GB / 1 GB free |
| PSK is a simple memorable phrase (operator choice) | Lab isolation comes from the VLAN + gateway policy, not the PSK |
| `mdns_enabled` reads true on OpenFLO-Lab (the PUT to false didn't stick) | No effect: the UDM has no interface on a VLAN-only network to reflect from |
| Lab clients aren't isolated from each other (L2 isolation off) | Only lab devices are on the SSID. Device-to-device traffic stays visible in the capture |
| Outbound DNS to third-party resolvers is allowed, not forced to dnsmasq | Baseline fidelity: if the iFLO hard-codes a resolver, we observe it (it's in the pcap) rather than masking it |
| Validation was done with the operator's phone plus gateway evidence, not the planned Mac Wi-Fi hop | The Mac was out of range of the lab AP |

## Results

Validation tests 0–10 PASS (6 by shared rule, 9 partial: no IPv6 attempted by the client). The detailed lab validation log is not published.

## Rollback readiness

A one-command WAN cut, a full teardown in 5 steps, and verification were written down. The pre-change router backup is taken.

## Questions for Mission 003

1. **Provisioning transport**: BLE, SoftAP or SmartConfig? Check the box/manual and the APK before powering on. It decides whether the credential handoff is observable at all.
2. **Android TLS visibility**: does the iFLO app trust user CAs? If not, choose between reading the APK statically and an instrumented device/emulator. No bypass was attempted.
3. **First-boot OTA**: allow a firmware update during baseline, or cut WAN the moment one is seen?
4. **Cartridge QR activation**: is it app ↔ cloud only, or does the device fetch a token? The baseline capture should answer this. Plan the provisioning session around it.
5. **Baseline length**: 24 h or 48 h before cutting WAN? (Default capture limits easily cover either.)
6. Reserve the Mac's IP on the router (a production DHCP change, needs approval) or keep pinning it in nftables?

## Ready-to-run for first provisioning

```bash
ssh root@192.168.1.2 "pct exec $CTID -- /usr/local/sbin/openflo-capture start first-provision"
# power on + provision the iFLO onto OpenFLO (PSK from the secrets manager) via the app
ssh root@192.168.1.2 "pct exec $CTID -- /usr/local/sbin/openflo-capture stop"   # after the baseline window
```

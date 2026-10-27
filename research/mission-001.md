# Mission 001: Lab network reconnaissance

Date: 2026-10-26. Read-only: no router, DNS, DHCP, firewall, routing, package or certificate changes. The iFLO was not touched.
Detail: `capture-plan.md` (how to see the traffic). The full inventory of the lab network is not published.

## 1. Infrastructure discovered (confirmed)

- **Gateway:** a consumer/prosumer router (the UDM below), console SSH closed.
- **Switching/Wi-Fi:** a managed PoE switch (no mirrors, DHCP snooping on) and several access points with per-AP groups.
- **Networks:** a default LAN (untagged, 192.168.1.0/24) plus a few tagged VLANs (IoT, guest). VLAN 30 is free.
- **DNS and proxies:** a LAN resolver and a reverse proxy already exist. None are relevant to iFLO.
- **Compute:** a Proxmox host on 192.168.1.2, switch port trunks all VLANs, `vmbr0` not VLAN-aware, tcpdump present.
- **Analyst Mac:** Wi-Fi only (192.168.1.50), Proxyman 6.14.0, Proxyman CA already in the System keychain. No Wireshark or mitmproxy.

## 2. Capture strategy

**A dedicated gateway LXC (`openflo-gw`) on a new, non-routed VLAN 30.** The UDM has no presence on VLAN 30, so the CT is the iFLO's only DHCP server, DNS resolver and path out. `tcpdump` on the CT's VLAN interface therefore sees every packet the device sends. No mirroring, no assumptions about who sees what on the network. The same box later blocks WAN with one rule and redirects cloud hostnames to a local stub, all without touching production.

Rejected options: tcpdump on an existing LAN host (it never sees the iFLO's unicast), UDM tcpdump (needs console SSH on the production gateway and is a dead end for redirection), port mirroring (mixes SSIDs, needs a cable, can't cover the meshed AP, can only watch). Full reasoning is in `capture-plan.md`.

## 3. Proxyman strategy

- **What it sees:** phone app ↔ iFLO cloud (REST, account, device claim, cartridge QR check, schedule and commands). **It never sees device ↔ cloud traffic**; the CT pcap covers that.
- **When:** for the first provisioning and first-day app use, running at the same time as the CT capture. Matching timestamps across the two shows which app action causes which device traffic.
- **How (Mission 002, not done):** phone HTTP proxy → 192.168.1.50:9090 on the home Wi-Fi, install and trust the Proxyman CA on the phone, enable SSL proxying for the iFLO hosts only.
- **Likely failures and what to do:**
  - Certificate pinning: fall back to APK static analysis or Frida on Android.
  - Flutter/React Native apps that ignore the system proxy: use Proxyman's iOS VPN mode or Android + Atlantis/Frida.
  - SoftAP provisioning: the phone leaves the home Wi-Fi, so Proxyman goes blind during the credential handoff.
- **Better source for the provisioning protocol:** the app binary itself, analysed with REA static tooling.

## 4. Proposed topology

```
iFLO ─2.4 GHz SSID "OpenFLO" (VLAN 30, one AP)─► switch ─trunk─► Proxmox vmbr0 ─► CT openflo-gw eth1 192.168.30.1
                                                                                     eth0 192.168.1.<x> ─NAT─► UDM ─► WAN
Phone (home Wi-Fi) ─HTTP proxy─► Mac Proxyman ─► internet
Mac ─static route 192.168.30.0/24 via CT─► iFLO   (one-way: iFLO cannot initiate to the LAN)
```

## 5. Risks and unknowns

| # | Item | Status |
|---|---|---|
| 1 | **Cloud-gated activation:** the app verifies the cartridge QR before the device runs. If the device needs a signed cloud token to dispense, local ownership has to emulate or replay it | Unknown, the top research question |
| 2 | Provisioning transport (BLE / SoftAP / SmartConfig) and the chipset | Unknown. Check the box/manual and the app's permissions before Mission 002 |
| 3 | Switch DHCP snooping could drop DHCP OFFERs from the CT on port 2 | Validate in pre-flight check 1 |
| 4 | Proxmox auto-creates `eno1.30` / `vmbr0v30` when a CT NIC gets `tag=30` on a non-VLAN-aware bridge. Small host-level side effect | Expected to be harmless. Note it in Mission 002 |
| 5 | Unprivileged LXC must be allowed to run nftables NAT and tcpdump on its own interfaces | Expected to work (own netns). Validate |
| 6 | Some ESP chipsets fail on WPA3 or PMF | Mitigated: WPA2-PSK, PMF off |
| 7 | First boot may run an OTA update that changes firmware behaviour | Capture it. Decide in Mission 002 whether to allow it |
| 8 | Cert pinning or proxy-bypass in the app | Likely. Fallbacks listed above |
| 9 | Which AP is nearest the air handler | Needed from you |
| 10 | Proxmox SSH had one connect timeout during recon | Transient, recovered immediately |
| 11 | Device firmware update over cloud could later remove local options | Blocking WAN after the baseline limits this |

## 6. Next actions (Mission 002, not executed)

1. **Router:** take a backup (`.unf`). Create network `OpenFLO-Lab` as **VLAN-only** (VLAN 30, no UDM gateway/DHCP). Create SSID `OpenFLO`: 2.4 GHz only, WPA2-PSK, PMF off, network OpenFLO-Lab, AP group = the AP nearest the air handler. Leave the PSK out of the repo.
2. **Proxmox:** create CT `openflo-gw` (Debian 12, unprivileged, 1 vCPU / 512 MB / 4 GB on `fastz`, next free CTID). `net0` = vmbr0 untagged, static 192.168.1.<x> (reserve on the router). `net1` = vmbr0 `tag=30`, 192.168.30.1/24. Install dnsmasq, nftables, tcpdump inside the CT. Keep the provisioning script in the repo (`deploy/examples/lab-vlan/`) so the CT is reproducible.
3. **CT config:** dnsmasq on eth1 only (DHCP 192.168.30.50–99, `log-queries`, `log-dhcp`, upstream 1.1.1.1/9.9.9.9). nftables: masquerade eth1→eth0, drop eth1 → RFC1918, allow established, allow 192.168.1.50 → 192.168.30.0/24.
4. **Pre-flight** (capture-plan.md checks 1–4) with a test client before the iFLO powers on.
5. **Mac:** `sudo route add -net 192.168.30.0/24 192.168.1.<x>`. Install Wireshark. Put the phone on the Proxyman proxy and trust the CA (you approve each step).
6. **Before provisioning:** pull the Android APK and do a static read of the provisioning flow and cloud hosts (REA), so we know whether it's SoftAP or BLE and which hosts to expect.
7. **Provision**, with the CT pcap + dnsmasq log + Proxyman all recording. Baseline for 24–48 h, then decide on the WAN cut.

## 7. Files created

- `research/mission-001.md`
- `research/capture-plan.md`

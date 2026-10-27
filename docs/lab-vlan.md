# Lab VLAN example (optional)

You don't need this to run OpenFLO. It is for researchers who want to watch a dispenser's traffic.

The example in [`deploy/examples/lab-vlan/`](../deploy/examples/lab-vlan/README.md) puts a dispenser on its own VLAN behind a small gateway container. The gateway adds:

- an isolated network with DHCP and DNS for the dispenser;
- a firewall that admits only known devices;
- a passive packet sniffer that groups the device's traffic into wake sessions;
- a capture tool for labelled packet captures.

It is written for one Proxmox home network. Treat it as a worked example, not an installer: edit its addresses, MAC and host names before you use it. Its README explains how to apply it.

The original lab's operating notes (build steps, rollback, network inventory) are not published; they describe one private network.

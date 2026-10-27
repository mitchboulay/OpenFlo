# Research notes

These notes are **historical interoperability research**. They record how iFLO firmware 3.0.64 talks to its cloud, found through static analysis of the firmware and tests on one lab device. They are the evidence behind OpenFLO's device-path rules (see [CONTRIBUTING.md](../CONTRIBUTING.md)).

- They are not user documentation. To run OpenFLO, start with the [README](../README.md) and [docs/deploy.md](../docs/deploy.md).
- Many notes describe the original lab setup and its host names, addresses and procedures. Those details are specific to that lab and may be out of date.
- [`migration-runbook.md`](migration-runbook.md) is historical: it moved the lab device by hand before OpenFLO had the Add device wizard. Use [docs/provisioning.md](../docs/provisioning.md) instead.
- Some notes mark their evidence: **[S]** static firmware analysis, **[R]** verified at runtime, **[I]** inference.

Vendor firmware, apps and packet captures are not in this repository; `artifacts/` holds checksums only.

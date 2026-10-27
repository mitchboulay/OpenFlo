#!/usr/bin/env bash
# Check the saved server address the way an iFLO connects: DNS, TLS 1.2 without SNI, an RSA leaf, a chain to the
# firmware's CA bundle (ISRG Root X1), the device healthcheck reaching this instance, and the port.
# Prints one line per check; exits non-zero when any check fails. Run on the host running the stack.
set -euo pipefail
cd "$(dirname "$0")/.."
exec docker compose exec -T openflo openflo check-address

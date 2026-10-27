#!/usr/bin/env python3
"""Create a local REA copy that admits Xtensa ELF (e_machine 94).

REA 6.4.0/6.8.0 reject EM_XTENSA in dist/domain/binaryTarget.js before the
Ghidra provider sees the file (upstream issue morluto/rea#3483). This script
copies the installed package, adds case 94, and accepts the installed Ghidra
12.2 release line (REA 6.4.0 only admits 12.1.x).

It returns "arm" only to satisfy REA's current architecture enum; the actual
disassembly language is forced with
REA_GHIDRA_LANGUAGE_ID=Xtensa:LE:32:default.

Usage:
    python3 patch_rea_xtensa.py [/tmp/rea-xtensa]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SOURCE = Path("/opt/homebrew/lib/node_modules/rea-agents")


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rea-xtensa")
    if not SOURCE.is_dir():
        print(f"source package not found: {SOURCE}", file=sys.stderr)
        return 1
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SOURCE, target)

    path = target / "dist/domain/binaryTarget.js"
    text = path.read_text()
    marker = '        case 183:\n            return "arm64";\n'
    replacement = (
        '        case 183:\n'
        '            return "arm64";\n'
        '        case 94: // EM_XTENSA: local workaround for the missing Xtensa lane\n'
        '            return "arm";\n'
    )
    if "case 94:" in text:
        print("already patched")
    elif text.count(marker) != 1:
        print("unexpected binaryTarget.js layout; not patched", file=sys.stderr)
        return 1
    else:
        path.write_text(text.replace(marker, replacement, 1))
        print(f"patched {path}")

    policy = target / "dist/ghidra/GhidraInstallationPolicy.js"
    policy_text = policy.read_text()
    old_version = 'export const SUPPORTED_GHIDRA_VERSION = "12.1.4";'
    new_version = 'export const SUPPORTED_GHIDRA_VERSION = "12.2";'
    if old_version in policy_text:
        policy.write_text(policy_text.replace(old_version, new_version, 1))
        print(f"patched {policy} to accept Ghidra 12.2")
    else:
        print(f"Ghidra version gate already changed or unexpected: {policy}")

    print(f"local REA: {target}")
    print("run with:")
    print(f"  node {target}/scripts/rea.mjs --version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

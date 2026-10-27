# REA Xtensa lane workaround (ESP32-S2)

Date: 2026-10-26. Status: **WORKING LOCALLY** — not an upstream fix.

## Problem

REA 6.4.0 (and 6.8.0, checked from the npm tarball) rejects an ELF with
`e_machine = 94` (`EM_XTENSA`) before the Ghidra provider is reached:

```
Cannot open artifact: unsupported ELF architecture.
details.reason = "unsupported ELF architecture"
```

The admission switch is in `dist/domain/binaryTarget.js`:

```js
const elfArchitecture = (machine) => {
    switch (machine) {
        case 3: return "x86";
        case 62: return "x86_64";
        case 8: return "mips";
        case 40: return "arm";
        case 183: return "arm64";
    }
    return undefined;
};
```

Upstream issue: [morluto/rea#3483](https://github.com/morluto/rea/issues/3483)
(open, 2026-10-14). The issue documents that Ghidra 12.1.4 already ships Xtensa
(`Ghidra/Processors/Xtensa`) and imports a wrapped image as
`Xtensa:LE:32:default`; only REA's admission boundary is missing. A contributor
volunteered, but no fix is merged as of 2026-10-26.

## Workaround

### 1. Wrap the ESP-IDF image as ELF

`artifacts/firmware/iflo-3.0.64.bin` is an app-only ESP-IDF image, not ELF.
`tools/make_xtensa_elf.py` emits a minimal ELF32 LE `ET_EXEC`:

- `e_machine = 94` (`EM_XTENSA`)
- `e_entry = 0x40025284`
- one `PT_LOAD` per image segment, at the segment load address
- segment permissions approximated from the ESP32-S2 memory map

```bash
python3 tools/make_xtensa_elf.py \
  artifacts/firmware/iflo-3.0.64.bin \
  artifacts/firmware/iflo-3.0.64.elf
```

The `.elf` is derived from vendor firmware and is ignored by `.gitignore`.

### 2. Patch a local REA copy

`tools/patch_rea_xtensa.py` copies the installed package to `/tmp/rea-xtensa`
and adds:

```js
case 94: // EM_XTENSA: local workaround for the missing Xtensa lane
    return "arm";
```

`"arm"` is only there to satisfy REA's current architecture enum (the MCP output
schema accepts `x86`, `x86_64`, `arm`, `arm64`, `mips`). The actual Ghidra
language is forced separately; the reported architecture is therefore
misleading and must not be treated as evidence.

```bash
python3 tools/patch_rea_xtensa.py
```

### 2b. Accept Ghidra 12.2 (local only)

Ghidra 12.2 is what Homebrew installs and it ships the Xtensa module. REA 6.4.0
accepts only 12.1.x, so the local copy also changes
`dist/ghidra/GhidraInstallationPolicy.js`:

```js
export const SUPPORTED_GHIDRA_VERSION = "12.2";
```

All other Ghidra checks (native decompiler, JDK 25) passed. This is a version
gate patch, not a claim that 12.2 is upstream-verified.

### 3. Force the Ghidra Xtensa language

```bash
export GHIDRA_INSTALL_DIR="$(brew --prefix ghidra)/libexec"   # adjust if needed
export REA_GHIDRA_LANGUAGE_ID="Xtensa:LE:32:default"
export REA_GHIDRA_COMPILER_SPEC_ID="default"
export PATH="/opt/homebrew/bin:$PATH"

node /tmp/rea-xtensa/scripts/rea.mjs inspect \
  artifacts/firmware/iflo-3.0.64.elf \
  --provider ghidra --format json
```

REA validates `REA_GHIDRA_LANGUAGE_ID` against the Ghidra language catalog, so
the ID must exist in the installed Ghidra. `Xtensa:LE:32:default` is the
little-endian windowed-ABI language used by ESP-IDF.

## Result (2026-10-26)

`rea inspect` succeeded on the wrapped image with **6,391 procedures** and
**3,695 strings**. Findings are in `research/rea-firmware-analysis.md`.

## Limitations

- This is a local, unsupported patch. Do not present it as REA's Xtensa lane.
- The ELF wrapper has no original section table, symbols or debug info. Function
  names are Ghidra-generated.
- `e_flags` is zero; the windowed ABI is selected through the language, not the
  ELF flags.
- The image is app-only; bootloader/partition/NVS are not covered.

## Proper fix

Add `EM_XTENSA` to REA's ELF admission layer as a first-class family, pin
`Xtensa:LE:32:default` / `gcc`, and record the windowed-vs-`call0` ABI from
`e_flags`. That is exactly the scope proposed in issue #3483.

#!/usr/bin/env python3
"""Wrap an ESP-IDF app image as a minimal ELF32 for Ghidra/REA.

A raw ESP-IDF .bin has no ELF header. Ghidra's Xtensa loader expects one, so
this script emits an ELF32 little-endian ET_EXEC with e_machine=EM_XTENSA (94)
and one PT_LOAD per image segment. The original .bin is never modified.

Usage:
    python3 make_xtensa_elf.py iflo-3.0.64.bin iflo-3.0.64.elf
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

EM_XTENSA = 94
ET_EXEC = 2
PT_LOAD = 1
PF_X, PF_W, PF_R = 1, 2, 4

HEADER_SIZE = 52
PHDR_SIZE = 32


def parse_image(data: bytes):
    if len(data) < 24 or data[0] != 0xE9:
        raise ValueError("not an ESP-IDF image (expected magic 0xE9)")
    segment_count = data[1]
    entry = struct.unpack_from("<I", data, 4)[0]
    chip_id = struct.unpack_from("<H", data, 12)[0]
    segments = []
    offset = 24
    for index in range(segment_count):
        load, size = struct.unpack_from("<II", data, offset)
        offset += 8
        blob = data[offset : offset + size]
        if len(blob) != size:
            raise ValueError(f"segment {index} is truncated")
        segments.append((load, blob))
        offset += size
    return entry, chip_id, segments


def segment_flags(load: int) -> int:
    # ESP32-S2 memory map approximations.
    if 0x3FF00000 <= load < 0x40000000:
        return PF_R | PF_W       # DRAM
    if 0x3F000000 <= load < 0x3FF00000:
        return PF_R              # DROM
    if 0x40000000 <= load < 0x50000000:
        return PF_R | PF_X       # IROM / IRAM
    return PF_R | PF_W


def build_elf(entry: int, segments):
    phnum = len(segments)
    data_offset = HEADER_SIZE + PHDR_SIZE * phnum
    data_offset = (data_offset + 15) & ~15

    out = bytearray(data_offset)
    phdrs = []
    cursor = data_offset
    for load, blob in segments:
        phdrs.append(
            (PT_LOAD, cursor, load, load, len(blob), len(blob),
             segment_flags(load), 1)
        )
        out += blob
        cursor += len(blob)
        pad = (-cursor) % 16
        if pad:
            out += b"\0" * pad
            cursor += pad

    ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    ehdr = ident + struct.pack(
        "<HHIIIIIHHHHHH",
        ET_EXEC, EM_XTENSA, 1, entry,
        HEADER_SIZE, 0, 0,
        HEADER_SIZE, PHDR_SIZE, phnum, 40, 0, 0,
    )
    out[0:HEADER_SIZE] = ehdr
    for index, phdr in enumerate(phdrs):
        start = HEADER_SIZE + index * PHDR_SIZE
        out[start : start + PHDR_SIZE] = struct.pack("<IIIIIIII", *phdr)
    return bytes(out)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    data = src.read_bytes()
    entry, chip_id, segments = parse_image(data)
    elf = build_elf(entry, segments)
    dst.write_bytes(elf)

    print(f"input:  {src} ({len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()})")
    print(f"output: {dst} ({len(elf)} bytes, sha256 {hashlib.sha256(elf).hexdigest()})")
    print(f"entry:  0x{entry:08x}  chip_id={chip_id}  segments={len(segments)}")
    for index, (load, blob) in enumerate(segments):
        print(f"  seg{index}: load=0x{load:08x} len={len(blob)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

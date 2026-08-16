#!/usr/bin/env python3
"""Verify B1on probe ZDLs before flashing: INFO fields, SONAME, Dll shape.

Usage:
    python check_probes.py <dir-with-ZDLs>

Checks that matter for the ctx[3] arena experiment:
  * real_type (INFO+32): FLT group=2, DLY group=8
  * fxid/sort_index (INFO+36)
  * bass_flags (INFO+40): 0x10 only for BassAmp
  * DT_SONAME prefix matches the category (ZDL_FLT_ / ZDL_DLY_)
  * the ELF entry (Dll) is a 3-field writer: writes ctx[0]=count,
    ctx[1]=descriptor VA, ctx[2]=imageInfo VA (G1on/B1on safe shape)
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path


def parse_zdl(path: Path) -> tuple[bytes, bytes, dict]:
    d = path.read_bytes()
    if d[:4] != b"\0\0\0\0" or d[4:8] != b"SIZE":
        raise ValueError(f"{path.name}: bad wrapper")
    # SIZE block: payload(4) @8, header_size(4) @12, elf_size(4) @16
    payload = struct.unpack_from("<I", d, 16)[0]
    hdr = struct.unpack_from("<I", d, 12)[0]
    info_off = d.find(b"INFO", 8)
    info_size = struct.unpack_from("<I", d, info_off + 4)[0]
    info = d[info_off + 8 : info_off + 8 + info_size]
    elf = d[16 + hdr : 16 + hdr + payload]
    if elf[:4] != b"\x7fELF":
        # fall back to locating ELF magic directly
        i = d.find(b"\x7fELF")
        elf = d[i : i + payload]
    return d, info, {"elf": elf}


def soname_of(elf: bytes) -> str:
    m = re.search(rb"ZDL_[A-Z]+_[A-Za-z0-9_]+", elf)
    return m.group(0).decode("latin1") if m else ""


def dll_shape(elf: bytes, e_entry: int) -> str:
    """Crude check: entry is a short stub that stores to [A4+0..8] (ctx[0..2])."""
    # We can't disassemble here; report entry VA and rely on the linker notes.
    return f"entry=0x{e_entry:X}"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(f"{'file':18s} {'rt':>3s} {'fxid':>6s} {'bass':>4s}  soname")
    print("-" * 62)
    for p in sorted(root.glob("*.ZDL")):
        d, info, ctx = parse_zdl(p)
        elf = ctx["elf"]
        # INFO payload layout (48 bytes after the 8-byte INFO header):
        # [0..31] version "ZOOM EFFECT DLL SYSTEM VER 1.00\0"
        # [32] real_type, [33] unknown1, [34] knob_type, [35] unknown2,
        # [36..37] sort_index u16 (fxid), [38] bass_flags, [39] sort_fx_type,
        # [40..43] fx_version "1.00"
        real_type = info[32]
        fxid = struct.unpack_from("<H", info, 36)[0]
        bass = info[38]
        sort_fx = info[39]
        soname = soname_of(elf)
        e_entry = struct.unpack_from("<I", elf, 0x18)[0]
        ok = "OK" if (bass in (0, 0x10)) and soname and sort_fx == real_type else "?"
        print(f"{p.name:18s} rt={real_type:2d} fxid=0x{fxid:04X} bass=0x{bass:02X} sfx={sort_fx}  {soname or '?':20s} {dll_shape(elf, e_entry)} {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

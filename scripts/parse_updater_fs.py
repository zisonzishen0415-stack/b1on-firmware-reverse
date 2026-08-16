#!/usr/bin/env python3
"""Parse the FS partition embedded in a Zoom B1on/G1on updater.

Layout (observed in B1on v1.30 / G1on v1.21 updaters):
  * a 32-byte-per-entry file directory, entries: 4x u32 + 12-byte name
    (padded with 0xFF), located where the first entry name appears
    (e.g. 160_COMP.ZDL at 0xc2b00 in B1on 1.30)
  * the payload area holds each file's bytes; ZDLs carry an 8-byte prefix
    before the standard NULL+SIZE wrapper

Usage:
    python parse_updater_fs.py <updater.exe> [--dump-dir]
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def find_dir_offset(b: bytes, probe: bytes) -> int:
    """Locate the directory by finding the first entry name."""
    i = b.find(probe)
    if i < 0:
        raise SystemExit(f"{probe!r} not found")
    return i


def parse_entries(b: bytes, dir_off: int, max_entries: int = 512) -> list[dict]:
    entries = []
    for n in range(max_entries):
        off = dir_off + n * 0x20
        e = b[off : off + 0x20]
        if len(e) < 0x20:
            break
        name = e[:12].rstrip(b"\x00\xff")
        name = "".join(chr(c) if 0x20 <= c < 0x7F else "?" for c in name)
        if not name:
            break
        w0, w1, w2, w3, w4 = struct.unpack_from("<5I", e, 12)
        entries.append(
            {"n": n, "w0": w0, "w1": w1, "w2": w2, "w3": w3, "w4": w4, "name": name}
        )
    return entries


def main() -> int:
    path = Path(sys.argv[1])
    b = path.read_bytes()
    probe = b"160_COMP.ZDL" if b"160_COMP.ZDL" in b else b"FLST_SEQ"
    dir_off = find_dir_offset(b, probe)
    entries = parse_entries(b, dir_off)
    print(f"file: {path.name}  dir @0x{dir_off:X}  entries: {len(entries)}")
    print(f"{'idx':>3s} {'f0':>10s} {'f1':>10s} {'f2':>10s} {'f3':>10s} {'f4':>10s}  name")
    for e in entries:
        print(
            f"{e['n']:3d} {e['w0']:10d} {e['w1']:10d} {e['w2']:10d} {e['w3']:10d} "
            f"{e['w4']:10d}  {e['name']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

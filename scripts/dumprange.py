#!/usr/bin/env python3
"""Hexdump / word-dump a byte range of a firmware chunk at a virtual address.

Usage:
    python dumprange.py <chunk.bin> <base_addr_hex> <start_addr_hex> <bytes>

Example:
    python dumprange.py chunk_c00c8580_13504.bin c00c8580 c00cb4f8 0x200
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def main() -> int:
    chunk, base_s, start_s, n_s = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    base, start, n = int(base_s, 16), int(start_s, 16), int(n_s, 0)
    data = Path(chunk).read_bytes()
    off = start - base
    if off < 0 or off + n > len(data):
        print(f"range out of bounds: chunk 0x{base:x}..0x{base + len(data):x}")
        return 1
    print(f"chunk {Path(chunk).name}  base 0x{base:x}  dump 0x{start:x}..0x{start + n:x}")
    for r in range(0, n, 16):
        addr = start + r
        hexb = " ".join(f"{b:02X}" for b in data[off + r:off + r + 16])
        words = struct.unpack_from("<4I", data, off + r)
        words = "  ".join(f"{w:08X}" for w in words)
        floats = " ".join(f"{struct.unpack_from('<f', data, off + r + i)[0]:.3g}"
                          for i in (0, 4, 8, 12))
        print(f"0x{addr:08X}  {hexb}  | {words}  | {floats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

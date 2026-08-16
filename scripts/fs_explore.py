#!/usr/bin/env python3
"""Explore the Zoom updater's embedded filesystem region (B1on/G1on).

The updater payload after the OS image records contains the FS partition.
This script dumps the region around the first ZDL INFO marker so the FS
container format can be pinned down.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    b = path.read_bytes()
    i = b.find(b"ZOOM EFFECT DLL SYSTEM VER 1.00")
    print(f"first ZDL INFO at 0x{i:X} (file {path.name}, {len(b)} bytes)")
    start = max(0, i - 0x300)
    for off in range(start, i, 0x10):
        seg = b[off : off + 0x10]
        print(f"{off:06X}: {seg.hex(' ')}  {repr(seg[:12])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

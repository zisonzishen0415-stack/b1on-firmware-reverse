#!/usr/bin/env python3
"""Catalog every embedded ZDL in a Zoom updater by scanning SIZE wrappers.

The updater stores FS files with an 8-byte prefix before the standard ZDL
wrapper (NULL + SIZE + header + INFO + ELF). This script locates each
wrapper, computes the real file span, validates INFO, and prints a table.

Usage:
    python scan_updater_zdis.py <updater.exe>
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def scan(path: Path) -> list[dict]:
    b = path.read_bytes()
    hits: list[tuple[int, int, int, int, bytes]] = []
    s = 0
    while True:
        i = b.find(b"SIZE", s)
        if i < 0:
            break
        if i >= 4 and b[i - 4 : i] == b"\0\0\0\0":
            payload = struct.unpack_from("<I", b, i + 4)[0]
            hdr = struct.unpack_from("<I", b, i + 8)[0]
            elfsz = struct.unpack_from("<I", b, i + 12)[0]
            if 0 < hdr < 0x400 and 0 < elfsz < 0x100000 and payload == 8:
                if b[i + 16 : i + 20] != b"INFO":
                    s = i + 4
                    continue
                info_off = i + 24
                info = b[info_off : info_off + 48]
                total = 20 + hdr + elfsz
                hits.append((i - 4, total, hdr, elfsz, info))
        s = i + 4
    recs = []
    for off, total, hdr, elfsz, info in hits:
        rt = info[32]
        fxid = struct.unpack_from("<H", info, 36)[0]
        elf = b[off + 20 + hdr : off + 20 + hdr + elfsz]
        soname = ""
        if b"ZDL_" in elf:
            j = elf.find(b"ZDL_")
            k = elf.find(b"\x00", j)
            soname = elf[j:k].decode("latin1", "replace")
        recs.append(
            {"off": off, "size": total, "rt": rt, "fxid": fxid, "soname": soname}
        )
    return recs


def main() -> int:
    path = Path(sys.argv[1])
    hits = scan(path)
    print(f"{path.name}: {len(hits)} ZDL wrappers")
    print(f"{'off':>9s} {'size':>9s} {'elfsz':>8s} {'rt':>3s} {'fxid':>5s}  soname")
    for r in hits:
        print(
            f"{r['off']:9d} {r['size']:9d} {r['size']-20-56 if False else '':8s}"
            f"{r['rt']:3d} 0x{r['fxid']:04X}  {r['soname']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

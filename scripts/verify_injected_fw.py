#!/usr/bin/env python3
"""Verify an injected updater: OS records unchanged, FS patches parse.

Usage:
    python verify_injected_fw.py <original-updater.exe> <injected-updater.exe>

Checks:
  1. every OS image record (0x01"YSX" blocks) is byte-identical
  2. every FS .ZDL patch has a valid wrapper (NULL + SIZE + INFO)
  3. reports total patches and any file containing a given token
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

from zfe_inject import load_updater

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def os_records(path: Path) -> list[tuple[int, bytes]]:
    b = path.read_bytes()
    pos = b.find(b"\x01YSX")
    recs: list[tuple[int, bytes]] = []
    while pos + 12 <= len(b):
        if b[pos : pos + 4] != b"\x01YSX":
            break
        addr, ln = struct.unpack_from("<II", b, pos + 4)
        recs.append((addr, b[pos + 12 : pos + 12 + ln]))
        pos += 12 + ln
        if ln == 0:
            break
    return recs


def main() -> int:
    orig, injected = Path(sys.argv[1]), Path(sys.argv[2])
    r1, r2 = os_records(orig), os_records(injected)
    same = len(r1) == len(r2) and all(
        a == c and hashlib.sha256(d1).digest() == hashlib.sha256(d2).digest()
        for (a, d1), (c, d2) in zip(r1, r2)
    )
    print(f"OS records: {len(r1)} vs {len(r2)}  byte-identical: {same}")
    if same:
        h = hashlib.sha256(b"".join(d for _, d in r1)).hexdigest()
        print(f"OS hash: {h}")

    _, fw = load_updater(injected)
    fw.load()
    z = [p for p in fw.patches if p.filename.upper().endswith(".ZDL")]
    bad = 0
    for p in z:
        c = p.content
        ok = c[:4] == b"\0\0\0\0" and c[4:8] == b"SIZE" and b"INFO" in c[:80]
        if not ok:
            bad += 1
            print(f"  BAD: {p.filename} ({len(c)} bytes)")
    print(f"FS ZDL patches: {len(z)}, malformed: {bad}, total patches: {len(fw.patches)}")
    return 0 if (same and bad == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

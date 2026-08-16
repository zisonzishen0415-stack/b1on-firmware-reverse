#!/usr/bin/env python3
"""Diff the embedded effect sets of the B1on and G1on updaters.

Usage:
    python compare_fs.py <b1on-updater.exe> <g1on-updater.exe>

Prints effects only in B1on, only in G1on, and shared (deduplicated by
fxid + real_type + SONAME base name).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from scan_updater_zdis import scan

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def base_name(soname: str) -> str:
    m = re.match(r"ZDL_[A-Z]+_([A-Za-z0-9_]+)", soname)
    return m.group(1).split("\\")[0] if m else soname


def key(r: dict) -> tuple:
    return (r["rt"], r["fxid"], base_name(r["soname"]))


def main() -> int:
    b1 = scan(Path(sys.argv[1]))
    g1 = scan(Path(sys.argv[2]))
    k1 = {key(r) for r in b1}
    k2 = {key(r) for r in g1}
    print(f"B1on wrappers: {len(b1)} unique: {len(k1)}")
    print(f"G1on wrappers: {len(g1)} unique: {len(k2)}")
    only_b1 = sorted(k1 - k2, key=lambda t: (t[0], t[1]))
    only_g1 = sorted(k2 - k1, key=lambda t: (t[0], t[1]))
    shared = sorted(k1 & k2, key=lambda t: (t[0], t[1]))
    print(f"\nshared: {len(shared)}")
    print(f"\nB1on only ({len(only_b1)}):")
    for rt, fxid, name in only_b1:
        print(f"  rt={rt:2d} fxid=0x{fxid:04X} {name}")
    print(f"\nG1on only ({len(only_g1)}):")
    for rt, fxid, name in only_g1:
        print(f"  rt={rt:2d} fxid=0x{fxid:04X} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

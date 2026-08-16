#!/usr/bin/env python3
"""Parse / rebuild Zoom FLST_SEQ.ZDT (on-device effect menu sequence).

Category section template (verified byte-for-byte on B1on 1.30 / G1on 1.21):
    b">>>" + b"\\x00" + cat_id + 8 zero bytes        (13 bytes, prefix)
    13-byte filename records ("NAME.ZDL" NUL padded)  (N records)
    b"<<<" + b"\\x00" + cat_id + 8 zero bytes        (13 bytes, suffix)

Usage:
    python edit_flst.py list <flst.zdt>
    python edit_flst.py add <flst.zdt> <NAME.ZDL> <cat_id> [-o out.zdt]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def parse(path: Path) -> tuple[bytes, list[tuple[int, list[str]]]]:
    b = path.read_bytes()
    cats: list[tuple[int, list[str]]] = []
    for m in re.finditer(rb">>>", b):
        if m.start() < 0x27:
            continue  # header marker, not a category
        cat_id = b[m.start() + 4]
        nxt = re.search(rb">>>", b[m.end() :])
        if nxt:
            suffix = nxt.start() + m.end() - 13
        else:
            last = b.rfind(b"<<<")
            suffix = last - 13
        seg = b[m.start() + 13 : suffix]
        names = []
        for i in range(0, len(seg), 13):
            rec = seg[i : i + 13]
            nm = rec.rstrip(b"\x00\xff").decode("ascii", "replace")
            if nm and "." in nm:
                names.append(nm)
        cats.append((cat_id, names))
    return b, cats


def rebuild_header_plus(b: bytes, new_names_region: bytes) -> bytes:
    """Insert a new names region while keeping the original header bytes."""
    # the first category prefix starts at 0x27
    return b[:0x27] + new_names_region


def insert_name(b: bytes, name: str, cat_id: int) -> bytes:
    """Insert a 12-byte filename record into the category, in place."""
    name = name.upper()
    if len(name) > 12:
        raise SystemExit(f"name too long: {name}")
    if len(name) > 12:
        raise SystemExit(f"name too long: {name}")
    record = name.encode("ascii").ljust(13, b"\x00")
    # locate category prefix: b">>>" + 0x00 + cat_id
    pat = b">>>" + bytes([0x00, cat_id])
    m = re.search(re.escape(pat), b)
    if not m:
        raise SystemExit(f"category {cat_id:02X} not found")
    start = m.start()
    nxt = re.search(rb">>>", b[start + 3 :])
    if not nxt:
        raise SystemExit("no next category marker")
    next_pos = start + 3 + nxt.start()
    names_end = next_pos - 13  # suffix length
    names_region = b[start + 13 : names_end]
    # avoid duplicates
    existing = [names_region[i : i + 13] for i in range(0, len(names_region), 13)]
    if record in existing:
        return b
    return b[:names_end] + record + b[names_end:]


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    if cmd == "list":
        _, cats = parse(Path(args[1]))
        for cid, names in cats:
            print(f"-- category {cid:02X} ({len(names)}) --")
            for n in names:
                print("   ", n)
        return 0
    if cmd == "add":
        src, name, cat = Path(args[1]), args[2].upper(), int(args[3], 0)
        out = Path(args[5]) if len(args) > 5 and args[4] == "-o" else None
        b, cats = parse(src)
        if not any(c == cat for c, _ in cats):
            raise SystemExit(f"category {cat:02X} not present")
        nb = insert_name(b, name, cat)
        if out:
            out.write_bytes(nb)
            print(f"added {name} to cat {cat:02X} -> {out} ({len(nb)} bytes, "
                  f"{len(nb) - len(b):+d})")
        else:
            sys.stdout.buffer.write(nb)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

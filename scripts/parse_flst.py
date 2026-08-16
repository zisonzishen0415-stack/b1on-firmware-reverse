#!/usr/bin/env python3
"""Parse Zoom FLST_SEQ.ZDT (on-device effect sequence list).

Observed layout (B1on 1.30 / G1on 1.21):
  header: b">>>" + zeros, b"<<<" + zeros, b">>>" + id bytes
  then per category: 12-byte filename records ("NAME.ZDL" NUL-padded),
  closed by b"<<<"+cat_id, padded, next b">>>"+cat_id...
This parser extracts filename tokens in order and records category id
boundaries (the byte just before/after each marker triple).
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def parse(path: Path) -> list[tuple[str, str]]:
    b = path.read_bytes()
    starts = [m.start() for m in re.finditer(rb">>>", b)]
    out: list[tuple[str, str]] = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(b)
        seg = b[s : min(end, s + 4096)]
        cat = "?"
        if s + 4 < len(b):
            cid = b[s + 4]
            if 0 < cid < 0x40:
                cat = f"{cid:02X}"
        for n in re.finditer(rb"[A-Z0-9_]{1,8}\.ZDL", seg):
            name = n.group(0).decode("ascii")
            out.append((cat, name))
    # de-duplicate consecutive repeats (marker windows overlap)
    dedup: list[tuple[str, str]] = []
    for item in out:
        if not dedup or item != dedup[-1]:
            dedup.append(item)
    return dedup


def main() -> int:
    for p in sys.argv[1:]:
        names = parse(Path(p))
        print(f"===== {Path(p).name}: {len(names)} effects =====")
        last = None
        for cat, name in names:
            if cat != last:
                print(f"  -- category {cat} --")
                last = cat
            print("   ", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

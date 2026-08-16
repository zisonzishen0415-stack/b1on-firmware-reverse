#!/usr/bin/env python3
"""Inject a custom ZDL into a B1on/G1on updater AND add it to the device menu.

Flow:
  1. zfe_inject: place the ZDL bytes into the FS (new file-table entry).
  2. edit_flst: insert "NAME.ZDL" into FLST_SEQ.ZDT's target category.
  3. zfe_inject: replace the FLST_SEQ.ZDT patch with the longer rebuilt file.

Usage:
    python inject_effect.py <updater.exe> <zdl> <cat_id> -o <out.exe>

cat_id is the INFO real_type / FLST_SEQ category id
(1 DYN, 2 FLT, 3 DRV, 4 AMP, 5 BASSAMP, 6 MOD, 7 SFX, 8 DLY, 9 REV).
"""

from __future__ import annotations

import sys
from pathlib import Path

from edit_flst import insert_name
from zfe_inject import Patch, load_updater

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def main(argv: list[str]) -> int:
    if len(argv) < 5 or "-o" not in argv:
        print(__doc__)
        return 1
    src_upd, zdl, cat_id = Path(argv[0]), Path(argv[1]), int(argv[2], 0)
    out = Path(argv[argv.index("-o") + 1])

    updater, fw = load_updater(src_upd)
    fw.load(keep_flst=True)

    # 1. inject the ZDL
    base = zdl.stem.upper()
    name = base[:8].rstrip("_") + ".ZDL"
    if any(p.filename.upper() == name.upper() for p in fw.patches):
        raise SystemExit(f"{name} already present")
    p = Patch(b"\xff" * 32)
    fw.inject(p, zdl.read_bytes(), name)
    print(f"[inject] {name}: {p.size} bytes -> block {p.addr}")

    # 2. edit FLST_SEQ
    flst = next((q for q in fw.patches if q.filename.upper() == "FLST_SEQ.ZDT"), None)
    if flst is None:
        raise SystemExit("FLST_SEQ.ZDT not found in updater")
    new_flst = insert_name(flst.content, name, cat_id)
    if len(new_flst) == len(flst.content):
        print(f"[menu] {name} already in category {cat_id:02X}; menu unchanged")
    else:
        fw.replace_patch("FLST_SEQ.ZDT", new_flst)
        print(f"[menu] added {name} to category {cat_id:02X} "
              f"(FLST_SEQ {len(flst.content)} -> {len(new_flst)} bytes)")

    # 3. save
    fw.rebuild_tables()
    fw.save(updater, out)
    print(f"saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""为 G1on/B1on FS 导出目录里的每个 ZDL 建效果清单(INFO + SONAME)。

输入:dump_updater_fs.py 导出的目录(每个 ZDL 前有 8B 记录头,后接
标准 NULL+SIZE 包装)。输出 CSV 到 stdout 或指定文件。

用法:
    python catalog_fs_zdl.py <fs_dir> [out.csv]
"""

from __future__ import annotations

import csv
import struct
import sys
from pathlib import Path


def parse_wrapper(b: bytes) -> dict | None:
    i = b.find(b"SIZE")
    while i >= 0:
        if i >= 4 and b[i - 4 : i] == b"\x00\x00\x00\x00":
            payload = struct.unpack_from("<I", b, i + 4)[0]
            hdr = struct.unpack_from("<I", b, i + 8)[0]
            elfsz = struct.unpack_from("<I", b, i + 12)[0]
            if 0 < hdr < 0x400 and 0 < elfsz < 0x100000 and payload == 8 \
                    and b[i + 16 : i + 20] == b"INFO":
                info = b[i + 24 : i + 24 + 48]
                elf = b[i + 20 + hdr : i + 20 + hdr + elfsz]
                soname = ""
                j = elf.find(b"ZDL_")
                if j >= 0:
                    k = elf.find(b"\x00", j)
                    soname = elf[j:k].decode("latin1", "replace")
                return {
                    "real_type": info[32],
                    "unk33": info[33],
                    "knob_type": info[34],
                    "unk35": info[35],
                    "fxid": struct.unpack_from("<H", info, 36)[0],
                    "sort_sub": struct.unpack_from("<H", info, 38)[0],
                    "info40": struct.unpack_from("<H", info, 40)[0],
                    "verstr": info[:32].split(b"\x00")[0].decode("latin1", "replace"),
                    "elf_size": elfsz,
                    "wrapper_size": 20 + hdr + elfsz,
                    "soname": soname,
                }
        i = b.find(b"SIZE", i + 4)
    return None


def main() -> int:
    fs_dir = Path(sys.argv[1])
    out = open(sys.argv[2], "w", newline="", encoding="utf-8") if len(sys.argv) > 2 else sys.stdout
    w = csv.writer(out)
    w.writerow(["file", "real_type", "unk33", "knob_type", "unk35", "fxid",
                "sort_sub", "info40", "verstr", "elf_size", "wrapper_size", "soname"])
    n_ok = n_bad = 0
    for f in sorted(fs_dir.glob("*.ZDL")):
        rec = parse_wrapper(f.read_bytes())
        if rec is None:
            n_bad += 1
            continue
        n_ok += 1
        w.writerow([f.name, rec["real_type"], rec["unk33"], rec["knob_type"],
                    rec["unk35"], f"0x{rec['fxid']:04X}", rec["sort_sub"],
                    f"0x{rec['info40']:04X}", rec["verstr"], rec["elf_size"],
                    rec["wrapper_size"], rec["soname"]])
    if out is not sys.stdout:
        out.close()
        print(f"catalog: {n_ok} ok, {n_bad} unparsed of {n_ok + n_bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

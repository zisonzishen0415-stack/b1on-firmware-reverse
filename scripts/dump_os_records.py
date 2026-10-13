#!/usr/bin/env python3
"""从 Zoom B1on/G1on Updater 中导出 OS 镜像记录(0x01"YSX" 块)。

记录格式: 01 59 53 58 + 小端 addr(4) + 小端 len(4) + data(len)
镜像之外的地址是未初始化 RAM,启动时为零,由运行时代码填充。

用法:
    python dump_os_records.py <updater.exe> <outdir>
产出:
    <outdir>/c<addr>_<len>.bin   每块原始数据
    <outdir>/records.json        记录清单(exe 偏移/虚拟地址/长度/SHA1)
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path


def os_records(b: bytes) -> list[tuple[int, int, int]]:
    """扫描全部 0x01"YSX" 记录,返回 (exe偏移, 虚拟地址, 长度)。"""
    recs: list[tuple[int, int, int]] = []
    pos = b.find(b"\x01YSX")
    while pos != -1:
        if pos + 12 > len(b):
            break
        addr, ln = struct.unpack_from("<II", b, pos + 4)
        ok = 0 < addr < 0xFFFF0000 and 0 < ln < 0x400000 and pos + 12 + ln <= len(b)
        if ok:
            recs.append((pos, addr, ln))
            pos = b.find(b"\x01YSX", pos + 12 + ln)
        else:
            pos = b.find(b"\x01YSX", pos + 4)
    return recs


def main() -> int:
    src, outd = Path(sys.argv[1]), Path(sys.argv[2])
    b = src.read_bytes()
    recs = os_records(b)
    outd.mkdir(parents=True, exist_ok=True)
    manifest = []
    print(f"file: {src.name}  records: {len(recs)}")
    for off, addr, ln in recs:
        data = b[off + 12: off + 12 + ln]
        name = f"c{addr:08x}_{ln:x}.bin"
        (outd / name).write_bytes(data)
        sha1 = hashlib.sha1(data).hexdigest()
        manifest.append(
            {"exe_offset": off, "addr": f"0x{addr:08X}", "len": ln,
             "name": name, "sha1": sha1}
        )
        print(f"  {name}  exe@0x{off:X}  sha1={sha1[:12]}")
    (outd / "records.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"manifest -> {outd / 'records.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

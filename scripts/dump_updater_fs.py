#!/usr/bin/env python3
"""导出 Updater 内嵌 FS 的全部文件(ZDL / FLST_SEQ.ZDT 等)。

复用 zfe_inject.py 的 4096B 块表解析(ZoomFirmwareEditor 同构实现)。
已存在且内容不同的目标文件不覆盖,改存 *.dup(避免无声丢数据)。

用法:
    python dump_updater_fs.py <updater.exe> <outdir>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zfe_inject  # noqa: E402


def main() -> int:
    src, outd = Path(sys.argv[1]), Path(sys.argv[2])
    updater, fw = zfe_inject.load_updater(src)
    fw.load(keep_flst=True)
    outd.mkdir(parents=True, exist_ok=True)
    print(
        f"file: {src.name}  patches: {len(fw.patches)}  "
        f"blocks: {fw.bin_blocks} used={fw.used_blocks()}"
    )
    total = 0
    for p in fw.patches:
        dst = outd / p.filename
        if dst.exists() and dst.read_bytes() != p.content:
            dst = outd / (p.filename + ".dup")
            print(f"  ! {p.filename} exists with different content -> {dst.name}")
        dst.write_bytes(p.content)
        total += p.size
    print(f"dumped {len(fw.patches)} files ({total} bytes) -> {outd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

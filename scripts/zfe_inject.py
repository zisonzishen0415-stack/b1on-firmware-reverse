#!/usr/bin/env python3
"""Zoom firmware updater editor (Python port of ZoomFirmwareEditor v0.98).

Usage:
  python zfe_inject.py list <updater.exe>
  python zfe_inject.py inject <updater.exe> <zdl> [<zdl> ...] -o <out.exe>

Implements the file-table + 4096-byte block format documented in the
ZoomFirmwareEditor README and mirrors FirmwareService/FileTableService/
PatchService from its Java sources. Only ZDL-type firmwares are supported
(G1on/G1Xon/B1on/B1Xon/MS-50G/MS-60B/MS-70CDR).
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

BLOCK = 4096
BLOCK_INFO = 6          # prev(2) + next(2) + size(2)
BLOCK_DATA = BLOCK - BLOCK_INFO
SYS_BLOCKS = 11
FIRST_DATA_BLOCK = 10
ITEM = 32
EMPTY = 0xFFFF
BIN_PATTERN = bytes.fromhex("55AA00010400")
EXCLUDE = {"FLST_SEQ.ZDT", "FLST_SEQ.ZT2"}


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


class Patch:
    def __init__(self, ft_item: bytes):
        self.ft_item = bytearray(ft_item)
        self.addr = u16(ft_item, 0)
        self.size = u32(ft_item, 4)
        end = ft_item.find(b"\x00", 8, 20)
        self.filename = ft_item[8:end if end >= 0 else 20].decode("ascii", "replace")
        self.content = b""


class Firmware:
    def __init__(self, updater: bytes, bin_start: int):
        self.bin_start = bin_start
        self.bin_blocks = u16(updater, bin_start + 8)
        end = bin_start + BLOCK * self.bin_blocks
        self.system = bytearray(updater[bin_start: bin_start + BLOCK * SYS_BLOCKS])
        self.data = bytearray(updater[bin_start + BLOCK * FIRST_DATA_BLOCK: end])
        self.blocks = [None] * (self.bin_blocks - FIRST_DATA_BLOCK)
        self.blocks[0] = "RESERVED"
        self.patches: list[Patch] = []

    def table_positions(self):
        return [BLOCK * (3 + i * 2) for i in range(4)]

    def table_valid(self, pos: int) -> bool:
        return self.system[pos + 1] == 0xA5 and self.system[pos + 5] == 0xFF

    def main_table_pos(self) -> int:
        main, alt = -1, -1
        for pos in self.table_positions():
            if self.table_valid(pos):
                if self.system[pos + 4] == 0xFF:
                    main = pos
                else:
                    alt = pos
        return main if main != -1 else alt

    def load(self, keep_flst: bool = False):
        pos = self.main_table_pos()
        if pos == -1:
            raise SystemExit("file table not found")
        for item_off in range(pos + 8, pos + BLOCK * 2, ITEM):
            raw = bytes(self.system[item_off: item_off + ITEM])
            if raw[:8] == b"\xff" * 8:
                continue
            p = Patch(raw)
            if not p.filename:
                continue
            if not keep_flst and p.filename in EXCLUDE:
                continue
            if not self._fill(p):
                continue
            if any(p.filename == q.filename for q in self.patches):
                continue
            self.patches.append(p)

    def replace_patch(self, name: str, content: bytes) -> None:
        """Replace an existing patch's content, re-allocating its blocks.

        The old blocks are orphaned (their chain headers stay in the data
        area but nothing references them), and the file gets fresh free
        blocks with the new size. Used to update FLST_SEQ.ZDT in place.
        """
        old = [p for p in self.patches if p.filename == name]
        if not old:
            raise SystemExit(f"patch {name} not present")
        p = old[0]
        self.patches.remove(p)
        addr, prev = p.addr, EMPTY
        while True:
            bpos = BLOCK * addr
            self.blocks[addr] = None
            nxt = u16(self.data, bpos + 2)
            if nxt == EMPTY or nxt == prev:
                break
            prev = addr
            addr = nxt
        np = Patch(b"\xff" * ITEM)
        self.inject(np, content, name)

    def _fill(self, p: Patch) -> bool:
        out = bytearray(p.size)
        prev, addr, cur = EMPTY, p.addr, 0
        if addr >= len(self.blocks):
            return False
        while True:
            bpos = BLOCK * addr
            if bpos + BLOCK > len(self.data):
                return False
            dsz = u16(self.data, bpos + 4)
            if cur + dsz > p.size:
                return False
            out[cur: cur + dsz] = self.data[bpos + BLOCK_INFO: bpos + BLOCK_INFO + dsz]
            cur += dsz
            if prev != EMPTY and u16(self.data, bpos) != prev:
                return False
            prev = addr
            self.blocks[addr] = p.filename
            nxt = u16(self.data, bpos + 2)
            if nxt == EMPTY:
                if cur == p.size:
                    p.content = bytes(out)
                    return True
                return False
            addr = nxt

    def used_blocks(self) -> int:
        return sum(1 for b in self.blocks if b is not None) - 1

    def total_blocks(self) -> int:
        return self.bin_blocks - SYS_BLOCKS

    def inject(self, p: Patch, content: bytes, name: str) -> None:
        if name in [q.filename for q in self.patches]:
            raise SystemExit(f"patch {name} already present")
        count = math.ceil(len(content) / BLOCK_DATA)
        if self.used_blocks() + count > self.total_blocks():
            raise SystemExit("not enough free blocks")
        free = [i for i in range(1, len(self.blocks)) if self.blocks[i] is None]
        if len(free) < count:
            raise SystemExit("free block not found")
        take = free[:count]
        p.addr = take[0]
        p.filename = name
        p.content = content
        p.size = len(content)
        for i, addr in enumerate(take):
            bpos = BLOCK * addr
            info = bytearray(b"\xff" * BLOCK_INFO)
            if i > 0:
                struct.pack_into("<H", info, 0, take[i - 1])
            if i < count - 1:
                struct.pack_into("<H", info, 2, take[i + 1])
                struct.pack_into("<H", info, 4, BLOCK_DATA)
            else:
                struct.pack_into("<H", info, 4, len(content) % BLOCK_DATA)
            self.data[bpos: bpos + BLOCK_INFO] = info
            chunk = content[i * BLOCK_DATA: (i + 1) * BLOCK_DATA]
            self.data[bpos + BLOCK_INFO: bpos + BLOCK_INFO + len(chunk)] = chunk
            self.blocks[addr] = name
        ft = bytearray(b"\xff" * ITEM)
        ft[0:2] = struct.pack("<H", p.addr)
        ft[2] = 0x01
        ft[4:8] = struct.pack("<I", len(content))
        nb = name.encode("ascii")
        ft[8:8 + len(nb)] = nb
        # Stock file-table entries NUL-pad short names to the full 12-byte name
        # field (_SVT.ZDL -> "_SVT.ZDL" + 4 x 0x00); 12-char names fill the field
        # exactly with no NUL (DUAL_CMP.ZDL / 160_COMP.ZDL do the same). Leaving
        # 0xFF padding makes the device fail to match the file by name.
        ft[8 + len(nb):20] = b"\x00" * (12 - len(nb))
        p.ft_item = ft
        self.patches.append(p)

    def rebuild_tables(self):
        table = bytearray(b"\xff" * (BLOCK * 2))
        off = 8
        for p in self.patches:
            table[off: off + ITEM] = p.ft_item
            off += ITEM
        for pos in self.table_positions():
            if self.table_valid(pos):
                self.system[pos + 8: pos + BLOCK * 2] = table[8:]

    def save(self, updater: bytearray, out_path: Path):
        data_end = BLOCK * (self.bin_blocks - FIRST_DATA_BLOCK)
        updater[self.bin_start + BLOCK * FIRST_DATA_BLOCK:
                self.bin_start + BLOCK * FIRST_DATA_BLOCK + data_end] = self.data
        updater[self.bin_start: self.bin_start + BLOCK * SYS_BLOCKS] = self.system
        out_path.write_bytes(updater)


def load_updater(path: Path) -> tuple[bytearray, Firmware]:
    updater = bytearray(path.read_bytes())
    idx = updater.find(BIN_PATTERN)
    if idx == -1:
        raise SystemExit("BIN not found in updater")
    return updater, Firmware(updater, idx)


def cmd_list(path: Path):
    _, fw = load_updater(path)
    fw.load()
    print(f"bin blocks: {fw.bin_blocks}  used: {fw.used_blocks()}  free: "
          f"{fw.total_blocks() - fw.used_blocks()}")
    for p in fw.patches:
        print(f"  {p.filename:<16} addr={p.addr:>5} size={p.size:>7} "
              f"blocks={math.ceil(p.size / BLOCK_DATA)}")


def cmd_inject(path: Path, zdls: list[Path], out: Path):
    updater, fw = load_updater(path)
    fw.load()
    for z in zdls:
        base = z.stem.upper()
        name = base[:8].rstrip("_") + ".ZDL"
        if len(name) > 12:
            raise SystemExit(f"filename too long: {z.name}")
        p = Patch(b"\xff" * ITEM)
        fw.inject(p, z.read_bytes(), name)
        print(f"injected {name}: {p.size} bytes -> block {p.addr}")
    fw.rebuild_tables()
    fw.save(updater, out)
    print(f"saved -> {out}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list")
    pl.add_argument("updater", type=Path)
    pi = sub.add_parser("inject")
    pi.add_argument("updater", type=Path)
    pi.add_argument("zdls", nargs="*", type=Path)
    pi.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "list":
        cmd_list(args.updater)
    else:
        cmd_inject(args.updater, args.zdls, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

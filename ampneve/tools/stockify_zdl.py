#!/usr/bin/env python3
"""Rewrite a ZDL's embedded ELF with the canonical TI C6000 section layout.

Stock G1on/B1on ZDLs ship the full 36-section TI layout (fixed section
indices: .audio=3, .text=4, .const=13, .fardata=18, .symtab=28,
.dynsym=29, .dynamic=30, .dynstr=31, .hash=32, .strtab=34, .shstrtab=35).
The minimal 12-section layout from the MS-70CDR linker works there because
that host resolves sections by name, but the B1on host reads sections by
index: every custom build so far freezes on select while stock files load.

This tool re-emits the ELF with the canonical section header table in stock
order, adds the missing NOBITS/empty sections plus a real .symtab/.strtab,
and keeps all section data, program headers and relocations byte-identical.

Usage: python stockify_zdl.py in.zdl out.zdl
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_NOBITS = 8
SHT_DYNSYM = 11
SHT_DYNAMIC = 6
SHT_HASH = 5
SHT_C6XABI_ATTRS = 0x6FFFFF03
SHT_TI_FLAGS = 0x7F000005

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHF_STRINGS = 0x20

STB_LOCAL = 0
STT_SECTION = 3
STT_FILE = 4
SHN_ABS = 0xFFF1

# (name, type, flags) in stock order. Sections marked has_data keep their
# bytes/addresses from the input ELF; the rest are emitted empty (NOBITS or
# zero-length PROGBITS exactly like stock zero-sized sections).
CANON = [
    (".rela.dyn",          SHT_RELA,     0x00, True),
    (".rela.plt",          SHT_RELA,     0x00, True),
    (".audio",             SHT_NOBITS,   0x00, False),
    (".text",              SHT_PROGBITS, SHF_ALLOC | SHF_EXECINSTR, True),
    (".stack",             SHT_NOBITS,   0x00, False),
    (".args",              SHT_NOBITS,   0x00, False),
    (".neardata",          SHT_NOBITS,   SHF_WRITE, False),
    (".rodata",            SHT_NOBITS,   0x00, False),
    (".bss",               SHT_NOBITS,   SHF_WRITE, False),
    (".text",              SHT_NOBITS,   SHF_EXECINSTR, False),
    (".cinit",             SHT_NOBITS,   0x00, False),
    (".cio",               SHT_NOBITS,   0x00, False),
    (".const",             SHT_PROGBITS, SHF_ALLOC, True),
    (".data",              SHT_NOBITS,   SHF_WRITE, False),
    (".switch",            SHT_NOBITS,   0x00, False),
    (".sysmem",            SHT_NOBITS,   0x00, False),
    (".far",               SHT_NOBITS,   SHF_WRITE, False),
    (".fardata",           SHT_PROGBITS, SHF_ALLOC | SHF_WRITE, True),
    (".ppinfo",            SHT_NOBITS,   0x00, False),
    (".ppdata",            SHT_NOBITS,   0x00, False),
    (".debug_info",        SHT_PROGBITS, 0x00, False),
    (".debug_line",        SHT_PROGBITS, 0x00, False),
    (".debug_abbrev",      SHT_PROGBITS, 0x00, False),
    (".debug_pubnames",    SHT_PROGBITS, 0x00, False),
    (".debug_aranges",     SHT_PROGBITS, 0x00, False),
    (".plt",               SHT_NOBITS,   0x00, False),
    (".c6xabi.attributes", SHT_C6XABI_ATTRS, 0x00, True),
    (".symtab",            SHT_SYMTAB,   0x00, False),
    (".dynsym",            SHT_DYNSYM,   0x00, True),
    (".dynamic",           SHT_DYNAMIC,  SHF_WRITE, True),
    (".dynstr",            SHT_STRTAB,   SHF_STRINGS, True),
    (".hash",              SHT_HASH,     0x00, True),
    (".TI.section.flags",  SHT_TI_FLAGS, 0x00, False),
    (".strtab",            SHT_STRTAB,   SHF_STRINGS, False),
    (".shstrtab",          SHT_STRTAB,   SHF_STRINGS, False),
]

TI_FLAGS_BLOB = bytes.fromhex(
    "0100000000000000000000000000000000000000000000000000")  # 26B, stock SVT


def _parse(elf: bytes):
    e_phoff, e_shoff = struct.unpack_from("<II", elf, 0x1C)
    e_phentsize, e_phnum = struct.unpack_from("<HH", elf, 0x2A)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", elf, 0x2E)
    phdrs = [struct.unpack_from("<8I", elf, e_phoff + i * e_phentsize)
             for i in range(e_phnum)]
    shdrs = [struct.unpack_from("<10I", elf, e_shoff + i * e_shentsize)
             for i in range(e_shnum)]
    names = elf[shdrs[e_shstrndx][4]:shdrs[e_shstrndx][4] + shdrs[e_shstrndx][5]]

    def cstr(off: int) -> str:
        end = names.find(b"\x00", off)
        return names[off:end].decode("latin1") if end >= 0 else ""

    secs: dict[str, dict] = {}
    index_by_name: dict[str, int] = {}
    for i, sh in enumerate(shdrs):
        nm = cstr(sh[0])
        if not nm:
            continue
        index_by_name[nm] = i
        secs[nm] = {"type": sh[1], "flags": sh[2], "addr": sh[3],
                    "offset": sh[4], "size": sh[5], "link": sh[6],
                    "info": sh[7], "align": sh[8], "entsize": sh[9]}
    return phdrs, secs, index_by_name, e_shoff


def _symtab(elf: bytes, secs: dict, canon_idx: dict[str, int],
            old_to_canon: dict[int, int], strtab: bytearray) -> bytes:
    """Standard TI .symtab: NULL + per-section + file + dynsym symbols."""
    syms = bytearray()

    def add(name: str, value: int, size: int, info: int, other: int, shndx: int):
        if name:
            no = strtab.find(name.encode() + b"\x00")
            if no < 0:
                no = len(strtab)
                strtab.extend(name.encode() + b"\x00")
        else:
            no = 0
        syms.extend(struct.pack("<IIIBBH", no, value, size, info, other, shndx))

    add("", 0, 0, 0, 0, 0)                                   # NULL
    for i, (name, _, _, _) in enumerate(CANON):              # section symbols
        add(name, secs.get(name, {}).get("addr", 0), 0,
            STB_LOCAL << 4 | STT_SECTION, 0, i + 1)
    add("SVT.c", 0, 0, STB_LOCAL << 4 | STT_FILE, 0, SHN_ABS)

    ds = secs.get(".dynsym", {})
    dstr = secs.get(".dynstr", {})
    if ds and dstr:
        sb = elf[ds["offset"]:ds["offset"] + ds["size"]]
        tb = elf[dstr["offset"]:dstr["offset"] + dstr["size"]]
        for off in range(0, len(sb), 16):
            no, val, size, info, other, shndx = struct.unpack_from("<IIIBBH", sb, off)
            if not no:
                continue
            end = tb.find(b"\x00", no)
            nm = tb[no:end].decode("latin1", "replace") if end >= 0 else ""
            add(nm, val, size, info, other, old_to_canon.get(shndx, shndx))
    return bytes(syms)


def stockify(elf: bytes) -> bytes:
    phdrs, secs, index_by_name, old_shoff = _parse(elf)
    canon_idx = {name: i + 1 for i, (name, _, _, _) in enumerate(CANON)}
    # Duplicate section names (two .text) must map to the FIRST canonical
    # occurrence, i.e. the real loadable section, not the NOBITS twin.
    name_to_first: dict[str, int] = {}
    for i, (name, _, _, _) in enumerate(CANON):
        if name not in name_to_first:
            name_to_first[name] = i + 1
    old_to_canon = {old: name_to_first[nm]
                    for nm, old in index_by_name.items() if nm in name_to_first}

    out = bytearray(elf[:old_shoff])          # header + phdrs + data, untouched

    strtab = bytearray(b"\x00")
    symtab = _symtab(elf, secs, canon_idx, old_to_canon, strtab)
    shstr_names = [""] + [n for n, _, _, _ in CANON]
    shstrtab = bytearray(b"\x00")
    for n in shstr_names[1:]:
        shstrtab.extend(n.encode() + b"\x00")

    new_off: dict[str, int] = {}
    new_off[".symtab"] = len(out);  out += symtab
    new_off[".strtab"] = len(out);  out += bytes(strtab)
    new_off[".TI.section.flags"] = len(out); out += TI_FLAGS_BLOB
    new_off[".shstrtab"] = len(out); out += bytes(shstrtab)
    new_size = {".symtab": len(symtab), ".strtab": len(strtab),
                ".TI.section.flags": len(TI_FLAGS_BLOB), ".shstrtab": len(shstrtab)}

    shdrs = bytearray()
    shdrs += b"\x00" * 40
    for i, (name, stype, sflags, has_data) in enumerate(CANON):
        idx = i + 1
        noff = shstrtab.find(name.encode() + b"\x00")
        sec = secs.get(name)
        if name in new_off:
            off, size, addr = new_off[name], new_size[name], 0
        elif sec and has_data:
            off = sec["offset"]
            size = sec["size"]
            addr = sec["addr"]
        else:
            off, size, addr = 0, 0, 0
        link = info = 0
        align, entsize = 1, 0
        if name == ".rela.dyn" or name == ".rela.plt":
            link, align, entsize = canon_idx[".dynsym"], 4, 12
        elif name == ".symtab":
            link, align, entsize = canon_idx[".strtab"], 4, 16
        elif name == ".dynsym":
            link, align, entsize = canon_idx[".dynstr"], 4, 16
        elif name == ".hash":
            link = canon_idx[".dynsym"]
        shdrs.extend(struct.pack("<10I", noff, stype, sflags, addr,
                                 off, size, link, info, align, entsize))

    shoff = len(out)
    out += shdrs
    struct.pack_into("<I", out, 0x20, shoff)
    struct.pack_into("<H", out, 0x30, len(CANON) + 1)
    struct.pack_into("<H", out, 0x32, len(CANON))
    return bytes(out)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    here = Path(__file__).resolve()
    zdl_root = (here.parent.parent.parent / "work" / "zoomreverse"
                / "ZoomMultistompZDL" / "build")
    sys.path.insert(0, str(zdl_root))
    from zdl import Zdl
    z = Zdl.load(src)
    new_elf = stockify(z.elf)
    z.elf = new_elf
    z.save(dst)
    print(f"[stockify] {src.name}: ELF {len(z.elf)} bytes, "
          f"{len(CANON) + 1} sections, canonical TI layout -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

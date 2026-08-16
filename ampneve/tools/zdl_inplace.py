#!/usr/bin/env python3
"""Transplant a compiled AmpNeve DSP into a STOCK B1on ZDL, in place.

The B1on firmware gives NEW/custom ZDL identities only a tiny ctx[3] arena
(probe-proven: >= 1 KB of state writes freeze the pedal), but every STOCK
identity gets the real host-managed arena. So we keep the stock MODREV.ZDL
identity 100% intact and swap ONLY:
  * .text bytes (grown: our code appended after the stock 0x1120 bytes),
  * .const bytes (grown: our coefficient tables appended),
  * the descriptor's audio-handler pointer (stock 0x8380 -> our entry),
  * the matching dynsym value,
  * the knob label strings (same-length swaps),
  * the fardata VA (moves because .const grows).

The B1on loader caps the .audio window at VA 0x7800 / 0xd80 bytes (the
largest stock .audio is exactly 0xd80; every stock effect with more code
puts it in .text, whose stock max is 0x3760). Growing .audio past that cap
corrupted memory - the effect registered but showed the previous effect's
UI and made no sound. So the code now lives in the grown .text region
(appended after the stock handlers), like the stock PARTICLE/amp effects.

Everything else (INFO header, Dll_ModReverb, init/edit handlers, descriptor
rows, imageInfo, picture, w28 DSP weight) stays byte-identical, so the host
loads it exactly like the stock reverb and allocates the full arena.

Usage:
  python zdl_inplace.py --obj <our.obj> --stock <MODREV.ZDL> --out <out.ZDL>
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

sys.path.insert(0, str(ROOT.parent / "work" / "zoomreverse" / "ZoomMultistompZDL" / "build"))
from linker import (  # noqa: E402
    ObjFile,
    RT_ABS_L16,
    RT_ABS_H16,
    RT_PCR_S21,
    _is_sbr_reloc,
    _patch_abs_l16,
    _patch_abs_h16,
    _patch_pcr_s21,
)


# ---------------------------------------------------------------------------
# stock MODREV.ZDL layout constants (B1on firmware 1.30)
# ---------------------------------------------------------------------------
STOCK_AUDIO_FILE_OFF = 0x1160
STOCK_AUDIO_SIZE = 0xD80
STOCK_AUDIO_VA = 0x7800
STOCK_CONST_FILE_OFF = 0x1EE0
STOCK_CONST_SIZE = 0xB1A
STOCK_CONST_VA = 0x80000000
STOCK_FARDATA_FILE_OFF = 0x29FC
STOCK_FARDATA_SIZE = 0x18
STOCK_FARDATA_VA = 0x80000B1C

STOCK_TEXT_FILE_OFF = 0x40
STOCK_TEXT_SIZE = 0x1120
CODE_VA = 0x1120            # our code starts right after the stock .text
OLD_AUDIO_HANDLER_VA = 0x8380

# descriptor audio pointer lives at .const VA 0x80000648 (name row +0x28)
CONST_DESC_AUDIO_PTR_OFF = 0x648

# the effect-name row ASCII lives at .const+0x628 (12-byte field, padded
# with NULs). Purely a UI string - the loader resolves the descriptor via
# dynsym/relocations, not by this text, so renaming it is safe.
CONST_NAME_OFF = 0x628
CONST_NAME_SIZE = 12

# same-length knob label swaps (stock label offset in .const -> new text)
KNOB_LABELS = {
    0x658: b"Gain\x00",   # Depth  (5 chars -> "Gain" + null)
    0x688: b"Mastr",      # Decay
    0x6E8: b"Bass",       # Rate
    0x718: b"Mid\x00",    # Tone
    0x748: b"Treb",       # PreD
    0x7A8: b"Neve",       # Tail
}


def align_up(x: int, a: int) -> int:
    return (x + a - 1) & ~(a - 1)


def parse_elf(elf: bytes):
    """Return (sections, phdrs, ehdr_fields) with names."""
    e_phoff, e_shoff = struct.unpack_from("<II", elf, 28)
    e_phentsize, e_phnum = struct.unpack_from("<HH", elf, 42)
    e_shentsize, e_shnum = struct.unpack_from("<HH", elf, 46)
    e_shstrndx = struct.unpack_from("<H", elf, 50)[0]
    shstr_off = struct.unpack_from("<I", elf, e_shoff + e_shstrndx * e_shentsize + 16)[0]

    def getstr(off: int) -> str:
        end = elf.index(b"\0", off)
        return elf[off:end].decode("latin1")

    secs = []
    for i in range(e_shnum):
        sh = elf[e_shoff + i * e_shentsize : e_shoff + (i + 1) * e_shentsize]
        name_off, typ, flags, addr, off, size, link, info, align, entsize = (
            struct.unpack_from("<IIIIIIIIII", sh, 0)
        )
        secs.append({
            "idx": i,
            "name": getstr(shstr_off + name_off),
            "type": typ,
            "flags": flags,
            "addr": addr,
            "off": off,
            "size": size,
            "link": link,
            "info": info,
            "align": align,
            "entsize": entsize,
        })

    phdrs = []
    for i in range(e_phnum):
        ph = elf[e_phoff + i * e_phentsize : e_phoff + (i + 1) * e_phentsize]
        typ, off, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from(
            "<IIIIIIII", ph, 0
        )
        phdrs.append({
            "type": typ, "off": off, "vaddr": vaddr, "paddr": paddr,
            "filesz": filesz, "memsz": memsz, "flags": flags, "align": align,
        })

    return secs, phdrs, {
        "e_phoff": e_phoff, "e_shoff": e_shoff,
        "e_phentsize": e_phentsize, "e_phnum": e_phnum,
        "e_shentsize": e_shentsize, "e_shnum": e_shnum,
        "e_shstrndx": e_shstrndx,
    }


def find_dynsym(elf: bytes, secs, name: str):
    """Return (dynsym_section_idx, entry_offset_within_elf) for a symbol."""
    dynsym = next(s for s in secs if s["name"] == ".dynsym")
    dynstr = next(s for s in secs if s["name"] == ".dynstr")
    dstr = elf[dynstr["off"] : dynstr["off"] + dynstr["size"]]
    for i in range(dynsym["size"] // 16):
        off = dynsym["off"] + i * 16
        n_off = struct.unpack_from("<I", elf, off)[0]
        end = dstr.index(b"\0", n_off)
        if dstr[n_off:end].decode("latin1") == name:
            return off
    raise KeyError(f"dynsym {name!r} not found")


def patch_elf(
    elf: bytes,
    secs,
    phdrs,
    eh,
    blob: bytes,
    const_blob: bytes,
    audio_entry_va: int,
    new_name: str | None = None,
) -> bytes:
    """Rebuild the ELF with grown .text/.const and shifted metadata."""
    new_text_size = STOCK_TEXT_SIZE + align_up(len(blob), 32)
    new_const_size = align_up(align_up(STOCK_CONST_SIZE, 8) + len(const_blob), 8)

    new_audio_file_off = STOCK_TEXT_FILE_OFF + new_text_size
    new_const_file_off = new_audio_file_off + STOCK_AUDIO_SIZE
    new_fardata_file_off = align_up(new_const_file_off + new_const_size, 4)
    new_fardata_va = STOCK_CONST_VA + align_up(new_const_size, 4)
    delta_after_fardata = new_fardata_file_off - STOCK_FARDATA_FILE_OFF

    out = bytearray()
    out.extend(elf[:STOCK_TEXT_FILE_OFF])            # ELF header + phdrs
    out.extend(elf[STOCK_TEXT_FILE_OFF:STOCK_TEXT_FILE_OFF + STOCK_TEXT_SIZE])
    out.extend(blob)
    out.extend(b"\0" * ((STOCK_TEXT_FILE_OFF + new_text_size) - len(out)))
    assert len(out) == new_audio_file_off

    # stock .audio bytes stay byte-identical at the same VA
    audio_old = elf[STOCK_AUDIO_FILE_OFF:STOCK_AUDIO_FILE_OFF + STOCK_AUDIO_SIZE]
    out.extend(audio_old)
    assert len(out) == new_const_file_off

    const_old = elf[STOCK_CONST_FILE_OFF : STOCK_CONST_FILE_OFF + STOCK_CONST_SIZE]
    out.extend(const_old)
    out.extend(b"\0" * (align_up(STOCK_CONST_SIZE, 8) - STOCK_CONST_SIZE))
    out.extend(const_blob)
    out.extend(b"\0" * ((new_const_file_off + new_const_size) - len(out)))
    assert len(out) == new_const_file_off + new_const_size

    fardata_old = elf[STOCK_FARDATA_FILE_OFF : STOCK_FARDATA_FILE_OFF + STOCK_FARDATA_SIZE]
    out.extend(b"\0" * (new_fardata_file_off - len(out)))
    out.extend(fardata_old)

    # everything after old .fardata shifts by delta_after_fardata
    tail = elf[STOCK_FARDATA_FILE_OFF + STOCK_FARDATA_SIZE :]
    out.extend(tail)
    assert len(out) == len(elf) + delta_after_fardata

    # --- patch dynsym values (content is in the shifted tail) ---
    sym_audio = find_dynsym(elf, secs, "Fx_REV_ModReverb") + delta_after_fardata
    struct.pack_into("<I", out, sym_audio + 4, audio_entry_va)
    sym_knob = find_dynsym(elf, secs, "_infoEffectTypeKnob_A_2") + delta_after_fardata
    struct.pack_into("<I", out, sym_knob + 4, new_fardata_va)

    # descriptor audio pointer in the (moved) .const bytes
    const_audio_ptr = new_const_file_off + CONST_DESC_AUDIO_PTR_OFF
    struct.pack_into("<I", out, const_audio_ptr, audio_entry_va)

    # knobInfo pointers inside .const that referenced the old fardata VA
    for off in range(new_const_file_off,
                     new_const_file_off + STOCK_CONST_SIZE - 3):
        if out[off : off + 4] == struct.pack("<I", STOCK_FARDATA_VA):
            struct.pack_into("<I", out, off, new_fardata_va)

    # knob label strings (same length)
    for rel_off, text in KNOB_LABELS.items():
        abs_off = new_const_file_off + rel_off
        old = bytes(out[abs_off : abs_off + len(text)])
        out[abs_off : abs_off + len(text)] = text
        print(f"    label @ .const+{rel_off:#06x}: {old!r} -> {text!r}")

    # effect name shown in the pedal browser/edit UI (UI-only string)
    if new_name:
        enc = new_name.encode("ascii")
        if len(enc) >= CONST_NAME_SIZE:
            raise SystemExit(f"effect name {new_name!r} too long "
                             f"(max {CONST_NAME_SIZE - 1} chars)")
        name_off = new_const_file_off + CONST_NAME_OFF
        old_name = bytes(out[name_off : name_off + CONST_NAME_SIZE])
        padded = enc + b"\0" * (
            CONST_NAME_SIZE - len(enc)
        )
        out[name_off : name_off + CONST_NAME_SIZE] = padded
        print(f"    name @ .const+{CONST_NAME_OFF:#06x}: "
              f"{old_name!r} -> {padded!r}")

    # --- rewrite section headers ---
    new_shoff = eh["e_shoff"] + delta_after_fardata
    new_phoff = eh["e_phoff"] + delta_after_fardata
    for s in secs:
        sh_off_in_file = new_shoff + s["idx"] * eh["e_shentsize"]
        # sh_offset field is at +16, sh_size at +20, sh_addr at +12
        # NOTE: stock ELFs carry TWO sections named ".text" -- the real
        # PROGBITS code section (idx 4) and a NOBITS placeholder (idx 10,
        # size 0). The loader walks every section entry, so patching the
        # NOBITS one to a large size makes it allocate/validate a phantom
        # 0x2e60 block and the effect registers but never initializes
        # (shows the previous effect's UI, no sound). Only touch PROGBITS.
        if s["name"] == ".text" and s["type"] == 1:
            struct.pack_into("<I", out, sh_off_in_file + 16, STOCK_TEXT_FILE_OFF)
            struct.pack_into("<I", out, sh_off_in_file + 20, new_text_size)
        elif s["name"] == ".audio":
            struct.pack_into("<I", out, sh_off_in_file + 16, new_audio_file_off)
        elif s["name"] == ".const":
            struct.pack_into("<I", out, sh_off_in_file + 16, new_const_file_off)
            struct.pack_into("<I", out, sh_off_in_file + 20, new_const_size)
        elif s["name"] == ".fardata":
            struct.pack_into("<I", out, sh_off_in_file + 12, new_fardata_va)
            struct.pack_into("<I", out, sh_off_in_file + 16, new_fardata_file_off)
        elif s["off"] > STOCK_FARDATA_FILE_OFF:
            struct.pack_into("<I", out, sh_off_in_file + 16, s["off"] + delta_after_fardata)

    # --- rewrite program headers ---
    for i, ph in enumerate(phdrs):
        ph_off = new_phoff + i * eh["e_phentsize"]
        if ph["vaddr"] == 0 and ph["filesz"] == STOCK_TEXT_SIZE:
            struct.pack_into("<IIIII", out, ph_off + 4,
                             STOCK_TEXT_FILE_OFF, 0, 0,
                             new_text_size, new_text_size)
        if ph["vaddr"] == STOCK_AUDIO_VA:
            struct.pack_into("<IIIII", out, ph_off + 4,
                             new_audio_file_off, STOCK_AUDIO_VA, STOCK_AUDIO_VA,
                             STOCK_AUDIO_SIZE, STOCK_AUDIO_SIZE)
        elif ph["vaddr"] == STOCK_CONST_VA:
            struct.pack_into("<IIIII", out, ph_off + 4,
                             new_const_file_off, STOCK_CONST_VA, STOCK_CONST_VA,
                             new_const_size, new_const_size)
        elif ph["vaddr"] == STOCK_FARDATA_VA:
            struct.pack_into("<IIIII", out, ph_off + 4,
                             new_fardata_file_off, new_fardata_va, new_fardata_va,
                             STOCK_FARDATA_SIZE, STOCK_FARDATA_SIZE)
        elif ph["off"] > STOCK_FARDATA_FILE_OFF:
            struct.pack_into("<I", out, ph_off + 4, ph["off"] + delta_after_fardata)

    # --- rewrite ELF header ---
    struct.pack_into("<I", out, 28, new_phoff)
    struct.pack_into("<I", out, 32, new_shoff)

    return bytes(out)


def build_blob(obj: ObjFile) -> tuple[bytes, bytes, dict, int]:
    """Return (blob, const_blob, sym_va, audio_entry_va)."""
    text = obj.get_section(".text")
    audio = obj.get_section(".audio")
    if text is None or audio is None or audio["size"] == 0:
        raise SystemExit("obj needs non-empty .text and .audio sections")

    text_data = text["data"] if text["size"] else b""
    audio_data = audio["data"]
    text_off_in_blob = 0
    audio_off_in_blob = align_up(len(text_data), 32)
    blob = bytearray(audio_off_in_blob)
    blob[: len(text_data)] = text_data
    blob.extend(audio_data)

    # our .const blob (all obj const sections, aligned)
    const_secs = [
        s for s in obj.sections
        if (s["name"] == ".const" or s["name"].startswith(".const:")) and s["size"] > 0
    ]
    const_blob = bytearray()
    const_off_by_sec: dict[int, int] = {}
    for s in const_secs:
        off = align_up(len(const_blob), max(s["align"], 4))
        const_blob.extend(b"\0" * (off - len(const_blob)))
        const_blob.extend(s["data"])
        const_off_by_sec[s["idx"]] = off
    const_blob = bytes(const_blob)

    OUR_CONST_VA = STOCK_CONST_VA + align_up(STOCK_CONST_SIZE, 8)
    section_va = {
        text["idx"]: CODE_VA + text_off_in_blob,
        audio["idx"]: CODE_VA + audio_off_in_blob,
    }
    for sec_idx, off in const_off_by_sec.items():
        section_va[sec_idx] = OUR_CONST_VA + off

    sym_va: dict[int, int] = {}
    for sym in obj.symbols:
        if sym["shndx"] in section_va:
            sym_va[sym["idx"]] = section_va[sym["shndx"]] + sym["value"]

    # apply relocations (mirrors repeat98 linker._apply_relocs)
    n_ok = 0
    for sec, base_off in ((text, text_off_in_blob), (audio, audio_off_in_blob)):
        for rel in obj.relocs.get(sec["idx"], []):
            sym = obj.symbols[rel["sym_idx"]]
            offset = rel["offset"]
            rtype = rel["type"]
            if _is_sbr_reloc(rtype):
                raise SystemExit(f"SBR reloc at {sec['name']}+0x{offset:X} - recompile with --mem_model:data=far")
            if rel["sym_idx"] not in sym_va:
                raise SystemExit(f"unresolved sym {sym['name']!r} at {sec['name']}+0x{offset:X}")
            addend = rel["addend"] if sym["shndx"] != 0 else 0
            target = sym_va[rel["sym_idx"]] + addend
            file_off = base_off + offset
            if rtype == RT_ABS_L16:
                _patch_abs_l16(blob, file_off, target)
            elif rtype == RT_ABS_H16:
                _patch_abs_h16(blob, file_off, target)
            elif rtype == RT_PCR_S21:
                _patch_pcr_s21(blob, file_off, target, CODE_VA + file_off)
            else:
                raise SystemExit(f"unknown reloc type {rtype} at {sec['name']}+0x{offset:X}")
            n_ok += 1

    audio_entry = next(
        s for s in obj.symbols if s["name"] == "Fx_AMP_AmpNeve"
    )
    audio_entry_va = CODE_VA + audio_off_in_blob + audio_entry["value"]
    print(f"  .text   {len(text_data):#x} bytes @ VA {CODE_VA:#x}")
    print(f"  .audio  {len(audio_data):#x} bytes @ VA {audio_entry_va:#x}")
    print(f"  .const  {len(const_blob):#x} bytes @ VA {OUR_CONST_VA:#x}")
    print(f"  relocs applied: {n_ok}")
    return bytes(blob), const_blob, sym_va, audio_entry_va


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obj", required=True, type=Path)
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--name", default=None,
                        help="replacement effect name shown in the pedal UI "
                             "(<= 11 chars; default keeps the stock name)")
    args = parser.parse_args(argv[1:])

    obj = ObjFile(str(args.obj))
    blob, const_blob, _sym_va, audio_entry_va = build_blob(obj)
    print(f"  blob {len(blob):#x} bytes (grow .text 0x{STOCK_TEXT_SIZE:x} -> "
          f"0x{STOCK_TEXT_SIZE + align_up(len(blob), 32):x})")

    stock = args.stock.read_bytes()
    assert stock[:8] == b"\0\0\0\0SIZE", "not a ZDL"
    sz_payload, header_size, elf_size = struct.unpack_from("<III", stock, 8)
    elf_off = 4 + 16 + header_size
    elf = stock[elf_off : elf_off + elf_size]
    secs, phdrs, eh = parse_elf(elf)

    new_elf = patch_elf(elf, secs, phdrs, eh, blob, const_blob, audio_entry_va,
                        args.name)

    out = bytearray()
    out.extend(stock[:elf_off])                       # NULL + SIZE + INFO
    struct.pack_into("<I", out, 16, len(new_elf))     # SIZE.elf_size
    out.extend(new_elf)
    args.out.write_bytes(out)
    print(f"\n  wrote {args.out} ({len(out)} bytes, stock was {len(stock)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

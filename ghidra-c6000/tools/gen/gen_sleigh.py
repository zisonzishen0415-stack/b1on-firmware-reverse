#!/usr/bin/env python3
"""Generate a TMS320C6000 SLEIGH module plus a rebuilt firmware image.

Inputs (all under the project analysis dir):
  analysis/b1on_os/chunk_*.bin   raw firmware chunks (code + data)
  analysis/b1on_os/*.dis         TI dis6x output for the code chunks

Outputs:
  work/c6000-sleigh/lang/TMS320C6000.slaspec/.ldefs/.cspec
  work/c6000-sleigh/image/*.bin  patched chunks (16-bit words -> synthetic)
  work/c6000-sleigh/image/manifest.json

Design notes
------------
* One SLEIGH constructor per distinct instruction word.  32-bit words keep
  their real encoding (p bit masked out).  16-bit compact words are replaced
  in the patched image by unique synthetic 16-bit patterns because their real
  decode depends on the fetch-packet header, which Ghidra's linear sweeper
  cannot see.
* Fetch-packet headers (signature 0xe------- in bits 31..28) get a dedicated
  no-op pseudo-instruction so the linear sweep can walk through packets.
* Addresses never change, so cross-function branch/call targets stay valid.
"""

from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_dis import (  # noqa: E402
    CtrlReg,
    Imm,
    Insn,
    Mem,
    Reg,
    RegPair,
    Units,
    parse_dis,
)
from semantics import emit_pcode  # noqa: E402


ROOT = Path(r"C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse")
ANALYSIS = ROOT / "analysis" / "b1on_os"
OUT = ROOT / "work" / "c6000-sleigh"
LANG = OUT / "lang"
IMG = OUT / "image"

CTRL_REGS = [
    "AMR", "CSR", "DNUM", "ECR", "EFR", "FADCR", "FAUCR", "FMCR",
    "GFPGFR", "GPLYA", "GPLYB", "ICR", "IER", "IERR", "IFR", "ILC",
    "IRP", "ISR", "ISTP", "ITSR", "NRP", "NTSR", "PCE1", "REP",
    "RILC", "SSR", "TSCH", "TSCL", "TSR", "ATSR",
]


def render_op(o) -> str:
    if isinstance(o, Reg):
        return o.name
    if isinstance(o, RegPair):
        return f"{o.hi}:{o.lo}"
    if isinstance(o, Imm):
        return f"{o.value:#x}"
    if isinstance(o, CtrlReg):
        return o.name
    if isinstance(o, Mem):
        off = render_op(o.offset) if o.offset else ""
        pre = {
            "pre_off": "+",
            "pre_off_neg": "-",
            "pre_inc": "++",
            "pre_dec": "--",
            "post_inc": "",
            "post_dec": "",
            "plain": "",
        }[o.mode]
        return f"*{pre}{o.base}{('[' + off + ']') if off else ''}"
    if isinstance(o, Units):
        return ",".join(o.names)
    return "?"


def signature(insn: Insn) -> tuple:
    return (
        insn.mnem,
        insn.unit,
        insn.side,
        insn.cross,
        tuple(render_op(o) for o in insn.ops),
    )


def chunk_map() -> dict[int, dict]:
    """base -> {bin, dis, is_code, size}"""
    chunks: dict[int, dict] = {}
    for f in sorted(ANALYSIS.glob("chunk_*.bin")):
        m = re.match(r"chunk_([0-9a-f]+)_([0-9a-f]+)\.bin$", f.name, re.I)
        if not m:
            continue
        base = int(m.group(1), 16)
        size = int(m.group(2), 16)
        dis = ANALYSIS / f"{base:08x}.dis"
        chunks[base] = {
            "bin": f,
            "dis": dis if dis.exists() else None,
            "is_code": dis.exists(),
            "size": size,
        }
    return chunks


def load_insns(chunks: dict[int, dict]) -> dict[int, list[Insn]]:
    per_chunk: dict[int, list[Insn]] = {}
    for base, info in chunks.items():
        if info["dis"] is None:
            continue
        insns = parse_dis(info["dis"])
        # keep only instructions within this chunk's byte range
        lo, hi = base, base + info["size"]
        insns = [i for i in insns if lo <= i.addr < hi]
        per_chunk[base] = insns
    return per_chunk


def collect_headers(chunks: dict[int, dict]) -> list[tuple[int, int]]:
    """Collect real fetch-packet header words (addr, word) from raw chunks.

    A header-based fetch packet stores its header at offset 28 of the
    32-byte-aligned packet, with bits 31..28 == 0xE.
    """
    headers = []
    for base, info in chunks.items():
        if not info["is_code"]:
            continue
        data = info["bin"].read_bytes()
        for off in range(28, len(data), 32):
            word = struct.unpack_from("<I", data, off)[0]
            if (word >> 28) == 0xE:
                headers.append((base + off, word))
    return headers


def assign_synthetic16(insns: list[Insn]) -> dict[tuple, int]:
    """Map 16-bit semantic signatures to unique synthetic words.

    Synthetic words are chosen so that their low 16 bits never equal the
    low 16 bits of any real 32-bit instruction word.  That makes every
    4-byte window starting at a 16-bit instruction address unable to match
    a real 32-bit constructor, which keeps the mixed-width decode
    deterministic for Ghidra's linear sweeper.
    """
    used = set()
    low16m = {((i.word & ~1) & 0xFFFF) for i in insns if i.width == 32}
    forbidden: set[int] = set()
    for v in low16m:
        forbidden.add(v)
        forbidden.add(v | 1)
    free = [w for w in range(1, 0x10000) if w not in forbidden]
    if len(free) < 20000:
        raise RuntimeError("not enough synthetic 16-bit patterns")
    mapping: dict[tuple, int] = {}
    fi = 0
    for i in insns:
        if i.width != 16:
            continue
        sig = signature(i)
        if sig in mapping:
            continue
        while free[fi] in used:
            fi += 1
        w = free[fi]
        fi += 1
        used.add(w)
        mapping[sig] = w
    return mapping


def build_constructors(insns: list[Insn], synth: dict[tuple, int]):
    """Return list of (word, width, insn, name) constructors."""
    by_word32: dict[int, Insn] = {}
    by_synth: dict[int, Insn] = {}
    ctr = Counter()
    names: dict[tuple, str] = {}
    out = []
    for i in insns:
        if i.width == 32:
            key = i.word & ~1  # mask the p bit
            if key in by_word32:
                other = by_word32[key]
                if signature(other) != signature(i):
                    # extremely unlikely; keep both with exact words
                    key2 = i.word
                    names.setdefault(key2, f"x{ctr['n']}")
                    ctr["n"] += 1
                    out.append((i.word, 32, i, names[key2], True))
                continue
            by_word32[key] = i
        else:
            sig = signature(i)
            w = synth[sig]
            if w in by_synth:
                continue
            by_synth[w] = i
    for key, i in by_word32.items():
        name = names.setdefault(("w32", key), f"{i.mnem.lower()}_{i.unit.lower()}{i.side}{'x' if i.cross else ''}_{key:08x}")
        out.append((key, 32, i, name, False))
    for w, i in by_synth.items():
        sig = signature(i)
        name = names.setdefault(("w16", sig), f"{i.mnem.lower()}_{i.unit.lower()}{i.side}{'x' if i.cross else ''}_{w:04x}")
        out.append((w, 16, i, name, False))
    return out, names


def emit_slaspec(constructors, names: dict, headers: list[tuple[int, int]], gap_words) -> str:
    L = []
    L.append("# TMS320C6000 (C64x+/C674x) - Zoom firmware canonical language")
    L.append("# Generated by gen_sleigh.py from TI dis6x corpus.")
    L.append("#")
    L.append("# 32-bit instructions use their real encodings (p bit masked);")
    L.append("# 16-bit compact instructions use synthetic patterns because")
    L.append("# their real decode depends on fetch-packet headers.")
    L.append("")
    L.append("define endian=little;")
    L.append("define alignment=1;")
    L.append("")
    L.append("define space ram type=ram_space size=4 default;")
    L.append("define space register type=register_space size=4;")
    L.append("")
    regs32 = [f"A{i}" for i in range(32)] + [f"B{i}" for i in range(32)]
    L.append("define register offset=0 size=4 [ " + " ".join(regs32) + " ];")
    L.append("define register offset=0x100 size=4 [ " + " ".join(CTRL_REGS) + " ];")
    L.append("define register offset=0x200 size=4 [ PC ];")
    L.append("")
    L.append("define token inst32 (32)")
    L.append("   w32 = (0,31)")
    L.append("   w31 = (1,31)")
    L.append(";")
    L.append("define token inst16 (16)")
    L.append("   w16 = (0,15)")
    L.append(";")
    L.append("")
    seen_h: set[int] = set()
    for _addr, word in headers:
        if word in seen_h:
            continue
        seen_h.add(word)
        L.append(f":fetch_packet_header_{word:08x} is w32 = 0x{word:08x} {{ }}")
    seen_g: set[int] = set()
    for _addr, word in gap_words:
        if word in seen_g:
            continue
        if word in seen_h:
            continue
        seen_g.add(word)
        L.append(f":gap_nop_{word:08x} is w32 = 0x{word:08x} {{ }}")
    L.append("")
    seen: set[tuple] = set()
    for word, width, insn, name, exact in constructors:
        if (word, width, exact) in seen:
            continue
        seen.add((word, width, exact))
        body = emit_pcode(insn)
        tok = "inst32" if width == 32 else "inst16"
        field = "w32" if width == 32 else "w16"
        if width == 32:
            pat = f"w32 = 0x{word:08x}" if exact else f"w31 = 0x{word >> 1:07x}"
        else:
            pat = f"{field} = 0x{word:04x}"
        pcode = "\n".join("    " + s for s in body) if body else "    "
        L.append(f":{name} is {pat} {{")
        L.append(pcode)
        L.append("}")
        L.append("")
    return "\n".join(L)


def emit_ldefs() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<language_definitions>
  <language processor="TMS320C6000" endian="little" size="32" variant="default"
            version="1.0" slafile="TMS320C6000.sla" processorspec="TMS320C6000.pspec"
            id="TMS320C6000:LE:32:default">
    <description>TI TMS320C6000 C64x+/C674x - Zoom firmware canonical (generated)</description>
    <compiler name="default" spec="TMS320C6000.cspec" id="default"/>
  </language>
</language_definitions>
"""


def emit_pspec() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<processor_spec>
  <programcounter register="PC"/>
  <default_memory_blocks>
    <memory_block name="ram" start_address="0x00000000" length="0x40000000" initialized="false"/>
  </default_memory_blocks>
</processor_spec>
"""


def emit_cspec() -> str:
    args = " ".join(
        [f'<pentry minsize="4" maxsize="4"><register name="{r}"/></pentry>'
         for r in ("A4", "B4", "A6", "B6", "A8", "B8", "A10", "B10", "A12", "B12")]
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<compiler_spec>
  <global>
    <range space="ram"/>
  </global>
  <stackpointer register="B15" space="ram" growth="negative"/>
  <default_proto>
    <prototype name="default" extrapop="0" stackshift="0">
      <input>{args}</input>
      <output>
        <pentry minsize="4" maxsize="4"><register name="A4"/></pentry>
      </output>
    </prototype>
  </default_proto>
</compiler_spec>
"""


def patch_images(chunks: dict[int, dict], per_chunk: dict[int, list[Insn]], synth: dict[tuple, int]):
    manifest = []
    for base, info in sorted(chunks.items()):
        data = bytearray(info["bin"].read_bytes())
        if info["is_code"]:
            for i in per_chunk.get(base, []):
                off = i.addr - base
                if i.width == 16:
                    w = synth[signature(i)]
                    data[off : off + 2] = struct.pack("<H", w)
        patched = IMG / info["bin"].name
        patched.write_bytes(bytes(data))
        if info["is_code"]:
            elf = wrap_elf(bytes(data), base)
            (IMG / info["bin"].with_suffix(".out").name).write_bytes(elf)
        manifest.append(
            {
                "file": patched.name,
                "base": f"{base:08x}",
                "size": info["size"],
                "code": info["is_code"],
            }
        )
    (IMG / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def wrap_elf(payload: bytes, vaddr: int) -> bytes:
    """Minimal 32-bit little-endian C6000 ELF with one executable .text load.

    Layout follows the proven wrap_for_dis6x.py builder (ZoomMultistompZDL):
    ELFOSABI_C6000_ELFABI, ET_DYN, .text immediately after the program
    header, and a compact section table ending with .shstrtab.
    """
    import struct

    shstr = b"\x00.text\x00.shstrtab\x00"
    name_text = shstr.index(b".text\x00")
    name_shstrtab = shstr.index(b".shstrtab\x00")

    ELF_HDR = 0x34
    PHDR_SIZE = 0x20
    NUM_PHDRS = 1
    SHDR_SIZE = 0x28
    NUM_SHDRS = 3  # NULL, .text, .shstrtab

    text_off = ELF_HDR + NUM_PHDRS * PHDR_SIZE
    shstr_off = text_off + len(payload)
    shdr_off = shstr_off + len(shstr)
    elf_size = shdr_off + NUM_SHDRS * SHDR_SIZE
    elf = bytearray(elf_size)

    elf[:4] = b"\x7fELF"
    elf[4] = 1    # ELFCLASS32
    elf[5] = 1    # ELFDATA2LSB
    elf[6] = 1    # EV_CURRENT
    elf[7] = 0x40 # ELFOSABI_C6000_ELFABI
    struct.pack_into("<H", elf, 0x10, 3)    # ET_DYN
    struct.pack_into("<H", elf, 0x12, 140)  # EM_TI_C6000
    struct.pack_into("<I", elf, 0x14, 1)
    struct.pack_into("<I", elf, 0x18, vaddr)
    struct.pack_into("<I", elf, 0x1C, ELF_HDR)
    struct.pack_into("<I", elf, 0x20, shdr_off)
    struct.pack_into("<I", elf, 0x24, 0)
    struct.pack_into("<H", elf, 0x28, ELF_HDR)
    struct.pack_into("<H", elf, 0x2A, PHDR_SIZE)
    struct.pack_into("<H", elf, 0x2C, NUM_PHDRS)
    struct.pack_into("<H", elf, 0x2E, SHDR_SIZE)
    struct.pack_into("<H", elf, 0x30, NUM_SHDRS)
    struct.pack_into("<H", elf, 0x32, NUM_SHDRS - 1)

    p = ELF_HDR
    struct.pack_into("<I", elf, p + 0x00, 1)   # PT_LOAD
    struct.pack_into("<I", elf, p + 0x04, text_off)
    struct.pack_into("<I", elf, p + 0x08, vaddr)
    struct.pack_into("<I", elf, p + 0x0C, vaddr)
    struct.pack_into("<I", elf, p + 0x10, len(payload))
    struct.pack_into("<I", elf, p + 0x14, len(payload))
    struct.pack_into("<I", elf, p + 0x18, 5)   # PF_R | PF_X
    struct.pack_into("<I", elf, p + 0x1C, 32)

    elf[text_off : text_off + len(payload)] = payload
    elf[shstr_off : shstr_off + len(shstr)] = shstr

    def _sh(idx, name_off, sh_type, flags, addr, off, sz, link=0, info=0, align=0, entsize=0):
        o = shdr_off + idx * SHDR_SIZE
        struct.pack_into("<I", elf, o + 0x00, name_off)
        struct.pack_into("<I", elf, o + 0x04, sh_type)
        struct.pack_into("<I", elf, o + 0x08, flags)
        struct.pack_into("<I", elf, o + 0x0C, addr)
        struct.pack_into("<I", elf, o + 0x10, off)
        struct.pack_into("<I", elf, o + 0x14, sz)
        struct.pack_into("<I", elf, o + 0x18, link)
        struct.pack_into("<I", elf, o + 0x1C, info)
        struct.pack_into("<I", elf, o + 0x20, align)
        struct.pack_into("<I", elf, o + 0x24, entsize)

    _sh(0, 0, 0, 0, 0, 0, 0)
    _sh(1, name_text, 1, 6, vaddr, text_off, len(payload), align=32)
    _sh(2, name_shstrtab, 3, 0, 0, shstr_off, len(shstr), align=1)
    return bytes(elf)


def wrap_elf_multi(segments) -> bytes:
    """Build one ELF with several PT_LOAD segments (code + data chunks).

    segments: list of (vaddr, payload, is_code, name)
    """
    import struct

    names = [s[3] for s in segments]
    shstr = b"\x00" + b"\x00".join(n.encode() for n in names) + b"\x00.shstrtab\x00"
    name_offs = {n: shstr.index(n.encode() + b"\x00") for n in names}
    name_shstrtab = shstr.index(b".shstrtab\x00")

    ELF_HDR = 0x34
    PHDR_SIZE = 0x20
    SHDR_SIZE = 0x28
    NUM_PHDRS = len(segments)
    NUM_SHDRS = len(segments) + 2  # NULL + segments + shstrtab

    text_off = ELF_HDR + NUM_PHDRS * PHDR_SIZE
    offs = []
    cur = text_off
    for _seg in segments:
        offs.append(cur)
        cur += _seg[1].__len__()
    shstr_off = cur
    shdr_off = shstr_off + len(shstr)
    elf_size = shdr_off + NUM_SHDRS * SHDR_SIZE
    elf = bytearray(elf_size)

    elf[:4] = b"\x7fELF"
    elf[4] = 1
    elf[5] = 1
    elf[6] = 1
    elf[7] = 0x40
    struct.pack_into("<H", elf, 0x10, 3)
    struct.pack_into("<H", elf, 0x12, 140)
    struct.pack_into("<I", elf, 0x14, 1)
    code_entries = [s[0] for s in segments if s[2]]
    struct.pack_into("<I", elf, 0x18, min(code_entries) if code_entries else segments[0][0])
    struct.pack_into("<I", elf, 0x1C, ELF_HDR)
    struct.pack_into("<I", elf, 0x20, shdr_off)
    struct.pack_into("<I", elf, 0x24, 0)
    struct.pack_into("<H", elf, 0x28, ELF_HDR)
    struct.pack_into("<H", elf, 0x2A, PHDR_SIZE)
    struct.pack_into("<H", elf, 0x2C, NUM_PHDRS)
    struct.pack_into("<H", elf, 0x2E, SHDR_SIZE)
    struct.pack_into("<H", elf, 0x30, NUM_SHDRS)
    struct.pack_into("<H", elf, 0x32, NUM_SHDRS - 1)

    for i, (vaddr, payload, is_code, _name) in enumerate(segments):
        p = ELF_HDR + i * PHDR_SIZE
        struct.pack_into("<I", elf, p + 0x00, 1)
        struct.pack_into("<I", elf, p + 0x04, offs[i])
        struct.pack_into("<I", elf, p + 0x08, vaddr)
        struct.pack_into("<I", elf, p + 0x0C, vaddr)
        struct.pack_into("<I", elf, p + 0x10, len(payload))
        struct.pack_into("<I", elf, p + 0x14, len(payload))
        struct.pack_into("<I", elf, p + 0x18, 5 if is_code else 6)
        struct.pack_into("<I", elf, p + 0x1C, 32)
        elf[offs[i] : offs[i] + len(payload)] = payload
    elf[shstr_off : shstr_off + len(shstr)] = shstr

    def _sh(idx, name_off, sh_type, flags, addr, off, sz, link=0, info=0, align=0, entsize=0):
        o = shdr_off + idx * SHDR_SIZE
        struct.pack_into("<I", elf, o + 0x00, name_off)
        struct.pack_into("<I", elf, o + 0x04, sh_type)
        struct.pack_into("<I", elf, o + 0x08, flags)
        struct.pack_into("<I", elf, o + 0x0C, addr)
        struct.pack_into("<I", elf, o + 0x10, off)
        struct.pack_into("<I", elf, o + 0x14, sz)
        struct.pack_into("<I", elf, o + 0x18, link)
        struct.pack_into("<I", elf, o + 0x1C, info)
        struct.pack_into("<I", elf, o + 0x20, align)
        struct.pack_into("<I", elf, o + 0x24, entsize)

    _sh(0, 0, 0, 0, 0, 0, 0)
    for i, (vaddr, payload, is_code, name) in enumerate(segments):
        _sh(i + 1, name_offs[name], 1, (6 if is_code else 2),
            vaddr, offs[i], len(payload), align=32)
    _sh(NUM_SHDRS - 1, name_shstrtab, 3, 0, 0, shstr_off, len(shstr), align=1)
    return bytes(elf)


def validate_placements(chunks, per_chunk, synth) -> list[str]:
    """Check that no 4-byte window at a 16-bit instruction address matches a
    real 32-bit constructor word (masked by the p bit)."""
    real32 = set()
    for base, insns in per_chunk.items():
        for i in insns:
            if i.width == 32:
                real32.add(i.word & ~1)
    problems = []
    for base, insns in per_chunk.items():
        data = (IMG / chunks[base]["bin"].name).read_bytes()
        for i in insns:
            if i.width != 16:
                continue
            off = i.addr - base
            if off + 4 > len(data):
                continue
            v = struct.unpack_from("<I", data, off)[0] & ~1
            if v in real32:
                problems.append(f"{i.addr:08x} window 0x{v:08x} collides")
    return problems


def validate_headers(chunks, per_chunk, headers) -> list[str]:
    """A 16-bit instruction window must never equal a real header word."""
    header_words = {w for _a, w in headers}
    problems = []
    for base, insns in per_chunk.items():
        data = (IMG / chunks[base]["bin"].name).read_bytes()
        for i in insns:
            if i.width != 16:
                continue
            off = i.addr - base
            if off + 4 > len(data):
                continue
            v = struct.unpack_from("<I", data, off)[0]
            if v in header_words:
                problems.append(f"{i.addr:08x} window 0x{v:08x} equals a real header")
    return problems


def main() -> int:
    LANG.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    chunks = chunk_map()
    per_chunk = load_insns(chunks)
    all_insns = [i for v in per_chunk.values() for i in v]
    synth = assign_synthetic16(all_insns)
    constructors, names = build_constructors(all_insns, synth)
    headers = collect_headers(chunks)
    hprob = validate_headers(chunks, per_chunk, headers)
    gap_words = collect_gap_words(chunks, per_chunk)
    with open(IMG / "insn_map.txt", "w", encoding="utf-8") as fh:
        for i in sorted(all_insns, key=lambda x: x.addr):
            fh.write(f"{i.addr:08x} {i.width}\n")
        for t, _w in sorted(gap_words):
            fh.write(f"{t:08x} 4\n")
    (LANG / "TMS320C6000.slaspec").write_text(
        emit_slaspec(constructors, names, headers, gap_words), encoding="utf-8"
    )
    (LANG / "TMS320C6000.ldefs").write_text(emit_ldefs(), encoding="utf-8")
    (LANG / "TMS320C6000.pspec").write_text(emit_pspec(), encoding="utf-8")
    (LANG / "TMS320C6000.cspec").write_text(emit_cspec(), encoding="utf-8")
    patch_images(chunks, per_chunk, synth)
    problems = validate_placements(chunks, per_chunk, synth)
    manifest = json.loads((IMG / "manifest.json").read_text(encoding="utf-8"))
    segments = []
    for entry in manifest:
        seg = (
            int(entry["base"], 16),
            (IMG / entry["file"]).read_bytes(),
            bool(entry["code"]),
            entry["file"].replace("chunk_", "").replace(".bin", ""),
        )
        segments.append(seg)
    (IMG / "fw_b1on_all.out").write_bytes(wrap_elf_multi(segments))
    print(f"chunks: {len(chunks)}  code chunks: {sum(1 for c in chunks.values() if c['is_code'])}")
    print(f"instructions: {len(all_insns)}  "
          f"32-bit: {sum(1 for i in all_insns if i.width == 32)}  "
          f"16-bit: {sum(1 for i in all_insns if i.width == 16)}")
    print(f"constructors: {len(constructors)}  synthetic 16-bit patterns: {len(synth)}")
    print(f"placement collisions: {len(problems)}")
    print(f"fetch-packet headers: {len(headers)}  header collisions: {len(hprob)}")
    for p in hprob[:10]:
        print("  ", p)
    print(f"combined image: {IMG / 'fw_b1on_all.out'}")
    for p in problems[:10]:
        print("  ", p)
    return 0


def collect_gap_words(chunks, per_chunk) -> list[tuple[int, int]]:
    """Branch targets inside code that decode to no instruction (data words).

    Return (address, word) pairs; the sleigh gets exact NOP constructors so
    the decompiler can pass through these rare mid-code data spots.
    """
    insn_addrs = {i.addr for v in per_chunk.values() for i in v}
    targets = set()
    for v in per_chunk.values():
        for i in v:
            if i.mnem in ("B", "BNOP", "BPOS", "BDEC", "CALLP") and i.ops:
                o = i.ops[0]
                if isinstance(o, Imm):
                    targets.add(o.value)
    out = []
    for base, info in chunks.items():
        if not info["is_code"]:
            continue
        data = info["bin"].read_bytes()
        lo, hi = base, base + info["size"]
        for t in targets:
            if lo <= t < hi and t not in insn_addrs:
                off = t - base
                w = struct.unpack_from("<I", data, off)[0]
                out.append((t, w))
    return out


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Parse GNU binutils TIC6X instruction tables into Python data structures.

Sources (from a binutils source tree):
  include/opcode/tic6x-insn-formats.h   -- instruction bit-field formats
  include/opcode/tic6x-opcode-table.h   -- opcode entries

The parser mirrors the C preprocessor macros used by the headers, so the
decoded bit layouts are byte-for-byte identical to binutils' tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# --------------------------------------------------------------------------
# Format header parsing
# --------------------------------------------------------------------------

_FLD_RE = re.compile(r"FLD\(\s*([a-zA-Z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_BFLD_RE = re.compile(r"BFLD\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_COMPFLD_RE = re.compile(
    r"COMPFLD\(\s*([a-zA-Z0-9_]+)\s*,\s*BFLD\d+\((.*)\)\s*\)\s*$",
    re.DOTALL,
)


def _parse_cflds(m: re.Match[str]) -> list[str]:
    """Expand CFLDSn(...) into individual FLD() macro texts."""
    args = m.group(2)
    n = int(m.group(1))
    parts = _split_args(args)
    assert len(parts) == n, (m.group(0), parts)
    return parts


def _split_args(s: str) -> list[str]:
    """Split a comma separated macro arg list at top nesting level."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


@dataclass
class BitField:
    low_pos: int
    width: int
    pos: int  # shift applied when extracting a composite value


@dataclass
class InsnField:
    name: str
    bits: list[BitField]

    def extract(self, word: int) -> int:
        v = 0
        for b in self.bits:
            v |= ((word >> b.low_pos) & ((1 << b.width) - 1)) << b.pos
        return v

    def mask(self) -> int:
        m = 0
        for b in self.bits:
            m |= ((1 << b.width) - 1) << b.low_pos
        return m


@dataclass
class InsnFormat:
    name: str
    num_bits: int
    cst_bits: int
    mask: int
    fields: dict[str, InsnField]


def parse_insn_formats(text: str) -> dict[str, InsnFormat]:
    formats: dict[str, InsnFormat] = {}
    for _callee, body in _extract_calls(text, "FMT"):
        args = _split_args(body)
        if len(args) < 5:
            continue
        name, nbits, cst_s, mask_s, fields_s = args[:5]
        cst = _eval_fmt_const(cst_s)
        mask = _eval_fmt_const(mask_s)
        fields: dict[str, InsnField] = {}
        # Expand the field macro list: CFLDSn/NFLDSn/SFLDSn/FLDSn
        fbody = fields_s.strip()
        fm = re.match(r"^(C|N|S|)FLDS(\d+)\((.*)\)$", fbody, re.DOTALL)
        if fm:
            kind, n, args = fm.groups()
            n = int(n)
            parts = _split_args(args)
            assert len(parts) == n, (name, fbody, parts)
            entries: list[str] = []
            if kind in ("C", ""):
                # CFLDS: p, creg, z  -- for 32-bit conditional formats
                entries = ["FLD(p,0,1)", "FLD(creg,29,3)", "FLD(z,28,1)"]
            elif kind == "N":
                entries = ["FLD(p,0,1)"]
            elif kind == "S":
                entries = ["FLD(s,0,1)"]
            entries += parts
        else:
            m2 = re.match(r"^FLDS(\d+)\((.*)\)$", fbody, re.DOTALL)
            assert m2, (name, fbody)
            entries = _split_args(m2.group(2))
        for e in entries:
            e = e.strip()
            cm = _COMPFLD_RE.match(e)
            if cm:
                fname, bf_args_s = cm.groups()
                bf_parts = _split_args(bf_args_s)
                bitfields = []
                for bp in bf_parts:
                    bm = _BFLD_RE.match(bp.strip())
                    assert bm, (name, bp)
                    low, width, pos = (int(x) for x in bm.groups())
                    bitfields.append(BitField(low, width, pos))
                fields[fname] = InsnField(fname, bitfields)
                continue
            fm2 = _FLD_RE.match(e)
            assert fm2, (name, e)
            fname, pos, width = fm2.groups()
            pos, width = int(pos), int(width)
            fields[fname] = InsnField(fname, [BitField(pos, width, 0)])
        formats[name] = InsnFormat(name, int(nbits), cst, mask, fields)
    return formats


def _eval_fmt_const(s: str) -> int:
    """Evaluate simple C expressions like 0x40 or DSZ(4)|0x0004."""
    s = s.strip()
    # 16-bit helpers: SAT(a) -> bit? TIC6X_COMPACT_SAT_POS etc.
    def repl_sat(m: re.Match[str]) -> str:
        return f"(({m.group(1)}) & 1) << 14"

    def repl_br(m: re.Match[str]) -> str:
        return f"(({m.group(1)}) & 1) << 15"

    def repl_dsz(m: re.Match[str]) -> str:
        return f"(({m.group(1)}) & 7) << 16"

    s = re.sub(r"SAT\(([^)]+)\)", repl_sat, s)
    s = re.sub(r"BR\(([^)]+)\)", repl_br, s)
    s = re.sub(r"DSZ\(([^)]+)\)", repl_dsz, s)
    s = s.replace("|", " | ").replace("<<", " << ")
    return int(eval(s, {"__builtins__": {}}, {}))  # noqa: S307 -- controlled input


# --------------------------------------------------------------------------
# Opcode table parsing
# --------------------------------------------------------------------------

_OP_MACRO_RE = re.compile(
    r"O(?P<rw>[RW])(?P<kind>[A-Z0-9_]+?)(?P<num>\d*)"
)

_OP_TABLE = {
    "WREG1": "reg",
    "WREG1Z": "zreg",
    "WREG1NORS": "reg_nors",
    "WREG2": "reg2",
    "WREG4": "reg4",
    "WREG9": "reg9",
    "RREG1": "reg",
    "RREG1B": "reg_bside",
    "RREG1BNORS": "reg_bside_nors",
    "RDREG1": "dreg",
    "RTREG1": "treg",
    "RWREG1": "reg",
    "RB15REG1": "b15reg",
    "WB15REG1": "b15reg",
    "RAREG1": "areg",
    "RXREG1": "xreg",
    "RREG12": "reg12",
    "RREG14": "reg14",
    "RXREG14": "xreg14",
    "DREG5": "dreg5",
    "TREG5": "treg5",
    "REGL1": "regpair",
    "REGD1": "regpair_d",
    "REGD12": "regpair_d12",
    "REGD4": "regpair_d4",
    "REGD45": "regpair_d45",
    "REGD67": "regpair_d67",
    "DREGD1": "dregpair",
    "TREGD1": "tregpair",
    "DREGD5": "dregpair5",
    "TREGD5": "tregpair5",
    "REGD1234": "regpair_d1234",
    "XREGD1324": "xregpair_d1324",
    "REGD910": "regpair_d910",
    "CREG1": "ctrl",
    "ILC1": "ilc",
    "MEMDW": "mem_deref",
    "MEMSB": "mem_short",
    "MEMLB": "mem_long",
    "MEMSH": "mem_short",
    "MEMLH": "mem_long",
    "MEMSW": "mem_short",
    "MEMLW": "mem_long",
    "MEMSD": "mem_short",
    "MEMND": "mem_ndw",
    "ACST": "asm_const",
    "LCST": "link_const",
    "HWCSTM1": "hw_const_-1",
    "HWCST0": "hw_const_0",
    "HWCST1": "hw_const_1",
    "HWCST5": "hw_const_5",
    "HWCST16": "hw_const_16",
    "HWCST24": "hw_const_24",
    "HWCST31": "hw_const_31",
    "FULIST": "func_unit",
    "IRP1": "irp",
    "NRP1": "nrp",
    "RETREG1": "retreg",
    "XREGD12": "xregpair_d12",
}


@dataclass
class FixedField:
    field: str
    min_val: int
    max_val: int


@dataclass
class Operand:
    type: str
    size: int
    rw: str
    min_val: int
    max_val: int
    flag1: int
    flag2: int


@dataclass
class Encoding:
    field: str
    coding: str
    op_index: int


@dataclass
class OpcodeEntry:
    name: str
    variant: str | None
    unit: str
    format: str
    arch: set[str]
    flags: str
    fixed: list[FixedField]
    operands: list[Operand]
    encodings: list[Encoding]

    @property
    def key(self) -> tuple[str, str | None, str]:
        return (self.name, self.variant, self.unit)


def _parse_operands(s: str) -> list[Operand]:
    """Expand OPn(...) into operand list."""
    m = re.match(r"^OP(\d+)\((.*)\)$", s.strip())
    assert m, s
    n = int(m.group(1))
    parts = _split_args(m.group(2))
    assert len(parts) == n, (s, parts)
    ops = []
    for p in parts:
        p = p.strip()
        assert p.startswith("O"), p
        body = p[1:]
        # exact match first (longest key), then RW-prefixed
        cands = [
            k
            for k in _OP_TABLE
            if k == body
            or (len(body) >= 2 and body[1:] == k)
            or (len(k) >= 2 and k[1:] == body)
        ]
        if not cands:
            raise ValueError(f"unknown operand macro {p}")
        key = max(cands, key=len)
        t = _OP_TABLE[key]
        if t is None:
            raise ValueError(f"unknown operand macro {p}")
        ops.append(Operand(t, 0, "rw", 0, 0, 0, 0))
    return ops


def parse_opcode_table(text: str) -> list[OpcodeEntry]:
    entries: list[OpcodeEntry] = []
    for _callee, body in _extract_calls(text, "INSNE"):
        args = _split_args(body)
        # INSNE(name, variant, unit, format, pipeline, arch, flags, fixed, ops, enc)
        if len(args) == 10:
            (
                name,
                variant,
                unit,
                fmt,
                pipeline,
                arch,
                flags,
                fixed_s,
                ops_s,
                enc_s,
            ) = args
        else:
            continue
        if "MACRO" in flags:
            continue
        fixed = _parse_fixed(fixed_s)
        operands = _parse_operands(ops_s)
        encodings = _parse_encodings(enc_s)
        archs = {a.strip() for a in arch.split("|") if a.strip()}
        entries.append(
            OpcodeEntry(
                name=name,
                variant=variant,
                unit=unit,
                format=fmt,
                arch=archs,
                flags=flags,
                fixed=fixed,
                operands=operands,
                encodings=encodings,
            )
        )
    for _callee, body in _extract_calls(text, "INSN"):
        args = _split_args(body)
        # INSN(name, unit, format, pipeline, arch, flags, fixed, ops, enc)
        if len(args) != 9:
            continue
        (
            name,
            unit,
            fmt,
            pipeline,
            arch,
            flags,
            fixed_s,
            ops_s,
            enc_s,
        ) = args
        if "MACRO" in flags:
            continue
        fixed = _parse_fixed(fixed_s)
        operands = _parse_operands(ops_s)
        encodings = _parse_encodings(enc_s)
        archs = {a.strip() for a in arch.split("|") if a.strip()}
        entries.append(
            OpcodeEntry(
                name=name,
                variant=None,
                unit=unit,
                format=fmt,
                arch=archs,
                flags=flags,
                fixed=fixed,
                operands=operands,
                encodings=encodings,
            )
        )
    return entries


def resolve_formats(
    entries: list[OpcodeEntry], formats: dict[str, InsnFormat]
) -> None:
    """Resolve bare format names in opcode entries to concrete FMT names.

    binutils entries name their format without the functional-unit prefix
    (e.g. ``1_or_2_src`` for ``l_1_or_2_src``).  The rule is
    ``<unit>_<bare>`` unless the bare name is already a format.
    """
    for e in entries:
        if e.format in formats:
            continue
        cand = f"{e.unit}_{e.format}"
        if cand not in formats:
            raise ValueError(f"cannot resolve format {e.format!r} for {e.name}/{e.unit}")
        e.format = cand


def _extract_calls(text: str, callee: str):
    """Yield (callee_name, args_text) for every balanced CALL(...) in text."""
    out = []
    start = 0
    while True:
        i = text.find(callee + "(", start)
        if i < 0:
            break
        j = i + len(callee) + 1
        depth = 1
        k = j
        while k < len(text) and depth:
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
            k += 1
        if depth == 0:
            out.append((text[i : i + len(callee)], text[j : k - 1]))
        start = k
    return out


def _parse_fixed(s: str) -> list[FixedField]:
    m = re.match(r"^FIX(\d+)\((.*)\)$", s.strip())
    if not m:
        return []
    parts = _split_args(m.group(2))
    out = []
    for p in parts:
        p = p.strip()
        fm = re.match(r"^FIX\(([a-zA-Z0-9_]+)\s*,\s*([^)]+)\)$", p)
        if fm:
            fname, val = fm.groups()
            out.append(FixedField(fname, int(val, 0), int(val, 0)))
            continue
        rm = re.match(r"^RAN\(([a-zA-Z0-9_]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\)$", p)
        if rm:
            fname, lo, hi = rm.groups()
            out.append(FixedField(fname, int(lo, 0), int(hi, 0)))
            continue
        raise ValueError(f"bad fixed field {p}")
    return out


def _parse_encodings(s: str) -> list[Encoding]:
    m = re.match(r"^ENC(\d+)\((.*)\)$", s.strip())
    if not m:
        return []
    parts = _split_args(m.group(2))
    out = []
    for p in parts:
        p = p.strip()
        em = re.match(r"^ENC\(([a-zA-Z0-9_]+)\s*,\s*([a-zA-Z0-9_]+)\s*,\s*(\d+)\)$", p)
        assert em, p
        fname, coding, opi = em.groups()
        out.append(Encoding(fname, coding, int(opi)))
    return out


def load_tables(insn_formats_path: Path, opcode_table_path: Path):
    fmt_text = insn_formats_path.read_text(encoding="utf-8", errors="replace")
    opc_text = opcode_table_path.read_text(encoding="utf-8", errors="replace")
    formats = parse_insn_formats(fmt_text)
    entries = parse_opcode_table(opc_text)
    resolve_formats(entries, formats)
    return formats, entries


def build_index(entries: list[OpcodeEntry]):
    """Index 32-bit opcode entries by (name, unit, variant)."""
    idx: dict[tuple, list[OpcodeEntry]] = {}
    for e in entries:
        if e.format not in FORMAT_CACHE:
            continue
        fmt = FORMAT_CACHE[e.format]
        if fmt.num_bits != 32:
            continue
        idx.setdefault((e.name, e.unit, e.variant), []).append(e)
    return idx


FORMAT_CACHE: dict[str, InsnFormat] = {}


def set_format_cache(formats: dict[str, InsnFormat]) -> None:
    global FORMAT_CACHE
    FORMAT_CACHE = formats


def decode_word(word: int, formats: dict[str, InsnFormat], entries: list[OpcodeEntry]):
    """Decode a 32-bit instruction word, mirroring binutils tic6x-dis.c."""
    for e in entries:
        fmt = formats.get(e.format)
        if fmt is None or fmt.num_bits != 32:
            continue
        if (word & fmt.mask) != fmt.cst_bits:
            continue
        creg = fmt.fields.get("creg")
        if creg is not None:
            z = fmt.fields.get("z")
            if z is None:
                continue
            cv = creg.extract(word)
            zv = z.extract(word)
            if not ((cv == 0 and zv == 0) or (1 <= cv <= 6 and zv <= 1)):
                continue
        ok = True
        for f in e.fixed:
            fld = fmt.fields.get(f.field)
            if fld is None:
                ok = False
                break
            v = fld.extract(word)
            if not (f.min_val <= v <= f.max_val):
                ok = False
                break
        if not ok:
            continue
        return e, fmt
    return None, None


if __name__ == "__main__":
    import sys

    base = Path(r"C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse\work\binutils-2.43\include\opcode")
    fmts, ents = load_tables(base / "tic6x-insn-formats.h", base / "tic6x-opcode-table.h")
    print(f"formats: {len(fmts)}  entries: {len(ents)}")
    n32 = sum(1 for e in ents if fmts.get(e.format) and fmts[e.format].num_bits == 32)
    print(f"32-bit entries: {n32}")
    for w in (0x0803E05A, 0x0020F07A, 0x008003A8, 0x4C1A0146):
        e, fmt = decode_word(w, fmts, ents)
        if e:
            print(f"{w:08X} -> {e.name} {e.variant or ''} unit={e.unit} fmt={e.format} arch={sorted(e.arch)}")
            for enc in e.encodings:
                fld = fmt.fields.get(enc.field)
                if fld:
                    print(f"    op{enc.op_index} {enc.field}={fld.extract(w):#x} ({enc.coding})")
        else:
            print(f"{w:08X} -> NO MATCH")

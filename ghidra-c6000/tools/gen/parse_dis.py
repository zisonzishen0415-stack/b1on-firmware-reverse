#!/usr/bin/env python3
"""Parse TI dis6x disassembly text into a structured instruction IR.

Handles the exact output dialect of dis6x from TI C6000 Code Generation
Tools 8.x: 16/32-bit mixed instructions, ``||`` / ``||^`` parallel markers,
predicates ``[A0]`` / ``[!B0]``, ``.fphead`` fetch-packet annotations,
registers, register pairs, immediates, control registers and the full
memory-operand addressing-mode set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


LINE_RE = re.compile(
    r"^([0-9a-f]{8})\s+([0-9a-f]+)\s+(\|\|)?\s*\^?\s*(.*?)\s*$",
    re.IGNORECASE,
)
PRED_RE = re.compile(r"^\[\s*(!?)([AB]\d+)\s*\]\s*(.*)$")
MEM_RE = re.compile(
    r"^\*(?:(?P<predec>--)|(?P<preinc>\+\+)|(?P<sign>[+-]))?"
    r"(?P<base>[AB]\d+)"
    r"(?:(?P<postdec>--)|(?P<postinc>\+\+))?"
    r"(?P<off>\[[^\]]*\]|\([^)]*\))?$"
)
REG_RE = re.compile(r"^([AB])(\d+)$")
REPAIR_RE = re.compile(r"^([AB]\d+):([AB]\d+)$")


@dataclass
class Reg:
    name: str  # e.g. "A0"


@dataclass
class RegPair:
    hi: str  # e.g. "A5"
    lo: str  # e.g. "A4"


@dataclass
class Imm:
    value: int
    raw: str


@dataclass
class CtrlReg:
    name: str


@dataclass
class Mem:
    mode: str  # pre_off / pre_off_neg / pre_inc / pre_dec / post_inc / post_dec / plain
    base: str
    offset: Reg | Imm | None


@dataclass
class Units:
    names: list[str]


Operand = Reg | RegPair | Imm | CtrlReg | Mem | Units


@dataclass
class Insn:
    addr: int
    width: int  # 16 or 32
    word: int  # raw instruction word (little-endian numeric value)
    parallel: bool  # `||` marker
    end_of_packet: bool  # `^` marker
    pred: Reg | None
    pred_neg: bool
    mnem: str  # base mnemonic, e.g. "MVK"
    unit: str  # "L" / "S" / "D" / "M" / "" (no functional unit)
    side: int  # 1 or 2
    cross: bool  # X cross-path suffix
    ops: list[Operand] = field(default_factory=list)
    raw: str = ""

    @property
    def unit_text(self) -> str:
        if not self.unit:
            return self.mnem
        s = f"{self.mnem}.{self.unit}{self.side}"
        if self.cross:
            s += "X"
        return s


def _parse_mem(s: str) -> Mem | None:
    m = MEM_RE.match(s)
    if not m:
        return None
    base = m.group("base")
    off_s = m.group("off")
    offset: Reg | Imm | None = None
    if off_s:
        inner = off_s[1:-1].strip()
        rm = REG_RE.match(inner)
        if rm:
            offset = Reg(inner)
        else:
            try:
                offset = Imm(int(inner, 0), inner)
            except ValueError:
                return None
    predec, preinc, sign = m.group("predec"), m.group("preinc"), m.group("sign")
    postdec, postinc = m.group("postdec"), m.group("postinc")
    if predec:
        mode = "pre_dec"
    elif preinc:
        mode = "pre_inc"
    elif postdec:
        mode = "post_dec"
    elif postinc:
        mode = "post_inc"
    elif sign == "+":
        mode = "pre_off"
    elif sign == "-":
        mode = "pre_off_neg"
    elif off_s:
        mode = "pre_off"  # *R[o] / *R(o) is base + offset without a plus sign
    else:
        mode = "plain"
    return Mem(mode, base, offset)


def _parse_operand(tok: str) -> Operand:
    if tok.startswith("*"):
        m = _parse_mem(tok)
        if m is None:
            raise ValueError(f"unparsed memory operand {tok!r}")
        return m
    if REG_RE.match(tok):
        return Reg(tok)
    if REPAIR_RE.match(tok):
        hi, lo = REPAIR_RE.match(tok).groups()
        return RegPair(hi, lo)
    if re.match(r"^0x[0-9a-f]+$", tok, re.I) or re.match(r"^-?\d+$", tok):
        return Imm(int(tok, 0), tok)
    if re.match(r"^[A-Z][A-Z0-9_]*$", tok):
        return CtrlReg(tok)
    raise ValueError(f"unparsed operand {tok!r}")


def _split_top(s: str) -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "[(":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return [o for o in out if o]


def parse_line(line: str) -> Insn | None:
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    addr_s, bytes_s, par, rest = m.groups()
    if not rest:
        return None
    if rest.startswith(".fphead") or rest.startswith("."):
        return None
    addr = int(addr_s, 16)
    width = len(bytes_s) * 4
    word = int(bytes_s, 16)
    pred: Reg | None = None
    pred_neg = False
    pm = PRED_RE.match(rest)
    if pm:
        pred_neg = bool(pm.group(1))
        pred = Reg(pm.group(2))
        rest = pm.group(3).strip()
    toks = rest.split(maxsplit=1)
    if not toks:
        return None
    mnem_full = toks[0]
    ops_s = toks[1] if len(toks) > 1 else ""
    # mnemonic forms: MVK.S1 / MV.L2X / CALLP.S2 / NOP / SPMASK
    mm = re.match(r"^([A-Z0-9_]+)\.([A-Z])(\d)(X?)(T\d)?$", mnem_full)
    if mm:
        mnem, unit, side_s, cross_s, _tpath = mm.groups()
        unit, side, cross = unit, int(side_s), bool(cross_s)
    else:
        mnem = mnem_full
        unit, side, cross = "", 0, False
    ops: list[Operand] = []
    for t in _split_top(ops_s):
        if mnem == "SPMASK" or mnem == "SPMASKR":
            ops.append(Units([x for x in t.split(",") if x.strip()]))
        else:
            ops.append(_parse_operand(t))
    return Insn(
        addr=addr,
        width=width,
        word=word,
        parallel=bool(par),
        end_of_packet="^" in rest,
        pred=pred,
        pred_neg=pred_neg,
        mnem=mnem.upper(),
        unit=unit,
        side=side,
        cross=cross,
        ops=ops,
        raw=line.strip(),
    )


def parse_dis(path: Path) -> list[Insn]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        insn = parse_line(line)
        if insn is not None:
            out.append(insn)
    return out


def load_corpus(paths: list[Path]) -> list[Insn]:
    all_insns: list[Insn] = []
    for p in paths:
        if p.is_dir():
            all_insns.extend(parse_dis(f) for f in sorted(p.glob("*.dis")))
        else:
            all_insns.extend(parse_dis(p))
    return all_insns


if __name__ == "__main__":
    import glob
    import collections

    files = [Path(f) for f in glob.glob(r"C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse\analysis\b1on_os\*.dis")]
    insns = []
    for f in files:
        insns.extend(parse_dis(f))
    print("parsed:", len(insns))
    bad = [i for i in insns if not i.ops and i.mnem not in ("NOP", "SPKERNEL", "DINT", "SWE", "SWENR", "RINT")]
    bad2 = collections.Counter((i.mnem, i.unit_text, i.raw) for i in insns if not i.ops)
    print("opless non-NOP:", len(bad))
    for k, n in list(bad2.most_common(20)):
        print(n, k)
    print("distinct mnemonics:", len(set(i.mnem for i in insns)))

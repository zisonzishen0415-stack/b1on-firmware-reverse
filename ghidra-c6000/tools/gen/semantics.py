#!/usr/bin/env python3
"""Translate parsed C6000 instructions into Sleigh p-code.

Operands are hard-coded into each constructor (one constructor per distinct
instruction word), which keeps the p-code simple and unambiguous.  The
semantic model is tuned for decompiler quality rather than cycle accuracy:
saturating/SIMD variants are approximated with their plain scalar or lane
equivalents and documented below.
"""

from __future__ import annotations

import re

from parse_dis import CtrlReg, Imm, Insn, Mem, Reg, RegPair, Units


def _reg(i: Reg | str) -> str:
    if isinstance(i, Reg):
        return i.name
    if isinstance(i, Imm):
        return str(i.value)
    if isinstance(i, RegPair):
        return f"{i.hi}:{i.lo}"
    if isinstance(i, CtrlReg):
        return i.name
    return str(i)


def _imm(i: Imm | int) -> int:
    return i.value if isinstance(i, Imm) else i


def _pair(rp: RegPair) -> str:
    return f"{rp.hi}:{rp.lo}"


def _pair_lo_hi(rp: RegPair) -> tuple[str, str]:
    """(low word register, high word register) for a TI register pair."""
    return rp.lo, rp.hi


def _pair_local(rp: RegPair, tag: str) -> tuple[str, list[str]]:
    """Build a 64-bit local from a register pair: (local name, prelude)."""
    lo, hi = _pair_lo_hi(rp)
    pre = [f"local {tag}:8 = (zext({hi}) << 32) | zext({lo});"]
    return tag, pre


def _split_pair(rp: RegPair, expr64: str) -> list[str]:
    lo, hi = _pair_lo_hi(rp)
    tag = "sp_" + re.sub(r"[^A-Za-z0-9_]", "", expr64)
    return [
        f"local {tag}:8 = {expr64};",
        f"local {tag}h:8 = {tag} >> 32;",
        f"{lo} = {tag}:4;",
        f"{hi} = {tag}h:4;",
    ]


def _shift_src64(op, signed: bool) -> tuple[str, list[str]]:
    """64-bit shift source: pair -> local, single -> sign/zero extended."""
    if isinstance(op, RegPair):
        return _pair_local(op, "a")
    ext = "sext" if signed else "zext"
    return f"{ext}({_reg(op)})", []


def _sext_op(op, tag: str) -> tuple[str, list[str]]:
    """Sign-extend an operand to 64 bits; immediates need a sized local."""
    if isinstance(op, Imm):
        return f"sext(c{tag})", [f"local c{tag}:4 = {op.value};"]
    return f"sext({_reg(op)})", []


def _src64(op, tag: str) -> tuple[str, list[str]]:
    """Unsigned 64-bit source for pair-wide ADD/SUB/bitwise ops."""
    if isinstance(op, RegPair):
        return _pair_local(op, tag)
    if isinstance(op, Imm):
        return f"zext(c{tag})", [f"local c{tag}:4 = {op.value};"]
    return f"zext({_reg(op)})", []


def _cond(insn: Insn) -> str:
    if insn.pred is None:
        return ""
    r = _reg(insn.pred)
    return f"{r} == 0" if insn.pred_neg else f"{r} != 0"


def _mem_addr(m: Mem) -> tuple[str, list[str]]:
    """Return (address expression, prelude p-code for writeback)."""
    base = _reg(m.base)
    off = m.offset
    off_s = "0"
    if isinstance(off, Reg):
        off_s = _reg(off)
    elif isinstance(off, Imm):
        off_s = str(off.value)
    prelude: list[str] = []
    if m.mode == "pre_off":
        if off_s == "0":
            return base, prelude
        return f"({base} + {off_s})", prelude
    if m.mode == "pre_off_neg":
        return f"({base} - {off_s})", prelude
    if m.mode == "pre_inc":
        prelude.append(f"{base} = {base} + {off_s};")
        return base, prelude
    if m.mode == "pre_dec":
        prelude.append(f"{base} = {base} - {off_s};")
        return base, prelude
    if m.mode == "post_inc":
        prelude.append(f"{base} = {base} + {off_s};")
        return base, prelude
    if m.mode == "post_dec":
        prelude.append(f"{base} = {base} - {off_s};")
        return base, prelude
    return base, prelude


def _load(insn: Insn, mem: Mem, dst: str) -> list[str]:
    addr, pre = _mem_addr(mem)
    size = {
        "LDB": 1, "LDBU": 1, "LDH": 2, "LDHU": 2,
        "LDW": 4, "LDNW": 4, "LDDW": 8, "LDNDW": 8,
    }[insn.mnem]
    if size == 8:
        lo, hi = _pair_lo_hi(dst)
        return pre + [f"{lo} = *[ram]{addr};", f"{hi} = *[ram]({addr} + 4);"]
    if size == 4:
        return pre + [f"{_reg(dst)} = *[ram]{addr};"]
    ext = "zext" if insn.mnem.endswith("U") else "sext"
    return pre + [f"local t:{size} = *[ram]{addr};", f"{_reg(dst)} = {ext}(t);"]


def _store(insn: Insn, mem: Mem, src: str) -> list[str]:
    addr, pre = _mem_addr(mem)
    size = {
        "STB": 1, "STH": 2, "STW": 4, "STNW": 4,
        "STDW": 8, "STNDW": 8,
    }[insn.mnem]
    if size == 8:
        lo, hi = _pair_lo_hi(src)
        return pre + [f"*[ram]{addr} = {lo};", f"*[ram]({addr} + 4) = {hi};"]
    if size == 4:
        return pre + [f"*[ram]{addr} = {_reg(src)};"]
    return pre + [f"local t:{size} = {_reg(src)}:{size};", f"*[ram]{addr} = t;"]


def _half_sext(src: str, high: bool, tag: str = "") -> list[str]:
    if high:
        return [
            f"local s{tag}:4 = {src} >> 16;",
            f"local x{tag}:2 = s{tag}:2;",
            f"local v{tag}:4 = sext(x{tag});",
        ]
    return [f"local x{tag}:2 = {src}:2;", f"local v{tag}:4 = sext(x{tag});"]


def _half_zext(src: str, high: bool, tag: str = "") -> list[str]:
    if high:
        return [
            f"local s{tag}:4 = {src} >> 16;",
            f"local x{tag}:2 = s{tag}:2;",
            f"local v{tag}:4 = zext(x{tag});",
        ]
    return [f"local x{tag}:2 = {src}:2;", f"local v{tag}:4 = zext(x{tag});"]


def _mul16(
    a: str, b: str, ahi: bool, bhi: bool, asigned: bool, bsigned: bool, tag: str = "m"
) -> list[str]:
    ha = _half_sext(a, ahi, tag + "a") if asigned else _half_zext(a, ahi, tag + "a")
    hb = _half_sext(b, bhi, tag + "b") if bsigned else _half_zext(b, bhi, tag + "b")
    return ha + hb + [f"local {tag}:4 = v{tag}a * v{tag}b;"]


def _select(dst: str, cond: str, a: str, b: str) -> list[str]:
    return [
        f"if ({cond}) goto <lbl0>;",
        f"{dst} = {b};",
        f"goto <lbl1>;",
        f"<lbl0>",
        f"{dst} = {a};",
        f"<lbl1>",
    ]


def emit_pcode(insn: Insn) -> list[str]:
    m = insn.mnem
    ops = insn.ops
    body: list[str] = []

    def r0() -> str:
        return _reg(ops[0])

    def r1() -> str:
        return _reg(ops[1])

    def r2() -> str:
        return _reg(ops[2])

    def v0() -> int:
        return _imm(ops[0])

    def v1() -> int:
        return _imm(ops[1])

    # ---- branches / calls / returns -------------------------------------
    if m in ("B", "BNOP", "BPOS", "BDEC"):
        target = ops[0]
        cond = _cond(insn)
        if m == "BPOS":
            body = [f"if ({r1()} s>= 0) goto 0x{_imm(target):08x};"]
        elif m == "BDEC":
            body = [
                f"{r1()} = {r1()} - 1;",
                f"if ({r1()} s>= 0) goto 0x{_imm(target):08x};",
            ]
        elif isinstance(target, Reg):
            if target.name == "B3":
                body = [f"return [{r0()}];"]
            else:
                body = [f"goto [{r0()}];"]
        elif isinstance(target, CtrlReg):
            if target.name in ("IRP", "NRP"):
                body = [f"return [{target.name}];"]
            else:
                body = [f"goto [{target.name}];"]
        else:
            body = [f"goto 0x{_imm(target):08x};"]
        if cond and m not in ("BPOS", "BDEC"):
            body = [f"if ({cond}) goto <lbl2>;", "goto <lbl3>;", "<lbl2>", *body, "<lbl3>"]
        return body
    if m == "CALLP":
        retreg = _reg(ops[1])
        target = _imm(ops[0])
        return [f"{retreg} = inst_next;", f"call 0x{target:08x};"]

    # ---- NOP / system / loop scaffolding ---------------------------------
    if m in ("NOP", "DINT", "RINT", "SWE", "SWENR", "SWI", "DDBG", "PLD",
             "SPLOOP", "SPLOOPD", "SPLOOPW", "SPKERNEL", "SPMASK", "SPMASKR"):
        return []

    # ---- moves / constants ------------------------------------------------
    if m == "MV":
        if isinstance(ops[0], RegPair) or isinstance(ops[1], RegPair):
            if isinstance(ops[0], RegPair):
                s_lo, s_hi = _pair_lo_hi(ops[0])
            else:
                s_lo = s_hi = _reg(ops[0])
            if isinstance(ops[1], RegPair):
                d_lo, d_hi = _pair_lo_hi(ops[1])
            else:
                d_lo, d_hi = _reg(ops[1]), _reg(ops[1])
            body = [f"{d_lo} = {s_lo};", f"{d_hi} = {s_hi};"]
        else:
            body = [f"{r1()} = {r0()};"]
    elif m == "MVD":
        body = [f"{r1()} = {r0()};"]
    elif m == "DMV":
        lo, hi = _pair_lo_hi(ops[2])
        body = [f"{lo} = {r0()};", f"{hi} = {r1()};"]
    elif m == "MVK":
        body = [f"{r1()} = {v0()};"]
    elif m == "MVKH":
        body = [f"{r1()} = ({r1()} & 0xffff) | ({v0()} << 16);"]
    elif m == "ZERO":
        if isinstance(ops[0], RegPair):
            lo, hi = _pair_lo_hi(ops[0])
            body = [f"{lo} = 0;", f"{hi} = 0;"]
        else:
            body = [f"{r0()} = 0;"]
    elif m == "NEG":
        body = [f"{r1()} = -{r0()};"]
    elif m == "NOT":
        body = [f"{r1()} = ~{r0()};"]
    elif m == "ABS":
        if isinstance(ops[0], RegPair):
            a, pre_a = _pair_local(ops[0], "a")
            sel = [
                f"local r:8 = {a};",
                f"if ({a} s< 0) goto <lbl0>;",
                f"goto <lbl1>;",
                f"<lbl0>",
                f"r = -{a};",
                f"<lbl1>",
            ]
            if isinstance(ops[1], RegPair):
                body = pre_a + sel + _split_pair(ops[1], "r")
            else:
                body = pre_a + sel + [f"{r1()} = r:4;"]
        else:
            body = _select(r1(), f"{r0()} s< 0", f"-{r0()}", r0())
    elif m == "ABSSP":
        body = [f"{r1()} = abs({r0()});"]

    # ---- integer ALU ------------------------------------------------------
    elif m in ("ADD", "ADDU", "SADD", "SADD2", "SADDUS2", "SADDU4", "ADD4"):
        if isinstance(ops[1], Imm):
            if isinstance(ops[2], RegPair):
                a, pa = _src64(ops[0], "a")
                body = pa + [f"local _s:8 = {a} + {v1()};"] + _split_pair(ops[2], "_s")
            else:
                body = [f"{r2()} = {r0()} + {v1()};"]
        elif isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} + {b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} + {r1()};"]
    elif m in ("SUB", "SUBU", "SSUB", "SUB4"):
        if isinstance(ops[1], Imm):
            if isinstance(ops[2], RegPair):
                a, pa = _src64(ops[0], "a")
                body = pa + [f"local _s:8 = {a} - {v1()};"] + _split_pair(ops[2], "_s")
            else:
                body = [f"{r2()} = {r0()} - {v1()};"]
        elif isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} - {b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} - {r1()};"]
    elif m == "ADD2":
        body = [
            f"local t0:4 = ({r0()} & 0xffff) + ({r1()} & 0xffff);",
            f"local t1:4 = (({r0()} >> 16) & 0xffff) + (({r1()} >> 16) & 0xffff);",
            f"{r2()} = (t0 & 0xffff) | ((t1 & 0xffff) << 16);",
        ]
    elif m == "SUB2":
        body = [
            f"local t0:4 = ({r0()} & 0xffff) - ({r1()} & 0xffff);",
            f"local t1:4 = (({r0()} >> 16) & 0xffff) - (({r1()} >> 16) & 0xffff);",
            f"{r2()} = (t0 & 0xffff) | ((t1 & 0xffff) << 16);",
        ]
    elif m == "AND":
        if isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} & {b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} & {r1()};"]
    elif m == "ANDN":
        if isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} & ~{b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} & ~{r1()};"]
    elif m == "OR":
        if isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} | {b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} | {r1()};"]
    elif m == "XOR":
        if isinstance(ops[2], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"local _s:8 = {a} ^ {b};"] + _split_pair(ops[2], "_s")
        else:
            body = [f"{r2()} = {r0()} ^ {r1()};"]
    elif m == "SHL":
        if isinstance(ops[2], RegPair):
            a, pre_a = _shift_src64(ops[0], True)
            body = pre_a + [f"local p:8 = {a} << {v1() if isinstance(ops[1], Imm) else r1()};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} << {v1() if isinstance(ops[1], Imm) else r1()};"]
    elif m == "SSHL":
        if isinstance(ops[2], RegPair):
            a, pre_a = _shift_src64(ops[0], True)
            body = pre_a + [f"local p:8 = {a} << {v1() if isinstance(ops[1], Imm) else r1()};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} << {v1() if isinstance(ops[1], Imm) else r1()};"]
    elif m == "SHR":
        if isinstance(ops[2], RegPair):
            a, pre_a = _shift_src64(ops[0], True)
            body = pre_a + [f"local p:8 = {a} s>> {v1() if isinstance(ops[1], Imm) else r1()};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} s>> {v1() if isinstance(ops[1], Imm) else r1()};"]
    elif m == "SHRU":
        if isinstance(ops[2], RegPair):
            a, pre_a = _shift_src64(ops[0], False)
            body = pre_a + [f"local p:8 = {a} >> {v1() if isinstance(ops[1], Imm) else r1()};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} >> {v1() if isinstance(ops[1], Imm) else r1()};"]
    elif m in ("SHR2", "SHRU2"):
        n = v1() if isinstance(ops[1], Imm) else _reg(ops[1])
        body = [f"{r2()} = {r0()} >> {n};"]
    elif m == "ROTL":
        n = v1() if isinstance(ops[1], Imm) else _reg(ops[1])
        body = [f"{r2()} = ({r0()} << {n}) | ({r0()} >> (32 - {n}));"]
    elif m == "SET":
        a, b = (str(o.value) if isinstance(o, Imm) else _reg(o) for o in (ops[1], ops[2]))
        d = _reg(ops[3]) if len(ops) >= 4 else r2()
        body = [
            f"local msk:4 = ((1 << ({b} - {a} + 1)) - 1) << {a};",
            f"{d} = {r0()} | msk;",
        ]
    elif m == "CLR":
        a, b = (str(o.value) if isinstance(o, Imm) else _reg(o) for o in (ops[1], ops[2]))
        d = _reg(ops[3]) if len(ops) >= 4 else r2()
        body = [
            f"local msk:4 = ((1 << ({b} - {a} + 1)) - 1) << {a};",
            f"{d} = {r0()} & ~msk;",
        ]
    elif m == "EXTU":
        a, b = (str(o.value) if isinstance(o, Imm) else _reg(o) for o in (ops[1], ops[2]))
        d = _reg(ops[3]) if len(ops) >= 4 else r2()
        body = [
            f"local msk:4 = (1 << ({b} - {a} + 1)) - 1;",
            f"{d} = ({r0()} >> {a}) & msk;",
        ]
    elif m == "EXT":
        a, b = (str(o.value) if isinstance(o, Imm) else _reg(o) for o in (ops[1], ops[2]))
        d = _reg(ops[3]) if len(ops) >= 4 else r2()
        body = [
            f"local sh:4 = 31 - {b};",
            f"local t:4 = ({r0()} << sh);",
            f"{d} = t s>> (sh + {a});",
        ]
    elif m in ("ADDK",):
        body = [f"{r1()} = {r1()} + {v0()};"]
    elif m == "ADDKPC":
        body = [f"{r1()} = inst_start + {v0()};"]
    elif m in ("ADDAW", "SUBAW"):
        op = "+" if m == "ADDAW" else "-"
        if isinstance(ops[1], Imm):
            body = [f"{r2()} = {r0()} {op} {v1() * 4};"]
        else:
            body = [f"{r2()} = {r0()} {op} ({r1()} << 2);"]
    elif m in ("ADDAH", "SUBAH"):
        op = "+" if m == "ADDAH" else "-"
        if isinstance(ops[1], Imm):
            body = [f"{r2()} = {r0()} {op} {v1() * 2};"]
        else:
            body = [f"{r2()} = {r0()} {op} ({r1()} << 1);"]
    elif m in ("ADDAB", "SUBAB"):
        op = "+" if m == "ADDAB" else "-"
        if isinstance(ops[1], Imm):
            body = [f"{r2()} = {r0()} {op} {v1()};"]
        else:
            body = [f"{r2()} = {r0()} {op} {r1()};"]
    elif m == "SAT":
        if isinstance(ops[0], RegPair):
            lo, _hi = _pair_lo_hi(ops[0])
            body = [f"{r1()} = {lo};"]
        else:
            body = [f"{r1()} = {r0()};"]
    elif m == "NORM":
        body = [f"{r1()} = lzcount({r0()} ^ ({r0()} s>> 31));"]
    elif m == "LMBD":
        val = _reg(ops[1]) if len(ops) >= 2 else r0()
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = lzcount({val});"]
    elif m in ("SSHVL", "SSHVR"):
        body = [f"{r2()} = {r0()} << {r1()};"] if m == "SSHVL" else [f"{r2()} = {r0()} s>> {r1()};"]
    elif m in ("MAX2", "MIN2"):
        op = "s>" if m == "MAX2" else "s<"
        body = _select(r2(), f"{r0()} {op} {r1()}", r0(), r1())
    elif m in ("MAXU4", "MINU4"):
        op = ">" if m == "MAXU4" else "<"
        body = _select(r2(), f"{r0()} {op} {r1()}", r0(), r1())

    # ---- comparisons -------------------------------------------------------
    elif m in ("CMPEQ", "CMPLT", "CMPGT", "CMPLTU", "CMPGTU"):
        opmap = {
            "CMPEQ": "==",
            "CMPLT": "s<",
            "CMPGT": "s>",
            "CMPLTU": "<",
            "CMPGTU": ">",
        }
        if isinstance(ops[0], RegPair) or isinstance(ops[1], RegPair):
            a, pa = _src64(ops[0], "a")
            b, pb = _src64(ops[1], "b")
            body = pa + pb + [f"{r2()} = zext({a} {opmap[m]} {b});"]
        else:
            body = [f"{r2()} = zext({r0()} {opmap[m]} {r1()});"]
    elif m == "CMPEQ2":
        body = [
            f"local s0:4 = {r0()};",
            f"local s1:4 = {r1()};",
            f"local h0:4 = s0 >> 16;",
            f"local h1:4 = s1 >> 16;",
            f"local t0:4 = zext((s0:2) == (s1:2));",
            f"local t1:4 = zext((h0:2) == (h1:2));",
            f"{r2()} = t0 | (t1 << 16);",
        ]
    elif m in ("CMPEQ4", "CMPGT2", "CMPGTU4"):
        body = [f"{r2()} = zext({r0()} == {r1()});"] if m == "CMPEQ4" else [
            f"{r2()} = zext({r0()} s> {r1()});"
        ] if m == "CMPGT2" else [f"{r2()} = zext({r0()} > {r1()});"]

    # ---- multiplies --------------------------------------------------------
    elif m == "MPY":
        body = _mul16(r0(), r1(), False, False, True, True) + [f"{r2()} = m;"]
    elif m == "MPYU":
        body = _mul16(r0(), r1(), False, False, False, False) + [f"{r2()} = m;"]
    elif m == "MPYH":
        body = _mul16(r0(), r1(), True, True, True, True) + [f"{r2()} = m;"]
    elif m == "MPYHU":
        body = _mul16(r0(), r1(), True, True, False, False) + [f"{r2()} = m;"]
    elif m == "MPYHL":
        body = _mul16(r0(), r1(), True, False, True, True) + [f"{r2()} = m;"]
    elif m == "MPYLH":
        body = _mul16(r0(), r1(), False, True, True, True) + [f"{r2()} = m;"]
    elif m == "MPYHLU":
        body = _mul16(r0(), r1(), True, False, False, False) + [f"{r2()} = m;"]
    elif m == "MPYLHU":
        body = _mul16(r0(), r1(), False, True, False, False) + [f"{r2()} = m;"]
    elif m == "MPYHSU":
        body = _mul16(r0(), r1(), True, False, True, False) + [f"{r2()} = m;"]
    elif m == "MPYHUS":
        body = _mul16(r0(), r1(), True, False, False, True) + [f"{r2()} = m;"]
    elif m == "MPYHULS":
        body = _mul16(r0(), r1(), True, True, False, False) + [f"{r2()} = m;"]
    elif m == "MPYHSLU":
        body = _mul16(r0(), r1(), True, True, True, False) + [f"{r2()} = m;"]
    elif m == "MPYLUHS":
        body = _mul16(r0(), r1(), False, False, False, True) + [f"{r2()} = m;"]
    elif m == "MPYLSHU":
        body = _mul16(r0(), r1(), False, False, True, False) + [f"{r2()} = m;"]
    elif m == "MPYSU":
        body = _mul16(r0(), r1(), False, False, True, False) + [f"{r2()} = m;"]
    elif m == "MPYUS":
        body = _mul16(r0(), r1(), False, False, False, True) + [f"{r2()} = m;"]
    elif m == "MPY2":
        body = (
            _mul16(r0(), r1(), False, False, True, True, "m0")
            + _mul16(r0(), r1(), True, True, True, True, "m1")
        )
        packed = "(m0 & 0xffff) | ((m1 & 0xffff) << 16)"
        if isinstance(ops[2], RegPair):
            lo, hi = _pair_lo_hi(ops[2])
            body += [f"{lo} = {packed};", f"{hi} = 0;"]
        else:
            body += [f"{r2()} = {packed};"]
    elif m in ("SMPY", "SMPYH", "SMPYHL", "SMPYLH"):
        if m == "SMPY":
            body = _mul16(r0(), r1(), False, False, True, True)
        elif m == "SMPYH":
            body = _mul16(r0(), r1(), True, True, True, True)
        elif m == "SMPYHL":
            body = _mul16(r0(), r1(), True, False, True, True)
        else:
            body = _mul16(r0(), r1(), False, True, True, True)
        body += [f"{r2()} = m << 1;"]
    elif m == "SMPY32":
        body = [f"{r2()} = ({r0()} * {r1()}) << 1;"]
    elif m == "MPYI":
        if isinstance(ops[0], Imm):
            if isinstance(ops[2], RegPair):
                body = [f"local c:4 = {v0()};", f"local p:8 = sext(c) * sext({r1()});"] + _split_pair(ops[2], "p")
            else:
                body = [f"{r2()} = {v0()} * {r1()};"]
        else:
            if isinstance(ops[2], RegPair):
                body = [f"local p:8 = sext({r0()}) * sext({r1()});"] + _split_pair(ops[2], "p")
            else:
                body = [f"{r2()} = {r0()} * {r1()};"]
    elif m in ("MPYID", "MPY32", "MPYLI"):
        if isinstance(ops[2], RegPair):
            a, pa = _sext_op(ops[0], "a")
            b, pb = _sext_op(ops[1], "b")
            body = pa + pb + [f"local p:8 = {a} * {b};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} * {r1()};"]
    elif m == "MPY32U":
        if isinstance(ops[2], RegPair):
            body = [f"local p:8 = zext({_reg(ops[0])}) * zext({_reg(ops[1])});"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} * {r1()};"]
    elif m == "MPY32SU":
        if isinstance(ops[2], RegPair):
            a, pa = _sext_op(ops[0], "a")
            body = pa + [f"local p:8 = {a} * zext({_reg(ops[1])});"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} * {r1()};"]
    elif m == "MPY32US":
        if isinstance(ops[2], RegPair):
            b, pb = _sext_op(ops[1], "b")
            body = pb + [f"local p:8 = zext({_reg(ops[0])}) * {b};"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} * {r1()};"]
    elif m in ("MPYSP",):
        body = [f"{r1()} = {r0()} f* {r1()};"] if len(ops) == 2 else [f"{r2()} = {r0()} f* {r1()};"]
    elif m == "MPYDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"local p:8 = {a} f* {b};"] + _split_pair(ops[2], "p")
    elif m in ("MPYSPDP", "MPYSP2DP"):
        if isinstance(ops[1], RegPair):
            b, pre_b = _pair_local(ops[1], "b")
            body = pre_b + [f"local p:8 = float2float({r0()}) f* {b};"] + _split_pair(ops[2], "p")
        else:
            body = [f"local t:4 = {r0()} f* {r1()};", f"local p:8 = float2float(t);"] + _split_pair(ops[2], "p")
    elif m == "MPYSU4":
        body = _mul16(r0(), r1(), False, False, True, False)
        if isinstance(ops[2], RegPair):
            body += [f"local q:8 = zext(m);"] + _split_pair(ops[2], "q")
        else:
            body += [f"{r2()} = m;"]
    elif m in ("MPYUS4", "MPYU4", "MPYU4"):
        body = _mul16(r0(), r1(), False, False, False, False)
        if isinstance(ops[2], RegPair):
            body += [f"local q:8 = zext(m);"] + _split_pair(ops[2], "q")
        else:
            body += [f"{r2()} = m;"]
    elif m in ("GMPY", "GMPY4", "MPY2IR", "MPYHIR", "MPYHI", "MPYLIR"):
        if isinstance(ops[2], RegPair):
            body = [f"local p:8 = sext({r0()}) * sext({r1()});"] + _split_pair(ops[2], "p")
        else:
            body = [f"{r2()} = {r0()} * {r1()};"]
    elif m == "DOTP2":
        body = (
            _mul16(r0(), r1(), False, False, True, True, "m0")
            + _mul16(r0(), r1(), True, True, True, True, "m1")
        )
        if isinstance(ops[2], RegPair):
            lo, hi = _pair_lo_hi(ops[2])
            body += [f"{lo} = m0 + m1;", f"{hi} = 0;"]
        else:
            body += [f"{r2()} = m0 + m1;"]
    elif m == "DOTPN2":
        body = (
            _mul16(r0(), r1(), False, False, True, True, "m0")
            + _mul16(r0(), r1(), True, True, True, True, "m1")
        )
        if isinstance(ops[2], RegPair):
            lo, hi = _pair_lo_hi(ops[2])
            body += [f"{lo} = m0 - m1;", f"{hi} = 0;"]
        else:
            body += [f"{r2()} = m0 - m1;"]
    elif m in ("DOTPNRSU2", "DOTPRSU2", "DOTPSU4", "DOTPU4"):
        body = [f"{r2()} = {r0()} * {r1()};"]

    # ---- floating point ----------------------------------------------------
    elif m in ("ADDSP",):
        body = [f"{r2()} = {r0()} f+ {r1()};"]
    elif m == "SUBSP":
        body = [f"{r2()} = {r0()} f- {r1()};"]
    elif m == "ADDDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"local p:8 = {a} f+ {b};"] + _split_pair(ops[2], "p")
    elif m == "SUBDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"local p:8 = {a} f- {b};"] + _split_pair(ops[2], "p")
    elif m == "CMPEQSP":
        body = [f"{r2()} = zext({r0()} f== {r1()});"]
    elif m == "CMPLTSP":
        body = [f"{r2()} = zext({r0()} f< {r1()});"]
    elif m == "CMPGTSP":
        body = [f"{r2()} = zext({r0()} f> {r1()});"]
    elif m == "CMPEQDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"{r2()} = zext({a} f== {b});"]
    elif m == "CMPLTDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"{r2()} = zext({a} f< {b});"]
    elif m == "CMPGTDP":
        a, pre_a = _pair_local(ops[0], "a")
        b, pre_b = _pair_local(ops[1], "b")
        body = pre_a + pre_b + [f"{r2()} = zext({a} f> {b});"]
    elif m == "INTSP":
        body = [f"{r1()} = int2float({r0()});"]
    elif m == "SPINT":
        body = [f"{r1()} = trunc({r0()});"]
    elif m == "INTDP":
        body = [f"local f:4 = int2float({r0()});", f"local p:8 = float2float(f);"] + _split_pair(ops[1], "p")
    elif m == "INTDPU":
        body = [f"local f:4 = int2float({r0()});", f"local p:8 = float2float(f);"] + _split_pair(ops[1], "p")
    elif m == "INTSPU":
        body = [f"{r1()} = int2float({r0()});"]
    elif m == "SPDP":
        body = [f"local p:8 = float2float({r0()});"] + _split_pair(ops[1], "p")
    elif m == "DPSP":
        a, pre_a = _pair_local(ops[0], "a")
        body = pre_a + [f"{r1()} = float2float({a});"]
    elif m == "DPTRUNC":
        a, pre_a = _pair_local(ops[0], "a")
        body = pre_a + [f"{r1()} = trunc({a});"]
    elif m == "SPTRUNC":
        body = [f"{r1()} = trunc({r0()});"]
    elif m == "RCPSP":
        body = [f"local o:4 = int2float(1:4);", f"{r1()} = o f/ {r0()};"]
    elif m == "RCPDP":
        a, pre_a = _pair_local(ops[0], "a")
        body = pre_a + [f"local o:4 = int2float(1:4);", f"local one:8 = float2float(o);", f"local p:8 = one f/ {a};"] + _split_pair(ops[1], "p")
    elif m == "RSQRSP":
        body = [f"local o:4 = int2float(1:4);", f"{r1()} = o f/ sqrt({r0()});"]
    elif m == "RSQRDP":
        a, pre_a = _pair_local(ops[0], "a")
        body = pre_a + [f"local o:4 = int2float(1:4);", f"local one:8 = float2float(o);", f"local p:8 = one f/ sqrt({a});"] + _split_pair(ops[1], "p")
    elif m == "ABSDP":
        a, pre_a = _pair_local(ops[0], "a")
        body = pre_a + [f"local p:8 = abs({a});"] + _split_pair(ops[1], "p")

    # ---- loads / stores -----------------------------------------------------
    elif m in ("LDB", "LDBU", "LDH", "LDHU", "LDW", "LDNW", "LDDW", "LDNDW"):
        mem = ops[0]
        dst = ops[1]
        body = _load(insn, mem, dst)
    elif m in ("STB", "STH", "STW", "STNW", "STDW", "STNDW"):
        src = ops[0]
        mem = ops[1]
        body = _store(insn, mem, src)

    # ---- control registers ---------------------------------------------------
    elif m == "MVC":
        a, b = ops[0], ops[1]
        if isinstance(a, CtrlReg) and isinstance(b, Reg):
            body = [f"{_reg(b)} = {a.name};"]
        elif isinstance(a, Reg) and isinstance(b, CtrlReg):
            body = [f"{b.name} = {_reg(a)};"]
        else:
            body = []

    # ---- packing / misc SIMD -------------------------------------------------
    elif m == "PACK2":
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} & 0xffff) | ({r1()} << 16);"]
    elif m == "PACKH2":
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} & 0xffff0000) | (({r1()} >> 16) & 0xffff);"]
    elif m == "PACKL4":
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} & 0xff) | (({r1()} & 0xff) << 8) | (({r0()} & 0xff00) << 8) | (({r1()} & 0xff00) << 16);"]
    elif m in ("PACKHL2", "PACKLH2"):
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} & 0xffff0000) | ({r1()} & 0xffff);"]
    elif m in ("PACKH4",):
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} & 0xffff0000) | (({r1()} >> 16) & 0xffff);"]
    elif m == "SWAP2":
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = ({r0()} << 16) | (({r0()} >> 16) & 0xffff);"]
    elif m in ("SHLMB", "SHRMB"):
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = {r0()} << 8;" if m == "SHLMB" else f"{d} = {r0()} >> 8;"]
    elif m in ("SPACK2", "SPACKU4", "UNPKHU4", "UNPKLU4", "SPACKU4"):
        d = r2() if len(ops) >= 3 else r1()
        body = [f"{d} = {r0()};"]

    # ---- fallback: no-op with comment ----------------------------------------
    else:
        body = []  # unimplemented mnemonic; keeps decode flowing

    # ---- predicate wrapping for non-branch instructions ----------------------
    cond = _cond(insn)
    if cond and body and not any(s.startswith("return") or s.startswith("call") for s in body):
        body = [f"if ({cond}) goto <lbl4>;", "goto <lbl5>;", "<lbl4>", *body, "<lbl5>"]
    return body

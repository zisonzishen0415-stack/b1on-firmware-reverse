#!/usr/bin/env python3
"""Parser for the dis6x-style .dis text produced from the B1on firmware.

Builds an address-indexed instruction database and a call graph, so reverse
engineering questions like "who calls c0098b98" or "extract the function at
c00b6fe8" can be answered quickly and reproducibly.

Usage:
    python disdb.py path/to/file.dis <cmd> [args...]

Commands:
    callers <addr>            print every direct call/branch target of <addr>
    callees <addr>            print every target called/branched inside <addr>
    fn <addr>                 extract the function body starting at <addr>
    find <pattern>            print instructions whose text contains <pattern>
    graph <addr> [depth]      BFS call graph rooted at <addr>
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


LINE_RE = re.compile(
    r"^(?P<addr>[0-9a-f]{8})\s+(?P<bytes>[0-9a-f]*)\s*(?P<body>.*)$")
OP_RE = re.compile(
    r"(?P<cond>\[[!A-Z0-9]+\]\s*)?(?P<mn>[A-Z][A-Z0-9.]*)(?:\.(?P<unit>[A-Z0-9]+))?"
    r"(?P<rest>.*)$")


def parse(path: str) -> dict:
    """Return {addr: {"raw": line, "text": body, "mn": mnemonic, "rest": operands}}."""
    db: dict[str, dict] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        addr = m.group("addr")
        body = m.group("body").strip()
        om = OP_RE.match(body)
        mn = om.group("mn").upper() if om else ""
        db[addr] = {
            "raw": line,
            "text": body,
            "mn": mn,
            "rest": om.group("rest").strip() if om else "",
        }
    return db


def targets(db: dict, addr: str) -> list[str]:
    """Direct control-flow targets of the instruction at addr."""
    ins = db.get(addr)
    if not ins:
        return []
    t = []
    rest = ins["rest"]
    # CALLP.S2 0xc00c7560,B3   /  BNOP.S1 0xc0098c54,5   /  B.S2X  A3
    for pat in (r"0x([0-9a-f]{8})", r"([0-9a-f]{8})"):
        hits = re.findall(pat, rest, re.I)
        for h in hits:
            if h != addr:
                t.append(h.lower())
    return t


def is_return(ins: dict) -> bool:
    # parse() 的 mn 带单位后缀(如 "BNOP.S2"),先截断再比较。
    mn = ins["mn"].split(".")[0]
    return mn in ("BNOP", "B") and "B3" in ins["rest"] and "S2X" not in ins["rest"]


def extract_fn(db: dict, start: str, max_len: int = 4000) -> list[str]:
    """Best-effort linear function extraction: stops at a return or at an
    address already claimed by a preceding function."""
    out = []
    seen = set()
    stack = [(start, 0)]
    # Linear sweep with nested-call awareness is hard on text; do a simple
    # forward sweep that stops at the first unconditional return.
    addrs = sorted(db.keys(), key=lambda a: int(a, 16))
    try:
        i = addrs.index(start)
    except ValueError:
        return [f"address {start} not found"]
    depth = 0
    for addr in addrs[i:]:
        ins = db[addr]
        out.append(ins["raw"])
        if is_return(ins) and depth == 0:
            break
        if len(out) >= max_len:
            break
    return out


def build_edges(db: dict) -> tuple[set, dict]:
    edges = set()
    rev: dict = defaultdict(set)
    for addr, ins in db.items():
        for t in targets(db, addr):
            edges.add((addr, t))
            rev[t].add(addr)
    return edges, rev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dis", help=".dis file path")
    ap.add_argument("cmd", choices=["callers", "callees", "fn", "find", "graph"])
    ap.add_argument("args", nargs="*")
    args = ap.parse_args(sys.argv[1:])

    db = parse(args.dis)
    edges, rev = build_edges(db)

    if args.cmd == "find":
        pat = args.args[0].lower()
        hits = [ins["raw"] for a, ins in sorted(db.items(), key=lambda kv: int(kv[0], 16))
                if pat in ins["raw"].lower()]
        print("\n".join(hits) if hits else "no hits")
        return 0

    if args.cmd == "callers":
        addr = args.args[0].lower()
        callers = sorted(rev.get(addr, set()), key=lambda a: int(a, 16))
        if not callers:
            print(f"no direct callers of {addr}")
        for c in callers:
            print(c, db[c]["text"])
        return 0

    if args.cmd == "callees":
        addr = args.args[0].lower()
        body = extract_fn(db, addr)
        calls = set()
        for raw in body:
            a = raw.split()[0]
            for t in targets(db, a):
                if int(t, 16) >= int("c0078d20", 16):
                    calls.add((a, t))
        for a, t in sorted(calls, key=lambda x: int(x[0], 16)):
            print(f"{a} -> {t}  {db[a]['text']}")
        return 0

    if args.cmd == "fn":
        addr = args.args[0].lower()
        print("\n".join(extract_fn(db, addr)))
        return 0

    if args.cmd == "graph":
        root = args.args[0].lower()
        depth = int(args.args[1]) if len(args.args) > 1 else 2
        seen = {root}
        frontier = {root}
        for d in range(depth):
            nxt = set()
            for a in frontier:
                for t in edges:
                    if t[0] == a and t[1] not in seen and int(t[1], 16) >= int("c0078d20", 16):
                        nxt.add(t[1])
            if not nxt:
                break
            print(f"--- depth {d + 1} ---")
            for n in sorted(nxt, key=lambda x: int(x, 16)):
                print(n)
            seen |= nxt
            frontier = nxt
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

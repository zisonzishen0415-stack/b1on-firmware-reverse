#!/usr/bin/env python3
"""Validate our binutils-table decoder against dis6x output.

For every 32-bit instruction line in a .dis file, decode the printed word
with our tables and compare the resulting opcode name with the dis6x
mnemonic.  This is the ground-truth loop for the SLEIGH generator.
"""

from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tic6x_tables import load_tables, decode_word  # noqa: E402


LINE_RE = re.compile(
    r"^([0-9a-f]{8})\s+([0-9a-f]+)\s+(\|\|\s*)?(.+?)\s*$", re.IGNORECASE
)


def parse_dis(path: Path):
    insns = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        addr_s, bytes_s, _par, rest = m.groups()
        if rest.startswith(".fphead") or rest.startswith("."):
            continue
        addr = int(addr_s, 16)
        width = len(bytes_s) * 4
        word = int(bytes_s, 16)
        rest = re.sub(r"^\[[^]]*\]\s*", "", rest.strip())
        mnem = rest.split()[0]
        insns.append((addr, width, word, mnem))
    return insns


def main() -> int:
    base = Path(
        r"C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse\work\binutils-2.43\include\opcode"
    )
    fmts, ents = load_tables(base / "tic6x-insn-formats.h", base / "tic6x-opcode-table.h")
    files = sorted(
        glob.glob(r"C:\Users\29517\Documents\ChatGPT\b1on-firmware-reverse\analysis\b1on_os\*.dis")
    )
    if not files:
        print("no .dis files")
        return 1
    total = matched = 0
    mism = []
    no_match = 0
    seen_names: dict[str, int] = {}
    for fp in files:
        for addr, width, word, mnem in parse_dis(Path(fp)):
            if width != 32:
                continue
            total += 1
            seen_names[mnem.upper()] = seen_names.get(mnem.upper(), 0) + 1
            e, fmt = decode_word(word, fmts, ents)
            if e is None:
                no_match += 1
                if len(mism) < 40:
                    mism.append((addr, f"{word:08X}", mnem, "NO-MATCH"))
                continue
            base_mnem = mnem.split(".")[0]
            if e.name.upper() == base_mnem.upper():
                matched += 1
            else:
                if len(mism) < 40:
                    mism.append((addr, f"{word:08X}", mnem, f"{e.name}({e.unit})"))
    print(f"32-bit instructions checked: {total}")
    print(f"decoder name match: {matched} ({100.0 * matched / max(total, 1):.2f}%)")
    print(f"no match: {no_match}")
    print(f"distinct dis6x mnemonics seen: {len(seen_names)}")
    print("\nfirst mismatches:")
    for addr, w, mnem, got in mism[:30]:
        print(f"  {addr:08X} {w}  dis6x={mnem:12s} ours={got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

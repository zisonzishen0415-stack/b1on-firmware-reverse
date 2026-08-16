import re
import sys

def scan(path, label):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    stw_re = re.compile(r"^([0-9a-f]{8})\s+(.*STW\..*?)\*\+?([AB][0-9]+)\[(\d+)\]")
    bases = {}
    for ln in lines:
        m = stw_re.match(ln.strip())
        if not m:
            continue
        addr = int(m.group(1), 16)
        ins = m.group(2)
        reg = m.group(3)
        idx = int(m.group(4))
        bases.setdefault(reg, []).append((addr, ins, idx))
    hits = []
    for reg, arr in bases.items():
        arr.sort()
        for i in range(len(arr) - 2):
            a0, i0, x0 = arr[i]
            a1, i1, x1 = arr[i + 1]
            a2, i2, x2 = arr[i + 2]
            if (x0, x1, x2) in ((0, 1, 2), (3, 4, 5), (10, 11, 12), (1, 2, 3), (2, 3, 4)) and a1 - a0 < 80 and a2 - a1 < 80:
                hits.append((a0, reg, (x0, x1, x2), (i0, i1, i2)))
    print("== %s: %d triple candidates ==" % (label, len(hits)))
    for a, reg, idxs, instrs in hits[:150]:
        print("  %08x %s idx%s: %s | %s | %s" % (a, reg, idxs, instrs[0][:60], instrs[1][:60], instrs[2][:60]))

if __name__ == "__main__":
    scan(sys.argv[1], sys.argv[2])

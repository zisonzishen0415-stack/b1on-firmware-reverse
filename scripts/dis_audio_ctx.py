import struct
import sys
from capstone import Cs, CS_ARCH_ARM  # placeholder

def main(path):
    # use capstone C6000
    from capstone import Cs, CS_ARCH_TMS320C64X, CS_MODE_BIG_ENDIAN
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    e = data[i:]
    le = "<" if e[5] == 1 else ">"
    shoff = struct.unpack_from(le + "I", e, 0x20)[0]
    shentsize = struct.unpack_from(le + "H", e, 0x2E)[0]
    shnum = struct.unpack_from(le + "H", e, 0x30)[0]
    shstrndx = struct.unpack_from(le + "H", e, 0x32)[0]
    shdrs = []
    for n in range(shnum):
        off = shoff + n * shentsize
        shdrs.append(struct.unpack_from(le + "IIIIIIIIII", e, off))
    st_off, st_size = shdrs[shstrndx][4], shdrs[shstrndx][5]
    strtab = e[st_off : st_off + st_size]
    def sname(n):
        j = strtab.find(b"\x00", n)
        return strtab[n:j].decode("latin1")
    # find .audio or .text section containing the audio func (from descriptor audio field)
    # simpler: disassemble .audio if PROGBITS else .text
    md = Cs(CS_ARCH_TMS320C64X, CS_MODE_BIG_ENDIAN)
    md.detail = True
    for sh in shdrs:
        name = sname(sh[0])
        if name not in (".audio", ".text"):
            continue
        if sh[1] != 1 or sh[5] == 0:
            continue
        blob = e[sh[4] : sh[4] + sh[5]]
        print("== %s: %s addr=0x%x size=0x%x" % (path, name, sh[3], sh[5]))
        ctx_refs = set()
        for ins in md.disasm(blob, sh[3]):
            # collect A4[3],A4[5],A4[6],A4[11],A4[12], ctx-like accesses
            txt = ins.op_str
            for pat in ("A4[3]", "A4[5]", "A4[6]", "A4[11]", "A4[12]", "A21[3]", "A21[5]", "A21[6]", "A21[11]", "A21[12]"):
                if pat in txt:
                    ctx_refs.add(pat)
            if "A4[3]" in txt or "A21[3]" in txt:
                print("  %08x  %s %s" % (ins.address, ins.mnemonic, ins.op_str))
        print("  ctx refs:", sorted(ctx_refs))

for p in sys.argv[1:]:
    main(p)

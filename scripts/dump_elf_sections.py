import struct
import sys

def parse(path):
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    if i < 0:
        print(path, "no ELF")
        return
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
    print("== %s" % path)
    for sh in shdrs:
        name = sname(sh[0])
        print(
            "  %-20s type=%-3d flags=0x%-8x addr=0x%08x off=0x%-6x size=0x%-6x link=%-3d info=%-3d"
            % (name, sh[1], sh[2], sh[3], sh[4], sh[5], sh[6], sh[7])
        )

for p in sys.argv[1:]:
    parse(p)

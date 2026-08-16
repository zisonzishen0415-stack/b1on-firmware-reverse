import struct
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def find_symbol(e, le, shdrs, strtab_of, sname, name):
    # walk .symtab/.dynsym for symbol name, return value+size
    for sh in shdrs:
        if sh[1] not in (2, 11):  # SYMTAB or DYNSYM
            continue
        ent = sh[9] or 16
        base = sh[4]
        link = sh[6]
        strtab_sh = shdrs[link]
        strtab_blob = e[strtab_sh[4] : strtab_sh[4] + strtab_sh[5]]
        for off in range(base, base + sh[5], ent):
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                le + "IIIBBH", e, off
            )
            j = strtab_blob.find(b"\x00", st_name)
            nm = strtab_blob[st_name:j].decode("latin1")
            if nm == name:
                return st_value, st_size, sh
    return None

def main(path):
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
    # file offset for a VA: find PT_LOAD or section containing it
    def va_to_off(va):
        for sh in shdrs:
            if sh[1] != 1:
                continue
            addr, size, off = sh[3], sh[5], sh[4]
            if addr <= va < addr + size:
                return off + (va - addr)
        return None
    base = os.path.splitext(os.path.basename(path))[0]
    sym = find_symbol(e, le, shdrs, strtab, sname, "SonicStomp")
    if not sym:
        sym = find_symbol(e, le, shdrs, strtab, sname, base)
    if not sym:
        sym = find_symbol(e, le, shdrs, strtab, sname, base.title())
    if not sym:
        sym = find_symbol(e, le, shdrs, strtab, sname, base.lstrip("_"))
    if not sym:
        sym = find_symbol(e, le, shdrs, strtab, sname, base.lstrip("_").title())
    names = []
    if not sym:
        for sh in shdrs:
            if sh[1] != 11:
                continue
            ent = sh[9] or 16
            link = sh[6]
            strtab_sh = shdrs[link]
            strtab_blob = e[strtab_sh[4] : strtab_sh[4] + strtab_sh[5]]
            for off in range(sh[4], sh[4] + sh[5], ent):
                st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                    le + "IIIBBH", e, off
                )
                j = strtab_blob.find(b"\x00", st_name)
                nm = strtab_blob[st_name:j].decode("latin1")
                if nm and st_value:
                    names.append((nm, st_value, st_size))
        print("  dynsym sample:", [(n, hex(v)) for n, v, _ in names[:40]])
        return
    va, size, _ = sym
    print("SonicStomp at 0x%08x size %d" % (va, size))
    off = va_to_off(va)
    if off is None:
        print("cannot map VA to file")
        return
    n = 0
    while n < size // 48:
        row = data[i + off + n * 48 : i + off + n * 48 + 48]
        name = row[0:12].rstrip(b"\x00").decode("latin1")
        (maxv, defv, pedal, res, func, audio, gstr) = struct.unpack_from("<IIIIIII", row, 12)
        w28 = struct.unpack_from("<f", row, 40)[0]
        flags = struct.unpack_from("<I", row, 44)[0]
        print(
            "  [%d] %-12s max=%-8d def=%-6d pedal=%-6d res=0x%-8x func=0x%-8x audio=0x%-8x gstr=0x%-8x w28=%-8.2f flags=0x%02x"
            % (n, name, maxv, defv, pedal, res, func, audio, gstr, w28, flags)
        )
        n += 1

for p in sys.argv[1:]:
    main(p)

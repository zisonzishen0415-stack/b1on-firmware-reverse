import glob
import os
import re
import struct
import subprocess

DIS6X = r"C:\ti\ti-cgt-c6000_8.5.0.LTS\ti-cgt-c6000_8.5.0.LTS\bin\dis6x.exe"
OUT = r"work\ctx_class"
os.makedirs(OUT, exist_ok=True)

def get_desc_row(path):
    """Return (w28, audio_va, count) of the descriptor name entry."""
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    if i < 0:
        return None
    e = data[i:]
    le = "<"
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
    names = [
        "SonicStomp",
        os.path.splitext(os.path.basename(path))[0],
        os.path.splitext(os.path.basename(path))[0].lstrip("_"),
        os.path.splitext(os.path.basename(path))[0].title(),
    ]
    sym = None
    for sh in shdrs:
        if sh[1] not in (2, 11):
            continue
        ent = sh[9] or 16
        link = sh[6]
        strtab_sh = shdrs[link]
        blob = e[strtab_sh[4] : strtab_sh[4] + strtab_sh[5]]
        for off in range(sh[4], sh[4] + sh[5], ent):
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                le + "IIIBBH", e, off
            )
            j = blob.find(b"\x00", st_name)
            nm = blob[st_name:j].decode("latin1")
            if nm in names and st_value and 0x80000000 <= st_value < 0x80010000:
                sym = (st_value, st_size)
                break
        if sym:
            break
    if not sym:
        return None
    va, size = sym
    for sh in shdrs:
        if sh[1] == 1 and sh[3] <= va < sh[3] + sh[5]:
            off = sh[4] + (va - sh[3])
            row = data[i + off : i + off + 48]
            w28 = struct.unpack_from("<f", row, 40)[0]
            audio = struct.unpack_from("<I", row, 0x20)[0]
            return w28, audio, size // 48
    return None

def find_audio_sym(path):
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    e = data[i:]
    le = "<"
    shoff = struct.unpack_from(le + "I", e, 0x20)[0]
    shentsize = struct.unpack_from(le + "H", e, 0x2E)[0]
    shnum = struct.unpack_from(le + "H", e, 0x30)[0]
    shstrndx = struct.unpack_from(le + "H", e, 0x32)[0]
    shdrs = []
    for n in range(shnum):
        off = shoff + n * shentsize
        shdrs.append(struct.unpack_from(le + "IIIIIIIIII", e, off))
    for sh in shdrs:
        if sh[1] != 11:
            continue
        ent = sh[9] or 16
        strtab_sh = shdrs[sh[6]]
        blob = e[strtab_sh[4] : strtab_sh[4] + strtab_sh[5]]
        for off in range(sh[4], sh[4] + sh[5], ent):
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                le + "IIIBBH", e, off
            )
            j = blob.find(b"\x00", st_name)
            nm = blob[st_name:j].decode("latin1")
            if (
                nm.startswith("Fx_")
                and st_value
                and st_value < 0x80000000
                and re.match(r"^Fx_[A-Z0-9]+_[A-Za-z0-9]+$", nm)
            ):
                return nm, st_value
    return None

def main():
    rows = []
    for path in sorted(glob.glob(r"work\b1on130_fw\*.ZDL")):
        base = os.path.basename(path)
        data = open(path, "rb").read()
        i = data.find(b"\x7fELF")
        e = data[i:]
        elf = os.path.join(OUT, base + ".elf")
        open(elf, "wb").write(e)
        try:
            res = subprocess.run([DIS6X, "-1", "-d", elf], capture_output=True, timeout=60)
            text = res.stdout.decode("latin1", errors="replace")
        except Exception as ex:
            rows.append((base, "ERR", "", 0, 0, ""))
            continue
        # classify the audio function only
        asym = find_audio_sym(path)
        if asym:
            name, va = asym
            # extract function body: from label line to next label line
            m = re.search(r"^%08x\s+%s:" % (va, re.escape(name)), text, re.M)
            body = ""
            if m:
                nxt = re.search(r"^%08x\s+[A-Za-z_].*:$" % (va), text[ m.end() : ], re.M)
                body = text[m.start() : m.end() + (nxt.start() if nxt else 8000)]
            else:
                body = text
            idxs = re.findall(r"LDW\.D1T[12]\s+\*\+?A(?:4|21)\[(\d+)\]", body)
            idxs = [int(x) for x in idxs]
            c3 = 3 in idxs
            c2 = 2 in idxs
        else:
            c3 = c2 = False
        # audio section size
        r = get_desc_row(path)
        w28 = r[0] if r else None
        audio_va = r[1] if r else None
        count = r[2] if r else 0
        rows.append((base, "C3" if c3 else ("C2" if c2 else "?"), w28, audio_va, count, asym[0] if asym else ""))
    print("%-20s %-3s %8s %8s %5s  %s" % ("file", "ctx", "w28", "audioVA", "rows", "audioSym"))
    for r in rows:
        if r[1] == "ERR":
            print("%-20s ERR" % r[0])
            continue
        print(
            "%-20s %-3s %8s %8s %5d  %s"
            % (
                r[0],
                r[1],
                ("%.2f" % r[2]) if isinstance(r[2], float) else "-",
                ("0x%x" % r[3]) if r[3] else "0",
                r[4],
                r[5],
            )
        )

if __name__ == "__main__":
    main()

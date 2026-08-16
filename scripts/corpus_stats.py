import struct
import glob
import os
import json

def parse(path):
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    if i < 0:
        return None
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
    sec = {}
    for sh in shdrs:
        name = sname(sh[0])
        sec[name] = {
            "type": sh[1],
            "flags": sh[2],
            "addr": sh[3],
            "size": sh[5],
            "entsize": sh[9],
        }
    return sec

def get_w28(path):
    # find SonicStomp descriptor name entry: scan .const for pattern? Simpler: search for float near 20.0
    data = open(path, "rb").read()
    i = data.find(b"\x7fELF")
    if i < 0:
        return None
    return None

rows = []
for path in sorted(glob.glob(r"work\b1on130_fw\*.ZDL")):
    sec = parse(path)
    if sec is None:
        continue
    audio = sec.get(".audio", {})
    text = sec.get(".text", {})
    const = sec.get(".const", {})
    fardata = sec.get(".fardata", {})
    rows.append(
        (
            os.path.basename(path),
            "AUDIO" if audio.get("type") == 1 and audio.get("size", 0) else ("audioNOBITS" if audio.get("type") == 8 else "noaudio"),
            audio.get("size", 0),
            text.get("size", 0),
            const.get("size", 0),
            fardata.get("size", 0),
        )
    )

rows.sort(key=lambda r: (r[1], -r[3]))
print("%-20s %-11s %6s %6s %6s %6s" % ("file", "audio", "aSz", "tSz", "cSz", "fSz"))
for r in rows:
    print("%-20s %-11s %6d %6d %6d %6d" % r)

#!/usr/bin/env python3
"""Full byte-level dump of a ZDL for reverse engineering.

Dumps: wrapper INFO fields, ELF header, program headers, every section
header, all dynamic/relocation/symbol data, the full descriptor table,
the imageInfo structure, and disassemblies of the Dll/audio/onf/edit
functions. Output is a flat text report meant for diffing across files.

Usage: python full_zdl_dump.py file.zdl [out.txt]
"""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path


def parse_elf(elf: bytes):
    out = {}
    out["e_type"], out["e_machine"] = struct.unpack_from("<HH", elf, 0x10)
    out["e_version"], out["e_entry"], out["e_phoff"], out["e_shoff"], out["e_flags"] = \
        struct.unpack_from("<IIIII", elf, 0x14)
    out["e_ehsize"], out["e_phentsize"], out["e_phnum"] = struct.unpack_from("<HHH", elf, 0x28)
    out["e_shentsize"], out["e_shnum"], out["e_shstrndx"] = struct.unpack_from("<HHH", elf, 0x2E)
    phdrs = [struct.unpack_from("<8I", elf, out["e_phoff"] + i * out["e_phentsize"])
             for i in range(out["e_phnum"])]
    out["phdrs"] = phdrs
    shdrs = [struct.unpack_from("<10I", elf, out["e_shoff"] + i * out["e_shentsize"])
             for i in range(out["e_shnum"])]
    names = elf[shdrs[out["e_shstrndx"]][4]:shdrs[out["e_shstrndx"]][4] + shdrs[out["e_shstrndx"]][5]]
    secs = {}
    for i, sh in enumerate(shdrs):
        end = names.find(b"\x00", sh[0])
        nm = names[sh[0]:end].decode("latin1") if end >= 0 else ""
        secs[i] = {"name": nm, "type": sh[1], "flags": sh[2], "addr": sh[3],
                   "offset": sh[4], "size": sh[5], "link": sh[6], "info": sh[7],
                   "align": sh[8], "entsize": sh[9]}
    out["secs"] = secs
    return out


def find_sym(elf: bytes, secs: dict, target: str):
    for sname, tname in ((".dynsym", ".dynstr"), (".symtab", ".strtab")):
        si = next((i for i, s in secs.items() if s["name"] == sname), None)
        ti = next((i for i, s in secs.items() if s["name"] == tname), None)
        if si is None or ti is None:
            continue
        s, t = secs[si], secs[ti]
        sb = elf[s["offset"]:s["offset"] + s["size"]]
        tb = elf[t["offset"]:t["offset"] + t["size"]]
        for off in range(0, len(sb), 16):
            no, val = struct.unpack_from("<II", sb, off)
            if not no:
                continue
            end = tb.find(b"\x00", no)
            nm = tb[no:end].decode("latin1", "replace") if end >= 0 else ""
            if nm == target:
                return val
    return None


def dump(path: Path, dis6x: Path) -> str:
    data = path.read_bytes()
    out = []
    w = out.append
    w(f"===== {path.name} ({len(data)} bytes) =====")

    # --- wrapper ---
    w("\n[WRAPPER]")
    if data[:4] != b"\x00\x00\x00\x00":
        w("  missing NULL prefix")
        return "\n".join(out)
    szp, hdr_size, elf_size = struct.unpack_from("<III", data, 8)
    w(f"  SIZE payload={szp} header_size={hdr_size} elf_size={elf_size}")
    if data[20:24] != b"INFO":
        w("  missing INFO")
        return "\n".join(out)
    info = data[28:76]
    ver = info[:32].split(b"\x00")[0].decode("latin1")
    w(f"  version_string={ver!r}")
    b = info[32:40]
    w(f"  real_type={b[0]} unknown1={b[1]} knob_type={b[2]} unknown2={b[3]} "
      f"sort_index={b[4]} sort_sub={b[5]} bass_flags={b[6]} sort_fx_type={b[7]}")
    w(f"  fx_version={info[40:48]!r}")
    extra = data[76:76 + hdr_size - 56] if hdr_size > 56 else b""
    w(f"  extra_header_payload={len(extra)}B head={extra[:16]!r}")

    # --- ELF ---
    elf = data[76 + (hdr_size - 56):76 + (hdr_size - 56) + elf_size]
    p = parse_elf(elf)
    w("\n[ELF]")
    w(f"  type={p['e_type']} machine={p['e_machine']:#x} flags={p['e_flags']:#x} "
      f"entry={p['e_entry']:#x}")
    for ph in p["phdrs"]:
        w(f"  PHDR type={ph[0]} off={ph[1]:#x} vaddr={ph[2]:#x} filesz={ph[4]:#x} "
          f"memsz={ph[5]:#x} flags={ph[6]}")
    w("  sections:")
    for i in sorted(p["secs"]):
        s = p["secs"][i]
        w(f"    [{i:2d}] {s['name']:22s} t={s['type']:10d} f={s['flags']:#x} "
          f"a={s['addr']:#010x} off={s['offset']:#x} sz={s['size']:6d} lk={s['link']} "
          f"inf={s['info']} al={s['align']} es={s['entsize']}")

    # dynamic
    di = next((i for i, s in p["secs"].items() if s["name"] == ".dynamic"), None)
    if di is not None:
        s = p["secs"][di]
        db = elf[s["offset"]:s["offset"] + s["size"]]
        w("  .dynamic:")
        for o in range(0, len(db), 8):
            tag, val = struct.unpack_from("<ii", db, o)
            if tag == 0:
                break
            w(f"    tag={tag} val={val}")

    # relocations
    ri = next((i for i, s in p["secs"].items() if s["name"] == ".rela.dyn"), None)
    if ri is not None:
        s = p["secs"][ri]
        rb = elf[s["offset"]:s["offset"] + s["size"]]
        w(f"  .rela.dyn ({len(rb)//12} entries):")
        for o in range(0, len(rb), 12):
            roff, rinfo, radd = struct.unpack_from("<III", rb, o)
            w(f"    off={roff:#x} info={rinfo:#x} add={radd:#x}")

    # symbols
    w("  symbols (dynsym+symtab):")
    for sname, tname in ((".dynsym", ".dynstr"), (".symtab", ".strtab")):
        si = next((i for i, s in p["secs"].items() if s["name"] == sname), None)
        ti = next((i for i, s in p["secs"].items() if s["name"] == tname), None)
        if si is None or ti is None:
            continue
        s, t = p["secs"][si], p["secs"][ti]
        sb = elf[s["offset"]:s["offset"] + s["size"]]
        tb = elf[t["offset"]:t["offset"] + t["size"]]
        for off in range(0, len(sb), 16):
            no, val, size, info, other, shndx = struct.unpack_from("<IIIBBH", sb, off)
            end = tb.find(b"\x00", no)
            nm = tb[no:end].decode("latin1", "replace") if no and end >= 0 else ""
            if nm:
                w(f"    [{sname}] {nm:34s} val={val:#x} size={size} info={info:#04x} "
                  f"other={other} shndx={shndx}")

    # descriptor + imageInfo
    ci = next((i for i, s in p["secs"].items() if s["name"] == ".const"), None)
    if ci is not None:
        c = elf[p["secs"][ci]["offset"]:p["secs"][ci]["offset"] + p["secs"][ci]["size"]]
        off = 0
        found = -1
        while off + 0x60 <= len(c):
            if c[off:off + 6] == b"OnOff\x00":
                first = struct.unpack_from("<12I", c, off)
                second = struct.unpack_from("<12I", c, off + 0x30)
                if first[3] == 1 and second[3] == 0xFFFFFFFF:
                    found = off
                    break
            off += 4
        if found >= 0:
            w(f"\n[DESCRIPTOR] at .const+{found:#x} (VA {p['secs'][ci]['addr'] + found:#x})")
            o = found
            for r in range(32):
                raw = c[o + r * 0x30:o + (r + 1) * 0x30]
                if len(raw) < 0x30:
                    break
                nm = raw[:12].split(b"\x00")[0].decode("latin1", "replace")
                if not nm:
                    break
                wd = struct.unpack_from("<12I", raw, 0)
                w28 = struct.unpack("<f", struct.pack("<I", wd[10]))[0]
                w(f"  row{r:2d} {nm:10s} max={wd[3]:6d} def={wd[4]:10d} pedal={wd[5]:3d} "
                  f"h=0x{wd[7]:08x} a=0x{wd[8]:08x} w28={w28:8.2f} fl=0x{wd[11]:02x}")
            # imageInfo
            iva = find_sym(elf, p["secs"], "effectTypeImageInfo")
            if iva is not None:
                ii = c[iva - p["secs"][ci]["addr"]:iva - p["secs"][ci]["addr"] + 212]
                w(f"\n[IMAGEINFO] VA {iva:#x}")
                wd = struct.unpack_from("<53I", ii, 0)
                w(f"  hdr={wd[0]} {wd[1]} {wd[2]} w={wd[3]} h={wd[4]} pic={wd[5]:#x} "
                  f"h6={wd[6]} h7={wd[7]} count={wd[8]}")
                for k in range(wd[8] if wd[8] < 12 else 12):
                    o2 = 36 + k * 16
                    kid, kx, ky, kva = struct.unpack_from("<IIII", ii, o2)
                    w(f"    coord{k}: kid={kid} x={kx} y={ky} va={kva:#x}")
        # picture size
        pva = find_sym(elf, p["secs"], "picEffectType_" + path.stem) or \
              find_sym(elf, p["secs"], "picEffectType_SVT") or \
              find_sym(elf, p["secs"], "picEffectType_ToTape9") or \
              find_sym(elf, p["secs"], "picEffectType_AmpNeve") or \
              find_sym(elf, p["secs"], "picEffectType_GAIN")
        if pva is not None and found >= 0:
            pic_off = pva - p["secs"][ci]["addr"]
            w(f"\n[PICTURE] VA {pva:#x} size={(found - pic_off) if found > pic_off else '?'} "
              f"head={c[pic_off:pic_off+16]!r}")

    # disassemble key functions
    for symname in ("Dll_" + path.stem, None):
        pass
    dllname = None
    for cand in ("Dll_" + path.stem, "Dll_SVT", "Dll_ToTape9", "Dll_AmpNeve", "Dll_Gain",
                 "Dll_Delay", "Dll_GAIN"):
        if find_sym(elf, p["secs"], cand) is not None:
            dllname = cand
            break
    if dllname and dis6x and dis6x.exists():
        tmp = path.with_suffix(".elf")
        tmp.write_bytes(elf)
        r = subprocess.run([str(dis6x), str(tmp)], capture_output=True, text=True)
        w(f"\n[DISASM {dllname}] (via dis6x, full listing below)")
        w(r.stdout[-20000:] if r.stdout else r.stderr[-5000:])
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    dis6x = Path(r"C:\ti\ti-cgt-c6000_8.5.0.LTS\ti-cgt-c6000_8.5.0.LTS\bin\dis6x.exe")
    report = dump(path, dis6x)
    if len(argv) >= 3:
        Path(argv[2]).write_text(report, encoding="utf-8")
        print(f"wrote {argv[2]}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

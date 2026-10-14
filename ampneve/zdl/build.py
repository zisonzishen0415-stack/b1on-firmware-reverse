#!/usr/bin/env python3
"""Build AmpNeve.ZDL from ampsim_zdl.c + manifest.json.

Requires TI C6000 Code Generation Tools (cl6x). Point AMPNEVE_TI_ROOT at the
compiler install, or set it in the file below. Example:
  AMPNEVE_TI_ROOT=/Applications/ti/ccs2050/ccs/tools/compiler/ti-cgt-c6000_8.5.0.LTS \\
    python3 build.py

Options:
  --smoke        link with audio_nop (pass-through DSP) - the FIRST thing a
                 new pedal should ever see. Output goes to dist_smoke/, not
                 dist/. Flash it, verify the effect appears and the pages/
                 knobs work, and only then build the real DSP.
  --no-inspect   skip the post-compile .obj safety audit (tools/check_zdl_obj.py).
                 The audit is pure Python (no TI tools) and fails the build on
                 the frozen-pedal patterns from SAFE-DSP-RULES; leave it on.

Compiler flags follow the reverson hardware-proven release pattern: -O2 and
NO --opt_for_space. High --opt_for_space emits __c6xabi_push_rts/pop_rts
helper calls whose bundled stubs are not hardware-tested here (see
SAFE-DSP-RULES). Set AMPNEVE_OPT_FOR_SPACE=n to experiment explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# ZoomMultistompZDL linker trees live under the g1oncontrol umbrella
# (<g1oncontrol>/zoomreverse/...). 2026-10-14: the old Documents\ChatGPT\
# zoomreverse copy was archived; defaults point at the fixed working tree
# first, then the frozen fork+shim tree, then the bundled upstream clone.
G1ON = HERE.parents[2]  # zdl -> ampneve -> b1on-firmware-reverse -> g1oncontrol
ZDL_ROOT = Path(os.environ.get("AMPNEVE_ZDL_ROOT",
    str(G1ON / "zoomreverse" / "ZoomMultistompZDL-2026-10")))
if not ZDL_ROOT.exists():
    ZDL_ROOT = G1ON / "zoomreverse" / "ZoomMultistompZDL"
if not ZDL_ROOT.exists():
    ZDL_ROOT = ROOT / "third_party" / "ZoomMultistompZDL"
sys.path.insert(0, str(ZDL_ROOT / "build"))
sys.path.insert(0, str(ZDL_ROOT / "src" / "airwindows" / "common"))

from linker import LinkerConfig, link, params_from_manifest  # noqa: E402
from manifest_params import write_param_header  # noqa: E402

TI_ROOT = Path(os.environ.get("AMPNEVE_TI_ROOT",
    "/Applications/ti/ccs2050/ccs/tools/compiler/ti-cgt-c6000_8.5.0.LTS"))
if not (TI_ROOT / "bin" / "cl6x").exists() and not (TI_ROOT / "bin" / "cl6x.exe").exists():
    _cand = Path(r"C:\ti\ti-cgt-c6000_8.5.0.LTS\ti-cgt-c6000_8.5.0.LTS")
    if (_cand / "bin" / "cl6x.exe").exists():
        TI_ROOT = _cand
CL6X = TI_ROOT / "bin" / "cl6x"
if not CL6X.exists() and (TI_ROOT / "bin" / "cl6x.exe").exists():
    CL6X = TI_ROOT / "bin" / "cl6x.exe"      # Windows install

CFLAGS = [
    "--c99",
    "--opt_level=2",
    "-mv6740",
    "--abi=eabi",
    "--mem_model:data=far",                 # critical, see ABI.md
    f"--include_path={ROOT / 'core'}",
    f"--include_path={TI_ROOT / 'include'}",
]
# Experiment-only escape hatch (see module docstring). Unset by default.
_opt_for_space = os.environ.get("AMPNEVE_OPT_FOR_SPACE")
if _opt_for_space:
    CFLAGS.insert(3, f"--opt_for_space={_opt_for_space}")


def check_effect_name(name: str) -> None:
    """Reject basenames Zoom may truncate or that collide with stock ZDLs
    (SAFE-DSP-RULES: both have frozen real pedals)."""
    if len(name) > 8:
        sys.exit(f"[ampneve] effect_name '{name}' is >8 chars; Zoom truncates "
                 "basenames and truncated duplicates have frozen pedals.")
    trimmed = name[:8].upper()
    stock_dir = ZDL_ROOT / "stock_zdls"
    if stock_dir.exists():
        for z in stock_dir.glob("*.ZDL"):
            if z.stem[:8].upper() == trimmed:
                sys.exit(f"[ampneve] basename collision with stock effect "
                         f"'{z.name}' - rename the effect.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true",
                        help="link with audio_nop (pass-through); output to dist_smoke/")
    parser.add_argument("--no-inspect", action="store_true",
                        help="skip the post-compile .obj safety audit")
    parser.add_argument("--no-cabi", action="store_true",
                        help="skip injecting the G1on AMP CABI header block "
                             "(kept for experiments; G1on AMP loads expect it)")
    parser.add_argument("--b1on", action="store_true",
                        help="build the B1on-native variant: BassAmp category "
                             "(gid=5), BCAB header payload, 3-field Dll stub, "
                             "CAB descriptor default=0. Same DSP and IRs; "
                             "only the loader metadata matches B1Xon stock amps.")
    return parser.parse_args(argv[1:])


def add_cabi(zdl_path: Path, fxid: int, effect_name: str) -> None:
    """Inject the CABI block every stock G1on AMP-category ZDL carries.

    The wrapper block is a G1on loader expectation for AMP-category effects
    (22/22 stock G1on amp models ship with it; our plain 56-byte header is the
    only structural difference from them). The DSP never reads it - AmpNeve
    renders its cabinets from the two embedded IR kernels (2x12 default /
    4x12, selected by the Cabtype knob), not from CABI coefficients - so the
    floats inside are inert loader metadata. We keep the stock 2x12 template
    and patch only the fxid/gid word and the model name.
    """
    sys.path.insert(0, str(ZDL_ROOT / "build"))
    from zdl import HEADER_SIZE_TYPICAL, Zdl  # noqa: E402

    template = (HERE / "cabi_2x12_template.bin").read_bytes()
    if template[:4] != b"CABI":
        sys.exit(f"[ampneve] {HERE / 'cabi_2x12_template.bin'} is not a CABI block")
    cabi = bytearray(template)
    struct.pack_into("<I", cabi, 0x08, (0x04 << 24) | (fxid & 0xFFFF))
    prefix = effect_name[:2].upper().ljust(2, "\x00").encode("latin1")
    cabi[0x0C:0x0E] = prefix
    model = effect_name[:8].upper().ljust(8, "\x00").encode("latin1")
    cabi[0x14:0x1C] = model

    z = Zdl.load(zdl_path)
    z.extra_header_payload = bytes(cabi)
    z.header_size = HEADER_SIZE_TYPICAL + len(cabi)
    zdl_path.write_bytes(z.pack())
    print(f"[ampneve] G1on AMP CABI block injected -> {zdl_path.name} "
          f"(header {HEADER_SIZE_TYPICAL} -> {z.header_size} bytes)")


def add_bcab(zdl_path: Path, effect_name: str) -> None:
    """Inject the BCAB block every stock B1Xon/B1on BassAmp ZDL carries.

    Mirrors the stock SVT payload (176 bytes): 'BCAB' + length + metadata.
    Our DSP never reads it - AmpNeve renders cabinets from its embedded IR
    kernels - so only the model/cab name strings are patched.
    """
    sys.path.insert(0, str(ZDL_ROOT / "build"))
    from zdl import HEADER_SIZE_TYPICAL, Zdl  # noqa: E402

    template = (HERE / "bcab_template.bin").read_bytes()
    if template[:4] != b"BCAB":
        sys.exit(f"[ampneve] {HERE / 'bcab_template.bin'} is not a BCAB block")
    bcab = bytearray(template)
    prefix = effect_name[:2].upper().ljust(2, "\x00").encode("latin1")
    bcab[0x0C:0x0E] = prefix
    cabname = b"2x12\x00\x00\x00\x00"
    bcab[0x14:0x1C] = cabname

    z = Zdl.load(zdl_path)
    z.extra_header_payload = bytes(bcab)
    z.header_size = HEADER_SIZE_TYPICAL + len(bcab)
    zdl_path.write_bytes(z.pack())
    print(f"[ampneve] B1on BCAB block injected -> {zdl_path.name} "
          f"(header {HEADER_SIZE_TYPICAL} -> {z.header_size} bytes)")


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    manifest_path = Path(os.environ.get("AMPNEVE_MANIFEST", "manifest.json"))
    manifest = json.loads((HERE / manifest_path).read_text(encoding="utf-8-sig"))
    # Env overrides let a smoke/AB variant ship alongside the real effect
    # (same-fxid duplicates collide on the pedal, so give variants a unique
    # name + fxid): AMPNEVE_EFFECT_NAME / AMPNEVE_FXID.
    name = os.environ.get("AMPNEVE_EFFECT_NAME", manifest["effect_name"])
    fxid = int(os.environ.get("AMPNEVE_FXID", manifest["fxid"]))
    audio_func = os.environ.get("AMPNEVE_AUDIO_FUNC",
                                manifest.get("audio_func_name"))
    w28_env = os.environ.get("AMPNEVE_W28")
    self_row_w28 = float(w28_env) if w28_env else None
    # B1on stock imageInfo always advertises count=3 (one knob row of 3),
    # regardless of the real descriptor param count (stock SVT has 9 params
    # with count=3). repeat98's MS-70CDR-style count=9 imageInfo loads on the
    # B1on but the knob/page walk comes out wrong (ToTape9/TEcho4 crippled).
    # Default to the B1on convention; override with AMPNEVE_IMAGE_INFO_COUNT.
    image_info_count = os.environ.get("AMPNEVE_IMAGE_INFO_COUNT")
    if image_info_count is not None:
        image_info_count = int(image_info_count)
    dll_fields = int(os.environ.get("AMPNEVE_DLL_FIELDS", "3"))
    check_effect_name(name)

    if not CL6X.exists():
        sys.exit(
            f"[ampneve] TI C6000 compiler not found at {CL6X}\n"
            "  Install TI CGT C6000 8.5.x LTS (free TI-account download) and set\n"
            "  AMPNEVE_TI_ROOT (see zdl/README.md).")

    smoke = args.smoke
    audio_nop = bool(manifest.get("audio_nop", False)) or smoke
    out_dir = ROOT / ("dist_smoke" if smoke else "dist")
    out_dir.mkdir(parents=True, exist_ok=True)

    # The B1on/G1on host renders the effect screen from a device-specific
    # bitmap format that differs from the MS-70CDR text screen. Ship the
    # stock SVT artwork bytes (1304 B) so the picture renders and the host
    # never walks past the buffer.
    pic_path = HERE / "svt_pic.bin"
    screen_image = pic_path.read_bytes() if pic_path.exists() else None

    # Category override: AMPNEVE_GID lets a non-amp build register the same
    # DSP under any stock category (e.g. 9=REV), which avoids the AMP-only
    # CABI/BCAB loader machinery entirely. gid 5 = B1on-native bass amp.
    env_gid = int(os.environ.get("AMPNEVE_GID", "0") or "0")
    gid = env_gid or (5 if args.b1on else int(manifest.get("gid", 4)))
    is_amp = gid in (4, 5)
    # G1on/B1on stock imageInfo always advertises count=3 (one knob row of
    # 3), regardless of the real descriptor param count (stock SVT has 9
    # params with count=3; TW_ROCK has 7 with count=3). The MS-70CDR-style
    # count=9 loads on the B1on/G1on but the knob/page walk comes out wrong.
    # Override with AMPNEVE_IMAGE_INFO_COUNT.
    if image_info_count is None and gid in (4, 5):
        image_info_count = 3
    flags_byte = 0 if gid == 5 else int(manifest.get("flags_byte", 0x01))
    bass_flags = 0x10 if gid == 5 else 0
    # G1on AMP-category effects need the 5-field Dll stub (count, descriptor
    # VA, imageInfo VA, plus two role-handler VAs). Stock G1on amp Dll stubs
    # write all five; the MS-70CDR-style 3-field stub registers a bypass/no-UI
    # effect that skips audio and freezes on re-entry (see zdl/README.md).
    # B1on BassAmp (gid=5) keeps the 3-field stub.
    dll_fields = 3 if gid == 5 else int(os.environ.get("AMPNEVE_DLL_FIELDS", "5"))
    # amp_cabi_* fed the lost repeat98 linker's CABI descriptor path; the
    # surviving trees raise on it (loud). The loader-visible CABI content
    # (fxid/gid word, prefix, model name) is written post-link by add_cabi()/
    # add_bcab() instead -- verified against the 22/22 stock G1on amp layout --
    # so passing None here is lossless for these builds.
    amp_cabi_default = None
    amp_cabi_fxid = None

    if smoke:
        print("[ampneve] *** SMOKE BUILD: audio function is NOPed (pass-through). ***")
        print("[ampneve] *** Flash this FIRST on a new pedal. Do not publish. ***")

    write_param_header(manifest, HERE / "ampsim_zdl_params.h", "AMPNEVE")

    src_c = HERE / "ampsim_zdl.c"
    obj = HERE / "ampsim_zdl.obj"
    out_zdl = out_dir / f"{name}.ZDL"

    print(f"[ampneve] compiling {src_c.name} -> {obj.name}")
    audio_defs = []
    if audio_func != manifest.get("audio_func_name"):
        audio_defs = [f"-DAMP_DRV_AUDIO_FUNC={audio_func}",
                      f"-DAMP_DRV_INIT_FUNC={audio_func}_init"]
    probe_defs = ["-DAMPNEVE_STATELESS"] if os.environ.get("AMPNEVE_STATELESS") else []
    fardata_state = bool(os.environ.get("AMPNEVE_FARDATA_STATE"))
    if fardata_state:
        probe_defs.append("-DAMPNEVE_FARDATA_STATE")
    if os.environ.get("AMPNEVE_INIT_ONLY"):
        probe_defs.append("-DAMPNEVE_INIT_ONLY")
    if os.environ.get("AMPNEVE_CTX2_STATE"):
        probe_defs.append("-DAMPNEVE_CTX2_STATE")
    subprocess.run([str(CL6X), *CFLAGS, *audio_defs, *probe_defs, "-c", str(src_c),
                    f"--output_file={obj}"],
                   check=True, cwd=HERE)

    if not args.no_inspect:
        print("[ampneve] auditing", obj.name, "(tools/check_zdl_obj.py)")
        subprocess.run([sys.executable, "-B", str(ROOT / "tools" / "check_zdl_obj.py"),
                        str(obj)], check=True)

    for junk in ("compiler.opt", "linker.cmd"):
        p = HERE / junk
        if p.exists():
            p.unlink()

    cfg = LinkerConfig(
        effect_name=name,
        audio_func_name=audio_func,
        gid=gid,
        fxid=fxid,
        params=params_from_manifest(manifest["params"]),
        obj_path=obj,
        output_path=out_zdl,
        fxid_version=manifest.get("fxid_version", "1.00").encode("ascii"),
        flags_byte=flags_byte,
        bass_flags=bass_flags,
        audio_nop=audio_nop,
        use_object_edit_handlers=False,
        synthesize_linesel_edit_handlers=True,
        synth_edit_start_index=2,
        # G1on requires the effect to materialize its own params through
        # _init: the host leaves the param table untouched, so params[0]
        # (the on flag) stays 0 and the effect sits in bypass with no UI and
        # re-entry freezes. Fx_AMP_AmpNeve_init writes the ON flag plus the
        # nine knob defaults into ctx[1]. B1on BassAmp (gid=5) keeps the
        # NOP_RETURN init (its host materializes defaults from the
        # descriptor). Override with AMPNEVE_USE_OBJECT_INIT=0/1.
        use_object_init_handler=(
            os.environ.get("AMPNEVE_USE_OBJECT_INIT", "1" if gid == 4 else "0")
            == "1"
        ),
        knob3_blob_path=Path("/tmp/__nonexistent__"),
        amp_cabi_fxid=amp_cabi_fxid,
        amp_cabi_default=amp_cabi_default,
        dll_fields=dll_fields,
        # Keep linker defaults (imageInfo count=params, header (21,23),
        # text screen): the repeat98 dist effects (ToTape9/TEcho4, 9 knobs)
        # load fine on the B1on exactly like this. The freeze was the AMP
        # wrapper (CABI/BCAB + CAB/OUT rows), not the imageInfo.
        knob_positions=[(2, 14, 46), (3, 55, 46), (4, 96, 46)],
        image_info_knob_count=image_info_count,
        screen_image=screen_image,
        self_row_w28=self_row_w28,
        max_fardata_bytes=64 * 1024,
        allow_large_fardata=fardata_state,
        # B1on/G1on stock-shape audio segment (2026-10-13 round-5 finding:
        # every stock G1on ZDL keeps the audio function in its own executable
        # segment @ VA 0x7800; our merged-into-.text shape is a structural
        # difference). 0 = legacy merged layout. Set AMPNEVE_AUDIO_VA=0x7800
        # to emit the stock shape.
        audio_va=int(os.environ.get("AMPNEVE_AUDIO_VA", "0") or "0", 0),
    )
    link(cfg)

    if gid == 5:
        add_bcab(out_zdl, name)
    elif gid == 4 and not args.no_cabi:
        add_cabi(out_zdl, fxid, name)

    if smoke:
        print(f"\n[ampneve] smoke done -> {out_zdl}  (PASS-THROUGH - test only)")
    else:
        print(f"\n[ampneve] done -> {out_zdl}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

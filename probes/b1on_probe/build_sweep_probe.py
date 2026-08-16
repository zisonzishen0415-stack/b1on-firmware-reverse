#!/usr/bin/env python3
"""Build the single-flash ctx[3] sweep probes (FLT and DLY identities).

Outputs:
  out/B1sweepFLT.ZDL  gid=2 (FLT), w28=20.0
  out/B1sweepDLY.ZDL  gid=8 (DLY), w28=20.0

Flash ONE of them, put it in the chain, turn the Arm switch on, and count
how many wobble segments play before silence.  Each segment is 1.5 s.
Decode table:
  segs  span(bytes)          segs  span(bytes)
  0     < 640                7     >= 64K
  1     >= 640               8     >= 128K
  2     >= 1K                9     >= 256K
  3     >= 2K                10    >= 512K
  4     >= 4K                11    >= 704K(大区!)
  5     >= 8K                12    >= 704K(直到结束)
  6     >= 16K
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "repeat98_tmp"
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "src" / "airwindows" / "common"))

from airwindows_image import make_airwindows_tape_screen  # noqa: E402
from linker import LinkerConfig, link, params_from_manifest  # noqa: E402
from manifest_params import write_param_header  # noqa: E402

TI_ROOT = Path(r"C:\ti\ti-cgt-c6000_8.5.0.LTS\ti-cgt-c6000_8.5.0.LTS")
CL6X = TI_ROOT / "bin" / "cl6x"
SRC = ROOT / "src" / "hardware_probes" / "descsize" / "descsize_sweep.c"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

CFLAGS = [
    "--c99",
    "--opt_level=2",
    "-mv6740",
    "--abi=eabi",
    "--mem_model:data=far",
    f"--include_path={TI_ROOT}/include",
]

MANIFEST = {
    "gid": 2,
    "fxid": 418,
    "fxid_version": "1.00",
    "flags_byte": 1,
    "params": [
        {
            "name": "Arm",
            "type": "switch",
            "max": 1,
            "default": 0,
            "audio_min": 0.0,
            "audio_max": 1.0,
            "audio_default": 0.0,
        }
    ],
}


def main() -> None:
    write_param_header(MANIFEST, HERE / "descsize_params.h", "DESCSIZE")
    params = params_from_manifest(MANIFEST["params"])
    for effect_name, gid in (("B1sweepFLT", 2), ("B1sweepDLY", 8)):
        audio_func_name = f"Fx_FLT_{effect_name}"
        obj = HERE / f"{effect_name}.obj"
        out_zdl = OUT / f"{effect_name}.ZDL"
        print(f"[sweep-probe] {effect_name}: gid={gid}")
        subprocess.run(
            [
                str(CL6X),
                *CFLAGS,
                f"--define=DESCSIZE_AUDIO_FUNC={audio_func_name}",
                f"--include_path={HERE}",
                f"--include_path={SRC.parent}",
                "-c",
                str(SRC),
                f"--output_file={obj}",
            ],
            check=True,
            cwd=HERE,
        )
        cfg = LinkerConfig(
            effect_name=effect_name,
            audio_func_name=audio_func_name,
            gid=gid,
            fxid=418,
            params=params,
            obj_path=obj,
            output_path=out_zdl,
            fxid_version=b"1.00",
            flags_byte=0x01,
            cost_w28=20.0,
            screen_image=make_airwindows_tape_screen(effect_name[:6], ""),
        )
        link(cfg)
    print("\n[sweep-probe] done ->", OUT)


if __name__ == "__main__":
    main()

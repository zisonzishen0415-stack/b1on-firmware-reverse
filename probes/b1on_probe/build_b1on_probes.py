"""Build read-only ctx[3] probes for B1on hardware.

The DSP reads ctx[3][0..2] ({base,end,span}) and reports via a safe stereo
wobble on the ctx[2]+0x18 counter ONLY when the descriptor byte length
meets the variant threshold. It never writes to the ctx[3] arena itself.

Variants:
  * threshold bisection (FLT gid, w28=20.0): 640B, 1K, 2K, 4K, 64K, 512K, 704K
  * gid=8 (DLY) with w28=20.0: 1K and 704K  -> tests per-type arena allocation
  * gid=2 (FLT) with w28=15.55 (DELAY value): 1K and 704K -> tests w28 trigger
"""

from __future__ import annotations

import json
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
SRC = ROOT / "src" / "hardware_probes" / "descsize" / "descsize.c"
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

# effect_name, gid, w28, threshold
VARIANTS = [
    # arena bisection, FLT (gid=2), w28=20.0
    ("B1sz0640", 2, 20.0, 640),
    ("B1sz001K", 2, 20.0, 1024),
    ("B1sz002K", 2, 20.0, 2048),
    ("B1sz004K", 2, 20.0, 4096),
    ("B1sz064K", 2, 20.0, 65536),
    ("B1sz512K", 2, 20.0, 524288),
    ("B1sz704K", 2, 20.0, 720896),
    # gid=8 (DLY) probes
    ("B1dly001K", 8, 20.0, 1024),
    ("B1dly704K", 8, 20.0, 720896),
    # w28=15.55 probes
    ("B1w15501K", 2, 15.55, 1024),
    ("B1w15504K", 2, 15.55, 4096),
    ("B1w15564K", 2, 15.55, 65536),
    ("B1w1557MK", 2, 15.55, 720896),
]

MANIFEST_BASE = {
    "gid": 2,
    "fxid": 417,
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
    manifest = dict(MANIFEST_BASE)
    write_param_header(manifest, HERE / "descsize_params.h", "DESCSIZE")
    params = params_from_manifest(manifest["params"])
    for effect_name, gid, w28, threshold in VARIANTS:
        audio_func_name = f"Fx_FLT_{effect_name}"
        obj = HERE / f"{effect_name}.obj"
        out_zdl = OUT / f"{effect_name}.ZDL"
        print(f"[b1on-probe] {effect_name}: gid={gid} w28={w28} thresh={threshold}")
        subprocess.run(
            [
                str(CL6X),
                *CFLAGS,
                f"--define=DESCSIZE_AUDIO_FUNC={audio_func_name}",
                f"--define=DESCSIZE_THRESHOLD_BYTES={threshold}u",
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
            fxid=417,
            params=params,
            obj_path=obj,
            output_path=out_zdl,
            fxid_version=b"1.00",
            flags_byte=0x01,
            cost_w28=w28,
            screen_image=make_airwindows_tape_screen(effect_name[:6], ""),
        )
        link(cfg)
    print("\n[b1on-probe] done ->", OUT)

if __name__ == "__main__":
    main()

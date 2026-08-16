import re
import numpy as np

SR = 44100.0

def parse_array(name, text):
    m = re.search(rf"{name}\[\s*AMP_CAB_IR_N\s*\]\s*=\s*\{{(.*?)\}};", text, re.S)
    if not m:
        raise SystemExit(f"{name} not found")
    vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", m.group(1))]
    return np.array(vals)

with open(r"C:\Users\29517\Documents\Codex\2026-08-13\https-github-com-zisonzishen0415-stack-ampneve\ampneve\core\ampsim_coeffs.h", "r", encoding="utf-8") as f:
    text = f.read()

nash = parse_array("AMP_CAB_IR_NASH", text)
emo = parse_array("AMP_CAB_IR_EMO", text)

def resp(ir, freq):
    w = 2 * np.pi * freq / SR
    n = np.arange(len(ir))
    return np.abs(np.sum(ir * np.exp(-1j * w * n)))

print(f"IR lengths: nash={len(nash)} emo={len(emo)}")
print(f"sum of taps: nash={nash.sum():.4f} emo={emo.sum():.4f}")

print("\nFrequency response (dB, relative to 1 kHz):")
freqs = [82.5, 110, 165, 220, 330, 440, 550, 660, 770, 880, 990, 1100, 1320, 1540, 1760, 2200, 3300, 4400, 5500]
for vname, ir in (("NASH", nash), ("EMO", emo)):
    db = [20 * np.log10(resp(ir, f) + 1e-12) for f in freqs]
    ref = db[freqs.index(990)]
    print(f"{vname}:")
    for f, d in zip(freqs, db):
        print(f"  {f:5.0f} Hz: {d - ref:+6.1f} dB (rel 1k)")

print("\nSweep 100..2000 Hz every 25 Hz (NASH, rel 1k):")
for f in range(100, 2001, 25):
    d = 20 * np.log10(resp(nash, f) + 1e-12)
    ref = 20 * np.log10(resp(nash, 1000) + 1e-12)
    bar = "#" * max(0, int((d - ref) * 2 + 20))
    print(f"{f:5d} {d - ref:+6.1f} {bar}")

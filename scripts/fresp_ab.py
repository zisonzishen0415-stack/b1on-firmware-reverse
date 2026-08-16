"""Clean frequency-response A/B: v15 vs v12 at two input levels.
Measures output amplitude at each input frequency (exact FFT bin, 1 s
window) so distortion products don't pollute the reading.
"""
import wave, numpy as np, subprocess, os, sys

ROOT = r"C:\Users\29517\Documents\Codex\2026-08-13\https-github-com-zisonzishen0415-stack-ampneve"
SR = 44100
FREQS = [80, 120, 200, 400, 800, 1000, 1200, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000]
LEVELS = [0.03, 0.15]   # -30 dBFS (linear-ish) and -16 dBFS (edge)

def make_wav(path, f, amp):
    n = 2 * SR
    t = np.arange(n) / SR
    x = (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)
    w = wave.open(path, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x * 32767).astype(np.int16).tobytes())
    w.close()

def out_amp(path, f):
    w = wave.open(path, 'rb')
    n = w.getnframes()
    raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    w.close()
    # stereo output from the renderer: take left channel
    x = raw.reshape(-1, 2)[:, 0] if len(raw) == 2 * (len(raw) // 2) else raw
    seg = x[-SR:]
    X = np.fft.rfft(seg)
    return abs(X[f]) / SR * 2.0

def render(exe, src, dst, gain, master, level, input_amp):
    r = subprocess.run([exe, src, dst, "1.0", str(gain), "0.5", "0.5", "0.5",
                        str(master), str(level), "1.0", "0.5", "1.0", "0.0"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(r.stderr); sys.exit(1)

def main():
    os.makedirs(os.path.join(ROOT, "work", "fresp"), exist_ok=True)
    res = {name: {lv: [] for lv in LEVELS} for name in ("v15", "v12")}
    for name, exe in (("v15", r"work\render_v15.exe"), ("v12", r"work\render_v12.exe")):
        for lv in LEVELS:
            for f in FREQS:
                src = os.path.join(ROOT, "work", "fresp", f"in_{f}.wav")
                dst = os.path.join(ROOT, "work", "fresp", f"{name}_{lv}_{f}.wav")
                make_wav(src, f, lv)
                render(os.path.join(ROOT, exe), src, dst, 0.25, 0.5, 0.8, lv)
                a = out_amp(dst, f)
                res[name][lv].append(a)
                print(f"{name} lv={lv} f={f}: {20*np.log10(a+1e-12):.1f} dB")
    # relative table (normalize to 1 kHz = 0 dB)
    print("\nfreq    v15-30  v15-16  v12-30  v12-16")
    for i, f in enumerate(FREQS):
        row = []
        for name in ("v15", "v12"):
            for lv in LEVELS:
                a = res[name][lv][i]
                a1k = res[name][lv][FREQS.index(1000)] if 1000 in FREQS else 1.0
                row.append(20 * np.log10(a / a1k + 1e-12))
        print(f"{f:5d}  " + "  ".join(f"{v:6.1f}" for v in row))

if __name__ == "__main__":
    main()

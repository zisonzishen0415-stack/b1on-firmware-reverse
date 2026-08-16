import numpy as np
import wave
import sys

SR = 44100

def load(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        ch = w.getnchannels()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768.0
    if ch == 2:
        raw = raw.reshape(-1, 2).mean(axis=1)
    return raw

def analyze(path, label):
    x = load(path)
    # steady state: middle 0.8 s (pluck transient excluded)
    seg = x[int(len(x) * 0.35):int(len(x) * 0.35) + 35300]
    win = np.hanning(len(seg))
    spec = np.fft.rfft(seg * win)
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)
    mag = np.abs(spec)

    mask = (freqs >= 50) & (freqs <= 12000)
    idx = np.argsort(mag[mask])[-10:][::-1]
    fpk = freqs[mask][idx]
    mpk = 20 * np.log10(mag[mask][idx] + 1e-12)

    # harmonic series around 82 Hz (fundamental)
    lo = (freqs > 70) & (freqs < 100)
    f0 = freqs[lo][np.argmax(mag[lo])]
    print(f"=== {label} ===")
    print(f"  f0 ~ {f0:.1f} Hz  top peaks:")
    for f, m in zip(fpk, mpk):
        print(f"    {f:7.1f} Hz: {m:+7.1f} dB")
    print("  harmonics of f0:")
    for h in range(1, 13):
        b = np.argmin(np.abs(freqs - f0 * h))
        print(f"    h{h:2d} ({f0*h:6.1f} Hz): {20*np.log10(mag[b]+1e-12):+7.1f} dB")

if __name__ == "__main__":
    root = r"C:\Users\29517\Documents\Codex\2026-08-13\https-github-com-zisonzishen0415-stack-ampneve\work"
    files = [
        ("out_flat.wav", "Nashville flat"),
        ("out_all1.wav", "Nashville bass=1 mid=1 treble=1"),
        ("out_midtreb.wav", "Nashville mid=1 treble=1"),
        ("out_basstreb.wav", "Nashville bass=1 treble=1"),
        ("out_treb.wav", "Nashville treble=1"),
        ("out_flat_emo.wav", "Emo flat"),
        ("out_midtreb_emo.wav", "Emo mid=1 treble=1"),
    ]
    for name, label in files:
        analyze(f"{root}\\{name}", label)

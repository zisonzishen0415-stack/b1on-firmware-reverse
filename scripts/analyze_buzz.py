import numpy as np
import wave
import sys

SR = 44100

def synth_guitar(dur=2.0):
    """A plucky, slightly dirty guitar-ish tone: low E + A + harmonic + noise."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f0, amp in ((82.4, 0.55), (110.0, 0.35), (220.0, 0.20), (329.6, 0.08)):
        # decaying pluck
        env = np.exp(-t * (2.0 + f0 / 200.0))
        x += amp * env * np.sin(2 * np.pi * f0 * t)
    # slight inharmonicity / pick noise
    x += 0.03 * np.exp(-t * 30.0) * np.random.default_rng(0).normal(0, 1, n)
    x /= np.max(np.abs(x))
    return x

def write_wav(path, x):
    pcm = np.clip(x, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def analyze(path, label):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768.0
    # take the last half (steady state), mono already
    seg = raw[-n // 2:]
    win = np.hanning(len(seg))
    spec = np.fft.rfft(seg * win)
    freqs = np.fft.rfftfreq(len(seg), 1 / SR)
    mag = np.abs(spec)
    # top 12 peaks between 50 Hz and 12 kHz
    mask = (freqs >= 50) & (freqs <= 12000)
    idx = np.argsort(mag[mask])[-12:][::-1]
    fpk = freqs[mask][idx]
    mpk = 20 * np.log10(mag[mask][idx] + 1e-12)
    print(f"\n=== {label} ({path}) ===")
    for f, m in zip(fpk, mpk):
        print(f"  {f:7.1f} Hz: {m:+7.1f} dB")
    # harmonic series of the strongest low peak
    low = freqs[(freqs > 70) & (freqs < 100)]
    if len(low):
        fi = np.argmax(mag[(freqs > 70) & (freqs < 100)])
        f0 = low[fi]
        print(f"  fundamental ~{f0:.1f} Hz, harmonics:")
        for h in range(1, 9):
            b = np.argmin(np.abs(freqs - f0 * h))
            print(f"    h{h} ({f0*h:6.1f} Hz): {20*np.log10(mag[b]+1e-12):+7.1f} dB")

if __name__ == "__main__":
    x = synth_guitar()
    inp = sys.argv[1]
    write_wav(inp, x)
    print("input written", inp)

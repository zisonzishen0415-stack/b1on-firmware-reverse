import numpy as np
import wave

SR = 44100
rng = np.random.default_rng(42)

def ks_note(freq, dur, damp=0.996, brightness=0.5, amp=1.0, detune=0.0):
    """Karplus-Strong plucked string (with a touch of string detune)."""
    n = int(dur * SR)
    if n <= 0:
        return np.zeros(0)
    out = np.zeros(n)
    for f, g in ((freq, amp), (freq * (1.0 + detune), amp * 0.6)):
        N = max(2, int(round(SR / f)))
        buf = rng.normal(0, 1, N)
        # soften the excitation for a less 'plasticky' attack
        buf = np.convolve(buf, np.array([0.25, 0.5, 0.25]), mode="same")
        if brightness < 1.0:
            buf = np.convolve(buf, np.ones(3) / 3.0, mode="same")
        buf = buf / (np.abs(buf).max() + 1e-9) * 0.9
        for i in range(n):
            out[i] += g * buf[0]
            nxt = damp * (buf[0] + buf[1]) * 0.5
            buf = np.roll(buf, -1)
            buf[-1] = nxt
    return out

def add_pick_noise(x, at, sr=SR):
    """small high-frequency pick transient at sample position 'at'."""
    nn = int(0.015 * sr)
    if at + nn >= len(x):
        return
    noise = rng.normal(0, 1, nn)
    # crude highpass
    noise = np.diff(noise, prepend=0.0)
    env = np.exp(-np.arange(nn) / (0.004 * sr))
    x[at:at + nn] += 0.02 * noise * env

def place(out, start, note):
    i0 = int(start * SR)
    seg = note
    end = min(len(out), i0 + len(seg))
    out[i0:end] += seg[:end - i0]

def play_notes(seq, bpm=96):
    beat = 60.0 / bpm
    t = 0.0
    total = sum(d for _, _, d in seq) * beat + 1.0
    out = np.zeros(int(total * SR))
    for f, dur_beats, note_dur in seq:
        place(out, t, ks_note(f, note_dur * beat, damp=0.994, brightness=0.45, amp=0.5))
        add_pick_noise(out, int(t * SR))
        t += dur_beats * beat
    return out

# ------- performance: muted chugs -> open E chord -> lead line -------
E2, B2, E3, Gs3, B3, E4, Gs4, B4, E5 = 82.41, 123.47, 164.81, 207.65, 246.94, 329.63, 415.30, 493.88, 659.26

perf = np.zeros(int(13.0 * SR))
t = 0.0

# 1) palm-muted low-E chugs (short, dull, fast decay)
for k in range(12):
    i0 = int(t * SR)
    seg = ks_note(E2, 0.28, damp=0.985, brightness=0.25, amp=0.65)
    end = min(len(perf), i0 + len(seg))
    perf[i0:end] += seg[:end - i0]
    add_pick_noise(perf, i0)
    t += 0.23

# 2) open E chord strums
chord = [E2, B2, E3, Gs3, B3, E4]
for k in range(3):
    for fi, f in enumerate(chord):
        seg = ks_note(f, 1.6, damp=0.9965, brightness=0.5, amp=0.5, detune=0.0012)
        i0 = int((t + fi * 0.012) * SR)
        end = min(len(perf), i0 + len(seg))
        perf[i0:end] += seg[:end - i0]
    add_pick_noise(perf, int(t * SR))
    t += 0.9

# 3) lead line: E4 -> G#4 -> B4 -> E5 -> B4
lead = [(E4, 0.9, 1.4), (Gs4, 0.9, 1.4), (B4, 0.9, 1.4), (E5, 1.8, 2.4), (B4, 1.8, 2.4)]
for f, d, nd in lead:
    seg = ks_note(f, nd, damp=0.997, brightness=0.55, amp=0.5)
    i0 = int(t * SR)
    end = min(len(perf), i0 + len(seg))
    perf[i0:end] += seg[:end - i0]
    add_pick_noise(perf, i0)
    t += d

perf = perf / np.abs(perf).max() * 0.85
pcm = (np.clip(perf, -1, 1) * 32767).astype(np.int16)
with wave.open(r"C:\Users\29517\Documents\Codex\2026-08-13\https-github-com-zisonzishen0415-stack-ampneve\work\guitar_ks.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote guitar_ks.wav", len(perf) / SR, "s")

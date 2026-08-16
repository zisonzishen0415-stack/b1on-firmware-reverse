/* extreme_probe.c - diagnose extreme-tone buzzing and max-gain distortion depth.
 * Research only. Feeds a 220 Hz sine burst then silence, and measures:
 *   - tail ringing after input stops (self-oscillation / instability check)
 *   - THD-style harmonic content at max gain (distortion depth)
 *   - dominant tail frequency (zero-crossing rate)
 */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f

static void set_all(Ampsim* a, float gain, float master, float level, float bass, float mid, float treble, float voice) {
    Ampsim_set_param(a, AMP_PARAM_INPUT, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_GAIN, gain);
    Ampsim_set_param(a, AMP_PARAM_BASS, bass);
    Ampsim_set_param(a, AMP_PARAM_MID, mid);
    Ampsim_set_param(a, AMP_PARAM_TREBLE, treble);
    Ampsim_set_param(a, AMP_PARAM_MASTER, master);
    Ampsim_set_param(a, AMP_PARAM_LEVEL, level);
    Ampsim_set_param(a, AMP_PARAM_NEVE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_CAB, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_PRESENCE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_VOICE, voice);
    Ampsim_reset(a);
}

/* zero-crossing rate of the tail: proxy for dominant frequency */
static double zcr(const float* x, int n) {
    int crossings = 0;
    for (int i = 1; i < n; ++i)
        if ((x[i - 1] < 0.0f) != (x[i] < 0.0f)) ++crossings;
    return (double)crossings / (n - 1) * (SR / 2.0);
}

/* harmonic content of a steady sine: ratio of total energy above 2x fundamental */
static double harmonics_above(const float* x, int n) {
    /* crude: count zero crossings *within* the sine window to get f0, then
     * do a Goertzel-free approach: high-pass at 2.5*f0 via a simple 2-pole
     * highpass and measure energy ratio. */
    (void)x; (void)n;
    return 0.0;
}

static void run_burst_tail(Ampsim* a, const char* label, float* tail, int* tail_n) {
    float o = 0.0f;
    /* 0.4 s sine burst (220 Hz, amp 0.25 ~ -12 dBFS) */
    for (int i = 0; i < (int)(0.4f * SR); ++i) {
        float t = (float)i / SR;
        Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
    }
    /* 0.6 s silence tail */
    int n = (int)(0.6f * SR);
    for (int i = 0; i < n; ++i) {
        Ampsim_process(a, 0.0f, &o);
        tail[i] = o;
    }
    *tail_n = n;
    double pk = 0.0, e = 0.0;
    for (int i = 0; i < n; ++i) {
        double v = fabs(tail[i]);
        if (v > pk) pk = v;
        e += (double)tail[i] * tail[i];
    }
    printf("%-38s tail_peak=%.6f tail_rms=%.1fdB zcr=%.0fHz\n",
           label, pk, 20.0 * log10(sqrt(e / n)), zcr(tail, n));
}

int main(void) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), SR);
    if (!a) return 1;

    float tail[26460];
    int tail_n;

    printf("=== tail ringing at extreme tone settings (gain=1 master=1 level=1) ===\n");
    const char* tone_names[8] = {
        "flat 0.5/0.5/0.5", "bass=1", "mid=1", "treble=1",
        "bass=1 mid=1", "bass=1 treble=1", "mid=1 treble=1", "all=1"
    };
    float bm[8] = {0.5f,1,0.5f,0.5f,1,1,0.5f,1};
    float mm[8] = {0.5f,0.5f,1,0.5f,1,0.5f,1,1};
    float tm[8] = {0.5f,0.5f,0.5f,1,0.5f,1,1,1};
    for (int i = 0; i < 8; ++i) {
        set_all(a, 1.0f, 1.0f, 1.0f, bm[i], mm[i], tm[i], 0.0f);
        run_burst_tail(a, tone_names[i], tail, &tail_n);
    }

    printf("\n=== max-gain distortion depth (220 Hz, amp=0.25, flat tone, master/level=1) ===\n");
    for (int v = 0; v < 2; ++v) {
        set_all(a, 1.0f, 1.0f, 1.0f, 0.5f, 0.5f, 0.5f, (float)v);
        /* capture steady output, measure zero crossings & peak shape */
        float o = 0.0f;
        for (int i = 0; i < (int)(0.5f * SR); ++i) {
            float t = (float)i / SR;
            Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
        }
        /* record 2 periods for shape analysis */
        float buf[4096];
        for (int i = 0; i < 4096; ++i) {
            float t = (float)((int)(0.5f * SR) + i) / SR;
            Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
            buf[i] = o;
        }
        double flat_top = 0.0;
        int clamped = 0;
        float hi = -1e9f, lo = 1e9f;
        for (int i = 0; i < 4096; ++i) {
            if (buf[i] > hi) hi = buf[i];
            if (buf[i] < lo) lo = buf[i];
            if (buf[i] > 0.62f || buf[i] < -0.62f) ++clamped;
        }
        flat_top = hi - lo;
        printf("voice=%d: peak=%.3f  flatness(hi-lo)=%.3f  samples_above_0.62=%d/4096  zcr=%.0fHz\n",
               v, hi, flat_top, clamped, zcr(buf, 4096));
    }

    /* harmonic analysis via Goertzel on steady sine: 1st, 2nd, 3rd, 5th, 7th */
    printf("\n=== harmonic magnitudes at max gain (220 Hz, flat tone) ===\n");
    for (int v = 0; v < 2; ++v) {
        set_all(a, 1.0f, 1.0f, 1.0f, 0.5f, 0.5f, 0.5f, (float)v);
        float o = 0.0f;
        int warm = (int)(0.5f * SR);
        int n = 8192;
        float* s = (float*)calloc(n, sizeof(float));
        for (int i = 0; i < warm + n; ++i) {
            float t = (float)i / SR;
            Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
            if (i >= warm) s[i - warm] = o;
        }
        printf("voice=%d:", v);
        for (int h = 1; h <= 7; h += 2) {
            double re = 0.0, im = 0.0;
            double w = 2.0 * 3.14159265358979 * h * 220.0 / SR;
            for (int i = 0; i < n; ++i) {
                re += s[i] * cos(w * i);
                im += s[i] * sin(w * i);
            }
            double mag = 2.0 * sqrt(re * re + im * im) / n;
            printf(" h%d=%.1f", h, 20.0 * log10(mag > 1e-9 ? mag : 1e-9));
        }
        printf(" dB\n");
        free(s);
    }

    free(mem);
    return 0;
}

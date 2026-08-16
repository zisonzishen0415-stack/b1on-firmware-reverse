/* spectrum_probe.c - locate resonant peaks at extreme tone settings. */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f

static void set_all(Ampsim* a, float bass, float mid, float treble, float voice) {
    Ampsim_set_param(a, AMP_PARAM_INPUT, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_GAIN, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_BASS, bass);
    Ampsim_set_param(a, AMP_PARAM_MID, mid);
    Ampsim_set_param(a, AMP_PARAM_TREBLE, treble);
    Ampsim_set_param(a, AMP_PARAM_MASTER, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_LEVEL, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_NEVE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_CAB, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_PRESENCE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_VOICE, voice);
    Ampsim_reset(a);
}

static double goertzel(const float* x, int n, double freq) {
    double w = 2.0 * 3.14159265358979 * freq / SR;
    double c = 2.0 * cos(w);
    double s0 = 0.0, s1 = 0.0, s2 = 0.0;
    for (int i = 0; i < n; ++i) {
        s0 = x[i] + c * s1 - s2;
        s2 = s1;
        s1 = s0;
    }
    double re = s1 - s2 * cos(w);
    double im = s2 * sin(w);
    return 2.0 * sqrt(re * re + im * im) / n;
}

static void spectrum(const char* label, float bass, float mid, float treble, float voice) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), SR);
    set_all(a, bass, mid, treble, voice);
    int warm = (int)(0.5f * SR);
    int n = 16384;
    float* s = (float*)calloc(n, sizeof(float));
    float o = 0.0f;
    for (int i = 0; i < warm + n; ++i) {
        float t = (float)i / SR;
        Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
        if (i >= warm) s[i - warm] = o;
    }
    printf("\n=== %s (voice=%d) top peaks 200Hz..12kHz ===\n", label, (int)voice);
    /* collect top peaks */
    float peaks[12][2];
    double freqs[120];
    for (int f = 0; f < 120; ++f) {
        double freq = 200.0 + f * 100.0;
        freqs[f] = 20.0 * log10(goertzel(s, n, freq) + 1e-12);
    }
    for (int k = 0; k < 12; ++k) {
        int bi = 0;
        for (int f = 1; f < 120; ++f) if (freqs[f] > freqs[bi]) bi = f;
        peaks[k][0] = (float)(200.0 + bi * 100.0);
        peaks[k][1] = (float)freqs[bi];
        freqs[bi] = -1e9;
    }
    for (int k = 0; k < 12; ++k)
        printf("  %.0f Hz: %+.1f dB\n", peaks[k][0], peaks[k][1]);
    free(s);
    free(mem);
}

int main(void) {
    spectrum("flat", 0.5f, 0.5f, 0.5f, 0.0f);
    spectrum("mid=1 treble=1", 0.5f, 1.0f, 1.0f, 0.0f);
    spectrum("all=1", 1.0f, 1.0f, 1.0f, 0.0f);
    spectrum("bass=1 treble=1", 1.0f, 0.5f, 1.0f, 0.0f);
    spectrum("treble=1 only", 0.5f, 0.5f, 1.0f, 0.0f);
    spectrum("flat Emo", 0.5f, 0.5f, 0.5f, 1.0f);
    spectrum("mid=1 treble=1 Emo", 0.5f, 1.0f, 1.0f, 1.0f);
    return 0;
}

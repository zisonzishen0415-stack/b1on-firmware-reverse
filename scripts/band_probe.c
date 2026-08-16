/* band_probe.c - which frequency band is the harshness in? */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f

static double band_energy(const float* x, int n, double lo, double hi) {
    /* simple 2nd-order bandpass energy via Goertzel grid */
    double e = 0.0;
    int bins = 24;
    for (int b = 0; b < bins; ++b) {
        double f = lo + (hi - lo) * (b + 0.5) / bins;
        double w = 2.0 * 3.14159265358979 * f / SR;
        double c = 2.0 * cos(w);
        double s0 = 0.0, s1 = 0.0, s2 = 0.0;
        for (int i = 0; i < n; ++i) {
            s0 = x[i] + c * s1 - s2;
            s2 = s1;
            s1 = s0;
        }
        double re = s1 - s2 * cos(w);
        double im = s2 * sin(w);
        e += (re * re + im * im);
    }
    return e;
}

int main(void) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), SR);
    if (!a) return 1;
    Ampsim_set_param(a, AMP_PARAM_INPUT, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_GAIN, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_BASS, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_MID, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_TREBLE, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_MASTER, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_LEVEL, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_NEVE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_CAB, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_PRESENCE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_VOICE, 0.0f);

    int warm = (int)(0.5f * SR);
    int n = 16384;
    float* s = (float*)malloc(n * sizeof(float));
    float o = 0.0f;
    for (int i = 0; i < warm + n; ++i) {
        float t = (float)i / SR;
        Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
        if (i >= warm) s[i - warm] = o;
    }
    const struct { double lo, hi; const char* name; } bands[] = {
        { 220.0, 660.0, "fund+2nd" }, { 660.0, 1320.0, "3rd-6th" },
        { 1320.0, 3000.0, "6th-13th" }, { 3000.0, 6000.0, "3-6k" },
        { 6000.0, 10000.0, "6-10k" }, { 10000.0, 20000.0, "10-20k" }
    };
    printf("max-gain output band energies (dB rel full):\n");
    double full = 0.0;
    for (int b = 0; b < 6; ++b) full += band_energy(s, n, bands[b].lo, bands[b].hi);
    for (int b = 0; b < 6; ++b) {
        double e = band_energy(s, n, bands[b].lo, bands[b].hi);
        printf("  %-10s %+6.1f dB\n", bands[b].name, 10.0 * log10(e / full));
    }
    free(s);
    free(mem);
    return 0;
}

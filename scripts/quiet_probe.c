/* quiet_probe.c - does max gain distort quiet inputs? */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f

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

    const float amps[5] = { 0.25f, 0.125f, 0.06f, 0.03f, 0.015f };
    const char* labels[5] = { "-12dBFS", "-18dBFS", "-24dBFS", "-30dBFS", "-36dBFS" };
    printf("max gain (g=1 m=1), 220 Hz sine:\n");
    for (int k = 0; k < 5; ++k) {
        Ampsim_reset(a);
        int warm = (int)(0.5f * SR);
        int n = 8192;
        float* s = (float*)malloc(n * sizeof(float));
        float o = 0.0f;
        double sum2 = 0.0;
        for (int i = 0; i < warm + n; ++i) {
            float t = (float)i / SR;
            Ampsim_process(a, amps[k] * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
            if (i >= warm) { s[i - warm] = o; sum2 += (double)o * o; }
        }
        double rms = sqrt(sum2 / n);
        double h1 = goertzel(s, n, 220.0);
        double h3 = goertzel(s, n, 660.0);
        printf("  %-8s in=%.4f rms=%+.1fdB h1=%+.1f h3=%+.1f (h3-h1=%+.1f)\n",
               labels[k], amps[k], 20.0 * log10(rms + 1e-12),
               20.0 * log10(h1 + 1e-12), 20.0 * log10(h3 + 1e-12),
               20.0 * log10(h3 / (h1 > 1e-9 ? h1 : 1e-9)));
        free(s);
    }
    free(mem);
    return 0;
}

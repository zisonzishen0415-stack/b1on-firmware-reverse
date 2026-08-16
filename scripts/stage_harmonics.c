/* stage_harmonics.c - harmonic magnitudes at each chain stage (research). */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f

void Ampsim_process_stage(Ampsim* a, float in, float* out, float* s0, float* s1, float* s2, float* s3, float* s4);

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
    Ampsim_reset(a);

    int warm = (int)(0.5f * SR);
    int n = 8192;
    float* st[5];
    for (int k = 0; k < 5; ++k) st[k] = (float*)calloc(n, sizeof(float));
    float o = 0.0f, s0, s1, s2, s3, s4;
    for (int i = 0; i < warm + n; ++i) {
        float t = (float)i / SR;
        Ampsim_process_stage(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * t),
                             &o, &s0, &s1, &s2, &s3, &s4);
        if (i >= warm) {
            st[0][i - warm] = s0;  /* after gain stage */
            st[1][i - warm] = s1;  /* after power stage */
            st[2][i - warm] = s2;  /* after transformer */
            st[3][i - warm] = s3;  /* after cab IR */
            st[4][i - warm] = s4;  /* final */
        }
    }
    const char* names[5] = { "after gain", "after power", "after xformer", "after cab", "final" };
    for (int k = 0; k < 5; ++k) {
        printf("%-14s", names[k]);
        for (int h = 1; h <= 11; h += 2) {
            double m = goertzel(st[k], n, 220.0 * h);
            printf(" h%d=%+.1f", h, 20.0 * log10(m + 1e-12));
        }
        printf("\n");
    }
    for (int k = 0; k < 5; ++k) free(st[k]);
    free(mem);
    return 0;
}

/* block_reset_probe.c - verify the per-block set_param state-reset hypothesis.
 * Mimics the VST: calls Ampsim_set_param(BASS/MID/TREBLE) every 128 samples
 * (one audio block), which currently zeroes the tone biquad states.
 * Measures sample-to-sample discontinuities at block boundaries. */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define SR 44100.0f
#define BLOCK 128

static void set_base(Ampsim* a, float bass, float mid, float treble) {
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
    Ampsim_set_param(a, AMP_PARAM_VOICE, 0.0f);
    Ampsim_reset(a);
}

static double max_step(const float* x, int n, int* where) {
    double m = 0.0;
    *where = 0;
    for (int i = 1; i < n; ++i) {
        double d = fabs((double)x[i] - x[i - 1]);
        if (d > m) { m = d; *where = i; }
    }
    return m;
}

int main(void) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    int n = (int)(2.0f * SR);
    float* out = (float*)calloc(n, sizeof(float));
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!out || !mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), SR);
    if (!a) return 1;

    const char* names[3] = { "flat 0.5/0.5/0.5", "bass=1 mid=0 treble=1", "mid=1 treble=1" };
    float b[3] = {0.5f, 1.0f, 0.5f};
    float m[3] = {0.5f, 0.0f, 1.0f};
    float t[3] = {0.5f, 1.0f, 1.0f};

    for (int k = 0; k < 3; ++k) {
        /* A: params set once */
        set_base(a, b[k], m[k], t[k]);
        float o = 0.0f;
        for (int i = 0; i < n; ++i) {
            float tt = (float)i / SR;
            Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * tt), &o);
            out[i] = o;
        }
        int wa; double sa = max_step(out, n, &wa);

        /* B: params re-set every block (VST behavior) */
        set_base(a, b[k], m[k], t[k]);
        o = 0.0f;
        for (int i = 0; i < n; ++i) {
            float tt = (float)i / SR;
            if ((i % BLOCK) == 0) {
                Ampsim_set_param(a, AMP_PARAM_BASS, b[k]);
                Ampsim_set_param(a, AMP_PARAM_MID, m[k]);
                Ampsim_set_param(a, AMP_PARAM_TREBLE, t[k]);
            }
            Ampsim_process(a, 0.25f * sinf(2.0f * 3.14159265f * 220.0f * tt), &o);
            out[i] = o;
        }
        int wb; double sb = max_step(out, n, &wb);
        /* boundary step: jump exactly at a block start */
        double bj = fabs((double)out[BLOCK] - out[BLOCK - 1]);
        printf("%-28s once: max_step=%.6f  per-block: max_step=%.6f  boundary_jump=%.6f\n",
               names[k], sa, sb, bj);
    }
    free(out);
    free(mem);
    return 0;
}

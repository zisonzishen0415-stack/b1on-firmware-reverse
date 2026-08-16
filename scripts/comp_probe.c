/* comp_probe.c - compression ratio at arbitrary gain/master/level. */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static double run_rms(Ampsim* a, float amp, unsigned n, unsigned skip) {
    double sum2 = 0.0;
    unsigned cnt = 0;
    float o = 0.0f;
    for (unsigned i = 0; i < n; ++i) {
        float t = (float)i / 44100.0f;
        float in = amp * sinf(2.0f * 3.14159265f * 220.0f * t);
        Ampsim_process(a, in, &o);
        if (i >= skip) { sum2 += (double)o * o; ++cnt; }
    }
    return cnt ? sqrt(sum2 / cnt) : 0.0;
}

int main(int argc, char** argv) {
    float gain = argc > 1 ? (float)atof(argv[1]) : 0.8f;
    float master = argc > 2 ? (float)atof(argv[2]) : 0.8f;
    float level = argc > 3 ? (float)atof(argv[3]) : 0.8f;
    float voice = argc > 4 ? (float)atof(argv[4]) : 0.0f;
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), 44100.0f);
    if (!a) return 1;
    Ampsim_set_param(a, AMP_PARAM_INPUT, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_GAIN, gain);
    Ampsim_set_param(a, AMP_PARAM_BASS, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_MID, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_TREBLE, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_MASTER, master);
    Ampsim_set_param(a, AMP_PARAM_LEVEL, level);
    Ampsim_set_param(a, AMP_PARAM_NEVE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_CAB, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_PRESENCE, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_VOICE, voice);
    Ampsim_reset(a);
    double r_lo = run_rms(a, 0.15f, 32768u, 16384u);
    Ampsim_reset(a);
    double r_hi = run_rms(a, 0.50f, 32768u, 16384u);
    printf("gain=%.2f master=%.2f level=%.2f voice=%.0f: soft=%+.1fdB loud=%+.1fdB ratio=%.3f\n",
           gain, master, level, voice, 20.0 * log10(r_lo), 20.0 * log10(r_hi), r_hi / (r_lo > 1e-9 ? r_lo : 1e-9));
    free(mem);
    return 0;
}

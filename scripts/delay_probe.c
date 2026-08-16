/* delay_probe.c - measure the wet path's latency (impulse response). */
#include "ampsim.h"
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), 44100.0f);
    if (!a) return 1;
    Ampsim_set_param(a, AMP_PARAM_INPUT, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_GAIN, 0.2f);   /* clean path */
    Ampsim_set_param(a, AMP_PARAM_MASTER, 0.5f);
    Ampsim_set_param(a, AMP_PARAM_LEVEL, 1.0f);
    Ampsim_reset(a);
    float o = 0.0f;
    printf("impulse response (first 40 samples):\n");
    for (int i = 0; i < 64; ++i) {
        Ampsim_process(a, i == 0 ? 1.0f : 0.0f, &o);
        if (i < 40) printf("  %2d: %+.4f\n", i, o);
    }
    free(mem);
    return 0;
}

/* gain_probe.c - measure AmpNeve gain behavior (research only, not part of repo). */
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

static void set_base(Ampsim* a, float gain, float master, float level, float voice) {
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
}

int main(void) {
    uint32_t need = Ampsim_state_size();
    size_t nf = (need + sizeof(float) - 1u) / sizeof(float);
    float* mem = (float*)calloc(nf, sizeof(float));
    if (!mem) return 1;
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), 44100.0f);
    if (!a) return 1;

    const char* voices[] = { "Nashville", "Emo/Edge" };

    /* 1) gain-knob sweep at small-signal (linear-ish) input, level=1 */
    printf("=== gain knob sweep (small input amp=0.02, master=0.5, level=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        printf("%-9s:", voices[v]);
        for (int gi = 0; gi <= 10; ++gi) {
            float g = gi / 10.0f;
            set_base(a, g, 0.5f, 1.0f, (float)v);
            double r = run_rms(a, 0.02f, 32768u, 16384u);
            printf(" %+.1f", 20.0 * log10(r));
        }
        printf("  dB\n");
    }

    /* 2) max-settings output for realistic DI levels (-18/-12/-6 dBFS) */
    printf("\n=== max settings (input=1 gain=1 master=1 level=1) ===\n");
    for (int v = 0; v < 2; ++v) {
        set_base(a, 1.0f, 1.0f, 1.0f, (float)v);
        printf("%-9s:", voices[v]);
        for (int ai = 0; ai < 3; ++ai) {
            float amp = ai == 0 ? 0.125f : (ai == 1 ? 0.25f : 0.5f);
            double r = run_rms(a, amp, 32768u, 16384u);
            printf("  amp=%.3f rms=%+.1fdB", amp, 20.0 * log10(r));
        }
        printf("\n");
    }

    /* 3) saturation depth: gain=1 output vs gain=0 output at -12 dBFS input */
    printf("\n=== saturation depth (input amp=0.25, master=0.5, level=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        double r0, r1;
        set_base(a, 0.0f, 0.5f, 1.0f, (float)v); r0 = run_rms(a, 0.25f, 32768u, 16384u);
        set_base(a, 1.0f, 0.5f, 1.0f, (float)v); r1 = run_rms(a, 0.25f, 32768u, 16384u);
        printf("%-9s: gain0=%+.1fdB gain1=%+.1fdB delta=%+.1fdB\n",
               voices[v], 20.0 * log10(r0), 20.0 * log10(r1), 20.0 * log10(r1 / r0));
    }

    /* 4) master-knob sweep: power-stage drive effect at fixed preamp gain */
    printf("\n=== master sweep (gain=0.6, input amp=0.25, level=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        printf("%-9s:", voices[v]);
        for (int mi = 0; mi <= 10; ++mi) {
            float m = mi / 10.0f;
            set_base(a, 0.6f, m, 1.0f, (float)v);
            double r = run_rms(a, 0.25f, 32768u, 16384u);
            printf(" %+.1f", 20.0 * log10(r));
        }
        printf("  dB\n");
    }

    /* 5) power-stage compression: master=1 output vs input level
     *    (ratio of loud/soft outputs: high ratio = less compression) */
    printf("\n=== power-stage compression (gain=0.6, master=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        double r_lo, r_hi;
        set_base(a, 0.6f, 1.0f, 1.0f, (float)v);
        r_lo = run_rms(a, 0.10f, 32768u, 16384u);
        r_hi = run_rms(a, 0.50f, 32768u, 16384u);
        printf("%-9s: soft=%+.1fdB loud=%+.1fdB ratio=%.2f\n",
               voices[v], 20.0 * log10(r_lo), 20.0 * log10(r_hi), r_hi / (r_lo > 1e-9 ? r_lo : 1e-9));
    }

    free(mem);
    return 0;
}

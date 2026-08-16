/* tone_eval.c - serious tone evaluation of the AmpNeve core. */
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

typedef struct {
    double rms_db, peak_db, h1_db, h3_db, h5_db;
} Eval;

static void eval(Ampsim* a, float amp, int n, int warm, Eval* e) {
    float* s = (float*)malloc(n * sizeof(float));
    float o = 0.0f;
    double sum2 = 0.0;
    float pk = 0.0f;
    for (int i = 0; i < warm + n; ++i) {
        float t = (float)i / SR;
        Ampsim_process(a, amp * sinf(2.0f * 3.14159265f * 220.0f * t), &o);
        if (i >= warm) {
            s[i - warm] = o;
            sum2 += (double)o * o;
            float v = o < 0.0f ? -o : o;
            if (v > pk) pk = v;
        }
    }
    e->rms_db = 20.0 * log10(sqrt(sum2 / n) + 1e-12);
    e->peak_db = 20.0 * log10(pk + 1e-12);
    e->h1_db = 20.0 * log10(goertzel(s, n, 220.0) + 1e-12);
    e->h3_db = 20.0 * log10(goertzel(s, n, 660.0) + 1e-12);
    e->h5_db = 20.0 * log10(goertzel(s, n, 1100.0) + 1e-12);
    free(s);
}

static void set_flat(Ampsim* a, float gain, float master, float level, float voice) {
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
    Ampsim* a = Ampsim_init(mem, (uint32_t)(nf * sizeof(float)), SR);
    if (!a) return 1;
    Eval e;

    printf("=== A. gain sweep @ -12dBFS DI (master=0.5 level=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        printf("voice=%d: ", v);
        for (int gi = 0; gi <= 10; ++gi) {
            set_flat(a, gi / 10.0f, 0.5f, 1.0f, (float)v);
            eval(a, 0.25f, 8192, 16384, &e);
            printf("g%.1f:r%+5.1f/p%+5.1f/h3%+5.1f  ", gi / 10.0f, e.rms_db, e.peak_db, e.h3_db);
        }
        printf("\n");
    }

    printf("\n=== B. gain sweep @ max master (master=1.0 level=1.0) ===\n");
    for (int v = 0; v < 2; ++v) {
        printf("voice=%d: ", v);
        for (int gi = 0; gi <= 10; ++gi) {
            set_flat(a, gi / 10.0f, 1.0f, 1.0f, (float)v);
            eval(a, 0.25f, 8192, 16384, &e);
            printf("g%.1f:r%+5.1f/h3%+5.1f/h5%+5.1f  ", gi / 10.0f, e.rms_db, e.h3_db, e.h5_db);
        }
        printf("\n");
    }

    printf("\n=== C. default settings loudness (gain=0.45 master=0.5 level=0.8) ===\n");
    for (int v = 0; v < 2; ++v) {
        set_flat(a, 0.45f, 0.5f, 0.8f, (float)v);
        eval(a, 0.25f, 8192, 16384, &e);
        printf("voice=%d: rms=%+.1f peak=%+.1f h1=%+.1f h3=%+.1f\n",
               v, e.rms_db, e.peak_db, e.h1_db, e.h3_db);
    }

    printf("\n=== D. tone knob response (gain=0.45 master=0.5 level=0.8, clean-ish) ===\n");
    {
        const float freqs[5] = { 100.0f, 220.0f, 850.0f, 3000.0f, 5000.0f };
        const char* knobs[3] = { "bass", "mid", "treble" };
        for (int k = 0; k < 3; ++k) {
            for (int ki = 0; ki < 3; ++ki) {
                float kv = ki == 0 ? 0.0f : (ki == 1 ? 0.5f : 1.0f);
                set_flat(a, 0.45f, 0.5f, 0.8f, 0.0f);
                if (k == 0) Ampsim_set_param(a, AMP_PARAM_BASS, kv);
                if (k == 1) Ampsim_set_param(a, AMP_PARAM_MID, kv);
                if (k == 2) Ampsim_set_param(a, AMP_PARAM_TREBLE, kv);
                Ampsim_reset(a);
                printf("%s=%+.1f:", knobs[k], kv);
                for (int f = 0; f < 5; ++f) {
                    Ampsim_reset(a);
                    float* s = (float*)malloc(8192 * sizeof(float));
                    float o = 0.0f;
                    for (int i = 0; i < 16384 + 8192; ++i) {
                        float t = (float)i / SR;
                        Ampsim_process(a, 0.05f * sinf(2.0f * 3.14159265f * freqs[f] * t), &o);
                        if (i >= 16384) s[i - 16384] = o;
                    }
                    double m = goertzel(s, 8192, freqs[f]);
                    printf(" %4.0fHz:%+5.1f", freqs[f], 20.0 * log10(m + 1e-12));
                    free(s);
                }
                printf("\n");
            }
        }
    }

    printf("\n=== E. extreme tone (bass=1 mid=1 treble=1) @ max gain, buzz check ===\n");
    set_flat(a, 1.0f, 1.0f, 1.0f, 0.0f);
    Ampsim_set_param(a, AMP_PARAM_BASS, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_MID, 1.0f);
    Ampsim_set_param(a, AMP_PARAM_TREBLE, 1.0f);
    Ampsim_reset(a);
    eval(a, 0.25f, 8192, 16384, &e);
    printf("all=1: rms=%+.1f h1=%+.1f h3=%+.1f h5=%+.1f\n", e.rms_db, e.h1_db, e.h3_db, e.h5_db);

    free(mem);
    return 0;
}

/*
 * ampsim_zdl_inplace.c -- AmpNeve as an in-place replacement for a STOCK
 * B1on ZDL (MODREV.ZDL from firmware 1.30).
 *
 * Why in-place: B1on gives NEW/custom ZDL identities only a tiny ctx[3]
 * arena - any state write >= ~1 KB freezes the pedal (probe-proven). The
 * stock MODREV identity gets the real host-managed ctx[3] arena
 * ({base,end,span}, used by the stock reverb for its delay lines), so we
 * keep the file identity 100% stock and swap ONLY the .audio code bytes.
 *
 * Buffer conventions follow the stock B1on big-state effects (DELAY and
 * MODREV both do this): ctx[5] is the in-place signal block (L at [0..7],
 * R at [8..15]) - read as input at entry, written back as output. ctx[12]
 * is the per-sample magic source (dry/current-sample register), ctx[11]
 * points to the magic destination; both are host postboxes, NOT audio
 * input. Reading ctx[12] as the audio input (v1) processed the wrong
 * signal and crackled.
 *
 * The DSP is the same core/ampsim.c as the VST, compiled with
 * AMPNEVE_NO_IR for phase 1 (the 16 KB sampled IRs do not fit the stock
 * .audio section; phase 2 restores them by growing .const).
 *
 * Knob mapping onto the stock MODREV params (labels are patched in the
 * stock .const with same-length strings):
 *   Depth -> Gain, Decay -> Mastr, Rate -> Bass, Tone -> Mid,
 *   PreD -> Treb, Level -> Level, Tail -> Neve
 */
#include <stdint.h>

#define AMPNEVE_NO_IR
#define AMPNEVE_ZDL_STATIC
#include "../core/ampsim.c"

#define AMP_DO_PRAGMA(x) _Pragma(#x)
#define AMP_EXPAND_PRAGMA(x) AMP_DO_PRAGMA(x)
#define AMP_CODE_SECTION(func) AMP_EXPAND_PRAGMA(CODE_SECTION(func, ".audio"))
#define AMP_ALWAYS_INLINE(func) AMP_EXPAND_PRAGMA(FUNC_ALWAYS_INLINE(func))
AMP_CODE_SECTION(Fx_AMP_AmpNeve)

#define ZDL_PTR(type, word) ((type)(uintptr_t)(word))

#define AMP_MAGIC   0x414D504Eu   /* 'AMPN' */
#define AMP_VERSION 1u
#define AMP_RAW_MAX 0.14f
#define AMP_RAW_TO_NORM 7.1428571f

/* In-place build, no-IR phase: the preamp state is ~130 floats/channel.
 * 256 floats/channel (~2 KB total) is plenty and makes the host-arena
 * bounds check pass on even a small arena. Phase 2 (with the 2048-tap
 * sampled IRs) needs the full 4352-float block. */
#ifdef AMPNEVE_NO_IR
#define AMP_STATE_FLOATS 256u
#else
#define AMP_STATE_FLOATS 4352u
#endif

typedef struct AmpZdlState {
    uint32_t magic;
    uint32_t version;
    uint32_t initialized;
    uint32_t reserved;
    float memL[AMP_STATE_FLOATS];
    float memR[AMP_STATE_FLOATS];
} AmpZdlState;

/* MODREV stock param slots (1-based knobs live at params[4+i]). */
#define KNOB_GAIN   5
#define KNOB_MASTER 6
#define KNOB_BASS   7
#define KNOB_MID    8
#define KNOB_TREBLE 9
#define KNOB_LEVEL  10
#define KNOB_NEVE   11

#define DEF_GAIN    0.35f
#define DEF_MASTER  0.55f
#define DEF_BASS    0.50f
#define DEF_MID     0.50f
#define DEF_TREBLE  0.50f
#define DEF_LEVEL   0.75f
#define DEF_NEVE    1.00f

AMP_ALWAYS_INLINE(amp_align4)
static inline uintptr_t amp_align4(uintptr_t x)
{
    return (x + 3u) & ~(uintptr_t)3u;
}

AMP_ALWAYS_INLINE(amp_clamp01)
static inline float amp_clamp01(float x)
{
    if (x < 0.0f) return 0.0f;
    if (x > 1.0f) return 1.0f;
    return x;
}

/* Normalize a host param value (0..100 raw, ~0.14 scaled, or 0..1) to
 * 0..1, mirroring the OTT param_norm pattern. */
AMP_ALWAYS_INLINE(amp_param_norm)
static inline float amp_param_norm(float raw, float fallback_norm)
{
    if (raw != raw) return amp_clamp01(fallback_norm);          /* NaN */
    if (raw < 0.0f) return amp_clamp01(fallback_norm);
    if (raw <= 0.0001f) return 0.0f;
    if (raw <= (AMP_RAW_MAX * 1.1f)) return amp_clamp01(raw * AMP_RAW_TO_NORM);
    if (raw <= 1.0f) return amp_clamp01(raw);
    if (raw <= 100.0f) return amp_clamp01(raw * 0.01f);
    return amp_clamp01(fallback_norm);
}

AMP_ALWAYS_INLINE(amp_zdl_init)
static inline void amp_zdl_init(AmpZdlState *st)
{
    unsigned i;
    for (i = 0; i < AMP_STATE_FLOATS; ++i) {
        st->memL[i] = 0.0f;
    }
    if (Ampsim_init(&st->memL, AMP_STATE_FLOATS * sizeof(float), 44100.0f) == 0)
        return;
    Ampsim_set_param((Ampsim *)&st->memL, AMP_PARAM_PRESENCE, 0.85f);
    st->magic = AMP_MAGIC;
    st->version = AMP_VERSION;
    st->initialized = 1u;
    st->reserved = 0u;
}

void Fx_AMP_AmpNeve(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    float *sig    = ZDL_PTR(float *, ctx[5]);   /* in-place L[0..7] R[8..15] */
    unsigned int *magicSrc = ZDL_PTR(unsigned int *, ctx[12]);
    unsigned int **magic = ZDL_PTR(unsigned int **, ctx[11]);
    unsigned int k;

    if (params[0] < 0.5f) {
        /* effect off: host signal already sits in ctx[5], leave it */
        for (k = 0; k < 8; ++k) *magic[0] = magicSrc[k];
        return;
    }

    /* lazy arena init (host-managed ctx[3] descriptor, stock MODREV gets
     * a real multi-hundred-KB region - bounds are still checked) */
    {
        volatile unsigned int *desc = ZDL_PTR(volatile unsigned int *, ctx[3]);
        uintptr_t base = 0u, end = 0u;
        unsigned int span = 0u;
        AmpZdlState *st;
        if (!desc) return;
        base = (uintptr_t)desc[0];
        end  = (uintptr_t)desc[1];
        span = desc[2];
        if (base == 0u || end <= base) return;
        if ((base & 3u) != 0u || (end & 3u) != 0u || (span & 3u) != 0u) return;
        if ((end - base) < sizeof(AmpZdlState)) return;
        if (span < (unsigned int)(end - base)) return;
        st = (AmpZdlState *)amp_align4(base);
        if ((uintptr_t)st + sizeof(AmpZdlState) > end) return;
        if (st->magic != AMP_MAGIC || st->version != AMP_VERSION ||
            !st->initialized) {
            amp_zdl_init(st);
            return;   /* first block just sets up state */
        }

        {
            float bass   = amp_param_norm(params[KNOB_BASS],   DEF_BASS);
            float mid    = amp_param_norm(params[KNOB_MID],    DEF_MID);
            float treble = amp_param_norm(params[KNOB_TREBLE], DEF_TREBLE);
            float gain   = amp_param_norm(params[KNOB_GAIN],   DEF_GAIN);
            float master = amp_param_norm(params[KNOB_MASTER], DEF_MASTER);
            float level  = amp_param_norm(params[KNOB_LEVEL],  DEF_LEVEL);
            float neve   = amp_param_norm(params[KNOB_NEVE],   DEF_NEVE);
            Ampsim *a = (Ampsim *)&st->memL;
            Ampsim_set_param(a, AMP_PARAM_BASS, bass);
            Ampsim_set_param(a, AMP_PARAM_MID, mid);
            Ampsim_set_param(a, AMP_PARAM_TREBLE, treble);
            Ampsim_set_param(a, AMP_PARAM_GAIN, gain);
            Ampsim_set_param(a, AMP_PARAM_MASTER, master);
            Ampsim_set_param(a, AMP_PARAM_LEVEL, level);
            Ampsim_set_param(a, AMP_PARAM_NEVE, neve);

            for (k = 0; k < 8; ++k) {
                float o;
                *magic[0] = magicSrc[k];
                Ampsim_process(a, sig[k], &o);
                sig[k] = o;
                sig[8u + k] = o;
            }
        }
    }
}

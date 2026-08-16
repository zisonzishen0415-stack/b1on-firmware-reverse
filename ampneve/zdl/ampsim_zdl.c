/*
 * ampsim_zdl.c -- AmpNeve for the Zoom MultiStomp (ZDL).
 *
 * Wraps the core (core/ampsim.c, inlined below) in the Zoom runtime ABI:
 *   - persistent state lives in the host-managed ctx[3] arena (2 x 2304
 *     floats, ~18.4 KB total - the arena is hundreds of KB)
 *   - params come from the params[] table (see ampsim_zdl_params.h)
 *   - block processing: 8 samples L + 8 samples R, channel-interleaved
 *   - ctx[11]/ctx[12] magic shuttle preserved
 *
 * Nine knobs across three LineSel pages (mirrors the VST):
 * P1: Bass / Mid / Treble,  P2: Gain / Master / Level,
 * P3: Neve / Cabtype (1x12/2x12/4x12) / Input.
 * Presence is fixed at 0.85 (no knob); single Nashville voice.
 *
 * Build (needs TI C6000 CGT, see zdl/README.md):
 *   cl6x --c99 --opt_level=2 -mv6740 --abi=eabi \
 *        --mem_model:data=far --include_path=<repo>/core \
 *        -c ampsim_zdl.c -o ampsim_zdl.obj
 *   python3 build.py
 */
#include <stdint.h>

/* inline the ZDL-safe core (single-obj build: the Zoom linker takes one .obj) */
#include "../core/ampsim.c"

#include "ampsim_zdl_params.h"

/* Hardware builds may expose a subset of the 9 DSP params (the B1on host
 * only fully drives 2-4 knobs on custom ZDLs - GAIN/OTT work, 9-knob
 * ToTape9/TEcho4 load but sit bypass/broken). Any param the generated
 * header does not define keeps its reference default below. */
#ifndef AMPNEVE_BASS_SLOT
#define AMPNEVE_BASS_SLOT (-1)
#define AMPNEVE_BASS_DEFAULT_NORM 0.5f
#define AMPNEVE_BASS_UI_DEFAULT 50
#endif
#ifndef AMPNEVE_MID_SLOT
#define AMPNEVE_MID_SLOT (-1)
#define AMPNEVE_MID_DEFAULT_NORM 0.5f
#define AMPNEVE_MID_UI_DEFAULT 50
#endif
#ifndef AMPNEVE_TREBLE_SLOT
#define AMPNEVE_TREBLE_SLOT (-1)
#define AMPNEVE_TREBLE_DEFAULT_NORM 0.5f
#define AMPNEVE_TREBLE_UI_DEFAULT 50
#endif
#ifndef AMPNEVE_GAIN_SLOT
#define AMPNEVE_GAIN_SLOT (-1)
#define AMPNEVE_GAIN_DEFAULT_NORM 0.35f
#define AMPNEVE_GAIN_UI_DEFAULT 35
#endif
#ifndef AMPNEVE_MASTER_SLOT
#define AMPNEVE_MASTER_SLOT (-1)
#define AMPNEVE_MASTER_DEFAULT_NORM 0.55f
#define AMPNEVE_MASTER_UI_DEFAULT 55
#endif
#ifndef AMPNEVE_LEVEL_SLOT
#define AMPNEVE_LEVEL_SLOT (-1)
#define AMPNEVE_LEVEL_DEFAULT_NORM 0.75f
#define AMPNEVE_LEVEL_UI_DEFAULT 75
#endif
#ifndef AMPNEVE_NEVE_SLOT
#define AMPNEVE_NEVE_SLOT (-1)
#define AMPNEVE_NEVE_DEFAULT_NORM 0.85f
#define AMPNEVE_NEVE_UI_DEFAULT 85
#endif
#ifndef AMPNEVE_CABTYPE_SLOT
#define AMPNEVE_CABTYPE_SLOT (-1)
#define AMPNEVE_CABTYPE_DEFAULT_NORM 0.0f
#define AMPNEVE_CABTYPE_UI_DEFAULT 0
#endif
#ifndef AMPNEVE_INPUT_SLOT
#define AMPNEVE_INPUT_SLOT (-1)
#define AMPNEVE_INPUT_DEFAULT_NORM 1.0f
#define AMPNEVE_INPUT_UI_DEFAULT 100
#endif

#ifndef AMP_DRV_AUDIO_FUNC
#ifndef AMP_DRV_AUDIO_FUNC
#define AMP_DRV_AUDIO_FUNC Fx_AMP_AmpNeve
#endif
#ifndef AMP_DRV_INIT_FUNC
#define AMP_DRV_INIT_FUNC Fx_AMP_AmpNeve_init
#endif
#endif

#define AMP_DO_PRAGMA(x) _Pragma(#x)
#define AMP_EXPAND_PRAGMA(x) AMP_DO_PRAGMA(x)
#define AMP_CODE_SECTION(func) AMP_EXPAND_PRAGMA(CODE_SECTION(func, ".audio"))
#define AMP_ALWAYS_INLINE(func) AMP_EXPAND_PRAGMA(FUNC_ALWAYS_INLINE(func))
AMP_CODE_SECTION(AMP_DRV_AUDIO_FUNC)

#define ZDL_PTR(type, word) ((type)(uintptr_t)(word))

#define AMP_MAGIC   0x414D504Eu   /* 'AMPN' */
#define AMP_VERSION 1u
#define AMP_RAW_MAX 0.14f
#define AMP_RAW_TO_NORM 7.1428571f

/* one Ampsim instance per channel; state float count is fixed generously.
   v18: per-channel state = core + dual 2048-float IR delay buffers
   (crossfade) = 16976 B = 4244 floats; 4352 gives margin. */
#define AMP_STATE_FLOATS 4352u

typedef struct AmpZdlState {
    uint32_t magic;
    uint32_t version;
    uint32_t initialized;
    uint32_t reserved;
    float memL[AMP_STATE_FLOATS];
    float memR[AMP_STATE_FLOATS];
} AmpZdlState;

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

/* Normalize a host param value (0..100 raw, ~0.14 scaled, or 0..1) to 0..1,
 * mirroring the OTT param_norm pattern. */
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

/* Read a param by slot; a negative slot (not exposed on this build) returns
 * the reference default. */
AMP_ALWAYS_INLINE(amp_get_param)
static inline float amp_get_param(float *params, int slot, float fallback_norm)
{
    if (slot < 0) return fallback_norm;
    return amp_param_norm(params[slot], fallback_norm);
}

AMP_ALWAYS_INLINE(amp_zdl_init)
static inline void amp_zdl_init(AmpZdlState *st)
{
    unsigned i;
    for (i = 0; i < AMP_STATE_FLOATS; ++i) { st->memL[i] = 0.0f; st->memR[i] = 0.0f; }
    if (Ampsim_init(&st->memL, AMP_STATE_FLOATS * sizeof(float), 44100.0f) == 0) return;
    if (Ampsim_init(&st->memR, AMP_STATE_FLOATS * sizeof(float), 44100.0f) == 0) return;
    /* Presence fixed at 0.85 (no knob in the 9-slot layout). */
    Ampsim_set_param((Ampsim *)&st->memL, AMP_PARAM_PRESENCE, 0.85f);
    Ampsim_set_param((Ampsim *)&st->memR, AMP_PARAM_PRESENCE, 0.85f);
    st->magic = AMP_MAGIC;
    st->version = AMP_VERSION;
    st->initialized = 1u;
    st->reserved = 0u;
}

#ifdef AMPNEVE_STATELESS
/* Stateless drive build for the B1on: the host only runs custom effects
 * that never write state (ctx[2]/ctx[3]/fardata writes hang boot). This
 * is a true overdrive with soft clipping - no filters, no state. */
void AMP_DRV_AUDIO_FUNC(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    float *fxBuf  = ZDL_PTR(float *, ctx[5]);
    float *outBuf = ZDL_PTR(float *, ctx[6]);
    unsigned int *magicSrc = ZDL_PTR(unsigned int *, ctx[12]);
    unsigned int *magicDst = ZDL_PTR(unsigned int *, *(unsigned int *)ZDL_PTR(unsigned int *, ctx[11]));
    *magicDst = *magicSrc;
    if (params[0] < 0.5f) return;
    float gain  = amp_get_param(params, AMPNEVE_GAIN_SLOT,   0.35f);  /* drive  */
    float level = amp_get_param(params, AMPNEVE_LEVEL_SLOT,  0.75f);  /* output */
    float master= amp_get_param(params, AMPNEVE_MASTER_SLOT, 0.55f);  /* body   */
    float drive = 0.5f + gain * 14.0f;                                 /* 0.5..14.5x */
    float trim  = 0.20f + master * 0.60f;
    float lvl   = 0.10f + level * 1.40f;
    for (int i = 0; i < 16; ++i) {
        float s = fxBuf[i] * drive;
        /* soft clip: s - s^3/3 saturates near +/-1.2 (tube-ish) */
        float c = s * s * s * 0.3333333f;
        s = s - c;
        if (s > 1.2f) s = 1.2f;
        if (s < -1.2f) s = -1.2f;
        outBuf[i] += s * trim * lvl;
    }
}
#else
#if defined(AMPNEVE_CTX2_STATE)
/* B1on pattern (KawaOD/DELAY): state pointer arrives in ctx[2], with the
 * first 16 bytes reserved and the usable block starting at +0x10. */
#define AMP_STATE_BASE(ctx) ((AmpZdlState *)((char *)ZDL_PTR(char *, (ctx)[2]) + 0x10))
#elif defined(AMPNEVE_FARDATA_STATE)
/* B1on probe: state lives in the ELF's own .fardata instead of the host
 * ctx[3] arena (which proved unreliable for custom effects on the B1on:
 * small-state builds hung boot once the arena checks passed). */
#pragma DATA_SECTION(amp_state_storage, ".fardata")
static AmpZdlState amp_state_storage;
#define AMP_STATE_BASE(ctx) (&amp_state_storage)
#endif
void AMP_DRV_AUDIO_FUNC(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    float *fxBuf  = ZDL_PTR(float *, ctx[5]);

#ifdef AMPNEVE_INIT_ONLY
    /* Probe (runs before the params[0] check so it fires even in bypass):
     * force the full 34 KB state footprint through ctx[3] on every block,
     * then pass audio through. Clean boot + audible dry signal = the state
     * write itself is safe; any hang = the state write is fatal on this
     * host (custom ZDLs get no usable state arena). */
    {
        volatile unsigned int *desc = ZDL_PTR(volatile unsigned int *, ctx[3]);
        if (desc) {
            AmpZdlState *st = (AmpZdlState *)amp_align4((uintptr_t)desc[0]);
            if (st && !((uintptr_t)st & 3u)) amp_zdl_init(st);
        }
    }
    {
        float *outBuf = ZDL_PTR(float *, ctx[6]);
        int i;
        for (i = 0; i < 16; ++i) outBuf[i] += fxBuf[i];
    }
    return;
}
#else
    unsigned int *magicSrc = ZDL_PTR(unsigned int *, ctx[12]);
    unsigned int *magicDst = ZDL_PTR(unsigned int *, *(unsigned int *)ZDL_PTR(unsigned int *, ctx[11]));
    *magicDst = *magicSrc;

    if (params[0] < 0.5f) return;   /* effect off: leave Fx buffer for the dry mix */

#ifdef AMPNEVE_CTX2_STATE
    AmpZdlState *st = AMP_STATE_BASE(ctx);
    if (!st) return;
#elif defined(AMPNEVE_FARDATA_STATE)
    AmpZdlState *st = AMP_STATE_BASE(ctx);
#else
    volatile unsigned int *desc = ZDL_PTR(volatile unsigned int *, ctx[3]);
    if (!desc) return;
#ifdef AMPNEVE_INIT_ONLY
    /* Probe: write the full state footprint even if the descriptor bounds
     * look wrong, so a clean boot means "34 KB through ctx[3] is safe" and
     * a hang means "the state write itself is fatal on this host". */
    AmpZdlState *st = (AmpZdlState *)amp_align4((uintptr_t)desc[0]);
    if (!st || ((uintptr_t)st & 3u)) return;
    amp_zdl_init(st);
    return;
#else
    uintptr_t base = (uintptr_t)desc[0];
    uintptr_t end  = (uintptr_t)desc[1];
    unsigned int span = desc[2];
    uintptr_t stateBase = amp_align4(base);
    uintptr_t requiredEnd = stateBase + sizeof(AmpZdlState);
    uintptr_t bytes = end - base;
    if (base == 0u || end <= base) return;
    if ((base & 3u) != 0u || (end & 3u) != 0u || (span & 3u) != 0u) return;
    if (bytes < sizeof(AmpZdlState) || span < bytes) return;
    if (requiredEnd > end) return;
    AmpZdlState *st = (AmpZdlState *)stateBase;
#endif
#endif
    if (st->magic != AMP_MAGIC || st->version != AMP_VERSION || !st->initialized) {
        amp_zdl_init(st);
        return;
    }
#ifdef AMPNEVE_INIT_ONLY
    /* unreachable (the top-of-function probe returns first) */
#endif

    float bass     = amp_get_param(params, AMPNEVE_BASS_SLOT,      AMPNEVE_BASS_DEFAULT_NORM);
    float mid      = amp_get_param(params, AMPNEVE_MID_SLOT,       AMPNEVE_MID_DEFAULT_NORM);
    float treble   = amp_get_param(params, AMPNEVE_TREBLE_SLOT,    AMPNEVE_TREBLE_DEFAULT_NORM);
    float gain     = amp_get_param(params, AMPNEVE_GAIN_SLOT,      AMPNEVE_GAIN_DEFAULT_NORM);
    float master   = amp_get_param(params, AMPNEVE_MASTER_SLOT,    AMPNEVE_MASTER_DEFAULT_NORM);
    float level    = amp_get_param(params, AMPNEVE_LEVEL_SLOT,     AMPNEVE_LEVEL_DEFAULT_NORM);
    float neve     = amp_get_param(params, AMPNEVE_NEVE_SLOT,      AMPNEVE_NEVE_DEFAULT_NORM);
    /* Cabtype: raw 0..1 (a knob scaled to 0..1 by the host). */
    float cabtype  = 0.0f;
    {
        float raw = amp_get_param(params, AMPNEVE_CABTYPE_SLOT, AMPNEVE_CABTYPE_DEFAULT_NORM);
        if (raw > 1.0f && raw <= 100.0f) raw = raw * 0.01f;   /* 0..100 -> 0..1 */
        if (raw < 0.0f) raw = 0.0f;
        if (raw > 1.0f) raw = 1.0f;
        cabtype = raw;
    }
    float input    = amp_get_param(params, AMPNEVE_INPUT_SLOT,     AMPNEVE_INPUT_DEFAULT_NORM);

    Ampsim *aL = (Ampsim *)&st->memL;
    Ampsim *aR = (Ampsim *)&st->memR;
    Ampsim_set_param(aL, AMP_PARAM_BASS,     bass);
    Ampsim_set_param(aL, AMP_PARAM_MID,      mid);
    Ampsim_set_param(aL, AMP_PARAM_TREBLE,   treble);
    Ampsim_set_param(aL, AMP_PARAM_GAIN,     gain);
    Ampsim_set_param(aL, AMP_PARAM_MASTER,   master);
    Ampsim_set_param(aL, AMP_PARAM_LEVEL,    level);
    Ampsim_set_param(aL, AMP_PARAM_NEVE,     neve);
    Ampsim_set_param(aL, AMP_PARAM_CABTYPE,  cabtype);
    Ampsim_set_param(aL, AMP_PARAM_INPUT,    input);
    Ampsim_set_param(aR, AMP_PARAM_BASS,     bass);
    Ampsim_set_param(aR, AMP_PARAM_MID,      mid);
    Ampsim_set_param(aR, AMP_PARAM_TREBLE,   treble);
    Ampsim_set_param(aR, AMP_PARAM_GAIN,     gain);
    Ampsim_set_param(aR, AMP_PARAM_MASTER,   master);
    Ampsim_set_param(aR, AMP_PARAM_LEVEL,    level);
    Ampsim_set_param(aR, AMP_PARAM_NEVE,     neve);
    Ampsim_set_param(aR, AMP_PARAM_CABTYPE,  cabtype);
    Ampsim_set_param(aR, AMP_PARAM_INPUT,    input);

    int i;
    for (i = 0; i < 8; i++) {
        float oL, oR;
        Ampsim_process(aL, fxBuf[i],     &oL);
        Ampsim_process(aR, fxBuf[i + 8], &oR);
        fxBuf[i]     = oL;
        fxBuf[i + 8] = oR;
    }
}
#endif
#endif

/* Zoom materializes effect params through the _init handler. MS-70CDR
 * tolerates a NOP init, but G1on leaves the host param table untouched -
 * the effect then registers as a bypass/no-UI stub whose audio never runs
 * (our audio keys off params[0]) and re-entry freezes. Write the ON flag
 * and the nine knob defaults into the host param table here. The audio
 * lazily initializes the ctx[3] state arena on its first block. */
void AMP_DRV_INIT_FUNC(unsigned int *ctx)
{
    float *params = ZDL_PTR(float *, ctx[1]);
    params[0] = 1.0f;
    params[AMPNEVE_BASS_SLOT]   = (float)AMPNEVE_BASS_UI_DEFAULT;
    params[AMPNEVE_MID_SLOT]    = (float)AMPNEVE_MID_UI_DEFAULT;
    params[AMPNEVE_TREBLE_SLOT] = (float)AMPNEVE_TREBLE_UI_DEFAULT;
    params[AMPNEVE_GAIN_SLOT]   = (float)AMPNEVE_GAIN_UI_DEFAULT;
    params[AMPNEVE_MASTER_SLOT] = (float)AMPNEVE_MASTER_UI_DEFAULT;
    params[AMPNEVE_LEVEL_SLOT]  = (float)AMPNEVE_LEVEL_UI_DEFAULT;
    params[AMPNEVE_NEVE_SLOT]   = (float)AMPNEVE_NEVE_UI_DEFAULT;
    params[AMPNEVE_CABTYPE_SLOT] = (float)AMPNEVE_CABTYPE_UI_DEFAULT;
    params[AMPNEVE_INPUT_SLOT]  = (float)AMPNEVE_INPUT_UI_DEFAULT;
}

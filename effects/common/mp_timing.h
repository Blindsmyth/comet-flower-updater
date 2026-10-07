/* mp_timing.h - double-pass kernel timing for the CF timing diagnostics
 * (effects/ratt, effects/t808). The including file defines:
 *   MPT_STATE   the DSP state type        MPT_COEFFS  the coefficient type
 *   MPT_SETUP(k)               fill coefficients (fixed, worst-case knobs)
 *   MPT_PROCESS(st, k, x)      one sample
 *   MPT_TAG                    4-character tag, e.g. 0x52415420 ('RAT ')
 * Per block: snapshot the state; pass 1 = MPT_SETUP + 16 samples on the
 * real state, timed (whatever cache state the firmware left: "cold");
 * pass 2 = the same on the snapshot with the same input ("warm": code and
 * data just used). The guitar is muted; the tone code (mp_fsk.h) reports:
 *   0 magic 0xCF0071ED   1 tag   2 blocks   3 sum cold   4 min cold
 *   5 max cold   6 sum warm   7 min warm   8 code address   9 0   10 0
 *   11 check
 * Decoder: tools/decode_memprobe.py. Never save it in a patch. */
#ifndef MP_TIMING_H
#define MP_TIMING_H
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#else
static unsigned TSCL;                /* host build: a counter that never moves */
#endif
#include "sh_params.h"
#include "mp_fsk.h"

typedef struct {
    MpFsk fsk;                       /* 64 B */
    MPT_STATE dsp;
    uint32_t n, sc, minc, maxc, sw, minw;
} KernelState;

typedef char mpt_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    float fade = coef[SH_COEFF_BYPASS];
    float lvl  = coef[SH_PARAM_LEVEL] * 0.5f;
    MPT_STATE snap;
    MPT_COEFFS k;
    float in[SH_FRAMES], sink = 0.0f;
    uint32_t t0, t1, t2, t3, dc, dw;
    uint32_t *src, *dst;
    int i;

#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD) {
        for (i = 0; i < SH_FRAMES; i++) { eff[i] = 0.0f; eff[i + SH_CH_B_OFFSET] = 0.0f; }
        return;
    }
#endif
    if (!(fade >= 0.0f && fade <= 1.0f)) fade = 0.0f;
    if (!(lvl >= 0.0f && lvl <= 0.8f)) lvl = 0.0f;

    for (i = 0; i < SH_FRAMES; i++) in[i] = eff[i];
    src = (uint32_t *)&s->dsp; dst = (uint32_t *)&snap;      /* no memcpy call */
    for (i = 0; i < (int)(sizeof(MPT_STATE) / 4); i++) dst[i] = src[i];

    t0 = TSCL;
    MPT_SETUP(&k);
    for (i = 0; i < SH_FRAMES; i++) sink += MPT_PROCESS(&s->dsp, &k, in[i]);
    t1 = TSCL;
    t2 = TSCL;
    MPT_SETUP(&k);
    for (i = 0; i < SH_FRAMES; i++) sink += MPT_PROCESS(&snap, &k, in[i]);
    t3 = TSCL;
    dc = t1 - t0; dw = t3 - t2;
    if (!(sink > -1.0e30f && sink < 1.0e30f))                 /* reset a blown state */
        for (i = 0; i < (int)(sizeof(MPT_STATE) / 4); i++) src[i] = 0u;

    if (s->n == 0) { s->minc = 0xffffffffu; s->minw = 0xffffffffu; }
    s->n++; s->sc += dc; s->sw += dw;
    if (dc < s->minc) s->minc = dc;
    if (dc > s->maxc) s->maxc = dc;
    if (dw < s->minw) s->minw = dw;

    if (MP_FSK_FRAME_START(&s->fsk)) {
        s->fsk.w[0] = 0xCF0071EDu;
        s->fsk.w[1] = MPT_TAG;
        s->fsk.w[2] = s->n;
        s->fsk.w[3] = s->sc;
        s->fsk.w[4] = s->minc;
        s->fsk.w[5] = s->maxc;
        s->fsk.w[6] = s->sw;
        s->fsk.w[7] = s->minw;
        s->fsk.w[8] = (uint32_t)(uintptr_t)&SH_AUDIO_FN;
        s->fsk.w[9] = 0;
        s->fsk.w[10] = 0;
        MP_FSK_SEAL(&s->fsk);
        s->n = 0; s->sc = 0; s->maxc = 0; s->sw = 0;
    }
    MP_FSK_BLOCK(&s->fsk, eff, lvl, fade);
}
#endif

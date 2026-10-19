/* ratx.c - "CF RAT": the ProCo RAT core (effects/common/rat_g1.h) as a G1
 * effect. Mono DSP on channel A, written to both channels; bypass crossfade
 * per channel. Guard prologue and output clamp as in drv808x.c.
 * Written by Claude as part of the DSP kit; the DSP lives in rat_g1.h.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "rat_g1.h"

typedef struct {
    RatState dsp;
    float dist, filter, vol;         /* knobs smoothed per block */
    float primed;
} KernelState;

/* the manifest's state_bytes must cover KernelState (compile-time check) */
typedef char ratx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

#define KNOB_SMOOTH 0.1f
#define TRIM        0.5f

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    RatCoeffs k;
    float wet[SH_FRAMES];
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kd   = coef[SH_PARAM_DISTORTION];
    float kf   = coef[SH_PARAM_FILTER];
    float kv   = coef[SH_PARAM_VOLUME];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kd >= 0.0f && kd <= 1.0f)) ok = 0;
    if (!(kf >= 0.0f && kf <= 1.0f)) ok = 0;
    if (!(kv >= 0.0f && kv <= 1.6f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->dist = kd; s->filter = kf; s->vol = kv; s->primed = 1.0f;
    } else {
        s->dist   += KNOB_SMOOTH * (kd - s->dist);
        s->filter += KNOB_SMOOTH * (kf - s->filter);
        s->vol    += KNOB_SMOOTH * (kv - s->vol);
    }
    rat_coeffs(&k, s->dist * 10.0f, s->filter, TRIM * s->vol);

    rat_block(&s->dsp, &k, eff, wet, SH_FRAMES);

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(SH_FRAMES, SH_FRAMES, SH_FRAMES)
#endif
    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float w = wet[i];
        float a, b;
        if (!(w > -8.0f && w < 8.0f)) w = 0.0f;
        a = da + fade * (w - da);
        b = db + fade * (w - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
}

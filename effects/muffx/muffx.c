/* muffx.c - "CF Muff": the Ram's Head Big Muff core (effects/common/muff_g1.h) as a G1
 * effect. Mono DSP on channel A, written to both channels; bypass crossfade
 * per channel. Guard prologue and output clamp as in drv808x.c.
 * Written by Claude as part of the DSP kit; the DSP lives in muff_g1.h.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "muff_g1.h"

typedef struct {
    MuffState dsp;
    float sus, tone, vol;           /* knobs smoothed per block */
    float primed;
} KernelState;

/* the manifest's state_bytes must cover KernelState (compile-time check) */
typedef char muffx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

#define KNOB_SMOOTH 0.1f
#define TRIM        0.5f

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *restrict eff = (float *)ctx[1];   /* only this pointer touches the bus here */
    KernelState *s    = (KernelState *)instance[2];
    MuffCoeffs k;
    float wetb[SH_FRAMES];
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kd   = coef[SH_PARAM_SUSTAIN];
    float kf   = coef[SH_PARAM_TONE];
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
        s->sus = kd; s->tone = kf; s->vol = kv; s->primed = 1.0f;
    } else {
        s->sus    += KNOB_SMOOTH * (kd - s->sus);
        s->tone   += KNOB_SMOOTH * (kf - s->tone);
        s->vol    += KNOB_SMOOTH * (kv - s->vol);
    }
    muff_coeffs(&k, s->sus, s->tone, TRIM * s->vol);

    /* the whole block through the core, stage by stage (docs/C6745_DESIGN.md) */
    muff_block(&s->dsp, &k, eff, wetb, SH_FRAMES);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = wetb[i];
        float a, b;
        if (!(wet > -8.0f && wet < 8.0f)) wet = 0.0f;
        a = da + fade * (wet - da);
        b = db + fade * (wet - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
}

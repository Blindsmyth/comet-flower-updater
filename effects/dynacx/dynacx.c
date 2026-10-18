/* dynacx.c - "CF DynaComp": the MXR Dyna Comp core (effects/common/dynacomp_g1.h) as a
 * G1 effect. Mono DSP on channel A, written to both channels; bypass crossfade per
 * channel. Guard prologue and output clamp as in muffx.c. The DSP lives in the header.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "dynacomp_g1.h"

typedef struct {
    DynaCompState dsp;
    float sus, out;                 /* knobs smoothed per block */
    float primed;
} KernelState;

typedef char dynacx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

#define KNOB_SMOOTH 0.1f

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    DynaCompCoeffs k;
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float ks   = coef[SH_PARAM_SUSTAIN];
    float ko   = coef[SH_PARAM_LEVEL];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(ks >= 0.0f && ks <= 1.0f)) ok = 0;
    if (!(ko >= 0.0f && ko <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->sus = ks; s->out = ko; s->primed = 1.0f;
    } else {
        s->sus += KNOB_SMOOTH * (ks - s->sus);
        s->out += KNOB_SMOOTH * (ko - s->out);
    }
    dynacomp_coeffs(&k, 10.0f * s->sus, 40.0f * s->out - 20.0f);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = dynacomp_process(&s->dsp, &k, da);
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

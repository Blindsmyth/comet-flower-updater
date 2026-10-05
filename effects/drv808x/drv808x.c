/* drv808x.c - "Green 808X": the circuit-exact TS808 (ts808_exact.h) as a G1
 * effect. Mono DSP on channel A, written to both channels; bypass crossfade
 * per channel. Guard prologue and output clamp as in stomphacks gain.c.
 *
 * Heavy by design: 8x oversampling with a 3-step diode solve per sample.
 * Declares a large dspload so the pedal budgets it like a big amp model.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "ts808_exact.h"

typedef struct {
    TsxState dsp;                    /* 300 B */
    float drive, tone, vol;          /* knobs smoothed per block */
    float primed;
} KernelState;                       /* 316 B = manifest state_bytes */

#define KNOB_SMOOTH 0.1f
#define TRIM        0.5f

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    TsxCoeffs k;
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kd   = coef[SH_PARAM_DRIVE];
    float kt   = coef[SH_PARAM_TONE];
    float kv   = coef[SH_PARAM_LEVEL];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kd >= 0.0f && kd <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(kv >= 0.0f && kv <= 1.6f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->drive = kd; s->tone = kt; s->vol = kv; s->primed = 1.0f;
    } else {
        s->drive += KNOB_SMOOTH * (kd - s->drive);
        s->tone  += KNOB_SMOOTH * (kt - s->tone);
        s->vol   += KNOB_SMOOTH * (kv - s->vol);
    }
    tsx_coeffs(&k, s->drive * 10.0f, s->tone, TRIM * s->vol);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = tsx_process(&s->dsp, &k, da);
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

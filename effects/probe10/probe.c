/* probe.c - G1 hardware diagnostics (the same kernel in probe30/ and probe10/,
 * which differ only in id and declared dspload).
 *
 * Load knob: burns knob x 200 iterations (kl * 20000, kl = knob/100) of a DEPENDENT multiply-add
 * chain per 16-sample block, 8 cycles each = 1600 cycles per knob step (each iteration waits for the previous one, so
 * the cost per iteration is fixed by instruction latency; read it from the
 * disassembly). Turn it up until the audio breaks up: that is the CPU limit.
 * Tone switch: adds a 440 Hz sine computed for 44.1 kHz at -14 dBFS. A tuner
 * reading A4 = 440 Hz confirms the sample rate and block timing.
 * Dry signal always passes; bypass fades the tone out.
 */
#include <stdint.h>
#include "sh_params.h"

typedef struct { float phase, acc; } ProbeState;   /* 8 B */

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    ProbeState *s     = (ProbeState *)instance[2];
    int i, j, n;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kl   = coef[SH_PARAM_LOAD];
    float kt   = coef[SH_PARAM_TONE];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kl >= 0.0f && kl <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    n = (int)(kl * 20000.0f + 0.5f);
    {
        float acc = s->acc;
        for (j = 0; j < n; j++)
            acc = acc * 0.9999f + 1.0e-6f;
        if (!(acc > -1.0f && acc < 1.0f)) acc = 0.0f;
        s->acc = acc;
    }

    {
        float ph = s->phase;
        float amp = (kt > 0.5f ? 0.2f : 0.0f) * fade;
        if (!(ph >= 0.0f && ph < 1.0f)) ph = 0.0f;
        for (i = 0; i < SH_FRAMES; i++) {
            /* sin(2*pi*ph) via x in [-pi, pi): sin(x) = -sin(2*pi*ph) shift */
            float x = 6.2831853f * ph - 3.14159265f;
            float x2 = x * x;
            float sn = -x * (1.0f + x2 * (-1.0f/6 + x2 * (1.0f/120 + x2 * (-1.0f/5040
                       + x2 * (1.0f/362880 + x2 * (-1.0f/39916800 + x2 * (1.0f/6227020800.0f)))))));
            float a = eff[i] + amp * sn;
            float b = eff[i + SH_CH_B_OFFSET] + amp * sn;
            if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
            if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
            eff[i] = a;
            eff[i + SH_CH_B_OFFSET] = b;
            ph += 440.0f / SH_SAMPLE_RATE;
            if (ph >= 1.0f) ph -= 1.0f;
        }
        s->phase = ph;
    }
}

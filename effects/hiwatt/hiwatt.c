/* hiwatt.c - "DR103": the Hiwatt DR103 Custom 100 circuit model
 * (hiwatt_amp.h, a port of Comet Flower's desktop amp) as a G1 effect.
 * Mono DSP on channel A, written to both channels; bypass crossfade per
 * channel. Guard prologue and output clamp as in stomphacks gain.c.
 *
 * Per block: knobs smoothed, the three networks re-derived (on the stack, not
 * in state: state stays under the G1's ~392 B), then 16 samples at 4x.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "hiwatt_amp.h"

typedef struct {
    HwState dsp;                     /* 292 B */
    float vol, tre, mid, bas, mas, pre;   /* knobs smoothed per block */
    float primed;
} KernelState;                       /* 320 B = manifest state_bytes */

#define KNOB_SMOOTH 0.1f

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    HwCoeffs k;
    int i, cab;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kv = coef[SH_PARAM_VOLUME], kt = coef[SH_PARAM_TREBLE];
    float km = coef[SH_PARAM_MIDDLE], kb = coef[SH_PARAM_BASS];
    float kp = coef[SH_PARAM_PRESENCE], ks = coef[SH_PARAM_MASTER];
    float kc = coef[SH_PARAM_CAB];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kv >= 0.0f && kv <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(km >= 0.0f && km <= 1.0f)) ok = 0;
    if (!(kb >= 0.0f && kb <= 1.0f)) ok = 0;
    if (!(kp >= 0.0f && kp <= 1.0f)) ok = 0;
    if (!(ks >= 0.0f && ks <= 1.0f)) ok = 0;
    if (!(kc >= 0.0f && kc <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->vol = kv; s->tre = kt; s->mid = km; s->bas = kb; s->mas = ks; s->pre = kp;
        s->primed = 1.0f;
    } else {
        s->vol += KNOB_SMOOTH * (kv - s->vol);
        s->tre += KNOB_SMOOTH * (kt - s->tre);
        s->mid += KNOB_SMOOTH * (km - s->mid);
        s->bas += KNOB_SMOOTH * (kb - s->bas);
        s->mas += KNOB_SMOOTH * (ks - s->mas);
        s->pre += KNOB_SMOOTH * (kp - s->pre);
    }
    hw_coeffs(&k, s->vol, s->tre, s->mid, s->bas, s->mas, s->pre);
    cab = kc > 0.5f;

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = hw_process(&s->dsp, &k, da, cab);
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

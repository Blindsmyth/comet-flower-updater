/* bypt.c - "CF BypTest": does the firmware call a bypassed effect?
 *
 * ON (fade 1): the bus passes unchanged. OFF (fade 0): the bus plus a quiet
 * 880 Hz beep scaled by (1 - fade). The beep can only be heard if the audio
 * function still runs while the effect is switched off; a silent-but-dry OFF
 * means the firmware stops calling it (or swaps in its default callback
 * 11818de0), and delay tails would need a firmware patch.
 * Oscillator: a rotating phasor (no libm), renormalised once per block.
 */
#include <stdint.h>
#include "sh_params.h"

#define BEEP_C 0.98014246f   /* cos(2*pi*880/44100) */
#define BEEP_S 0.19827948f   /* sin(2*pi*880/44100) */

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    float *state      = (float *)instance[2];   /* [0] = cos, [1] = sin */
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float beep = coef[SH_PARAM_BEEP];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(beep >= 0.0f && beep <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    float c = state[0], s = state[1];
    float m = c * c + s * s;
    if (!(m > 0.5f && m < 2.0f)) { c = 1.0f; s = 0.0f; }
    else { float g = 1.5f - 0.5f * m; c *= g; s *= g; }   /* renormalise */
    float amp = 0.1f * beep * (1.0f - fade);              /* <= -20 dBFS */

    for (i = 0; i < SH_FRAMES; i++) {
        float nc = c * BEEP_C - s * BEEP_S;
        float ns = s * BEEP_C + c * BEEP_S;
        float a = eff[i] + amp * ns;
        float b = eff[i + SH_CH_B_OFFSET] + amp * ns;
        c = nc; s = ns;
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
    state[0] = c; state[1] = s;
}

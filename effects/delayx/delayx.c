/* delayx.c - "CF Delay": Comet Flower's DelayMobile (effects/common/delay_g1.h) as a G1 effect.
 * Mono in (channel A), stereo out (main tap left, the 20 ms later tap right); bypass crossfade
 * per channel. The 512 KB line and its state live in the slot's work buffer (instance[3] ->
 * {base, end, size}, 0x81330 B, docs/helpers/DELAY_MEM_SONNET_2026-10-17.md); it is never
 * cleared: the first block after a load resets only the counters, and cells not yet written
 * read as zero (as the original's MonoDelayLine). Guard prologue and output clamp as muffx.c.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#define CE2_SAT_BLOB
#include "delay_g1.h"

typedef struct {
    float fb, mix;                  /* smoothed per block (the original smooths these two; Time glides in the core) */
    float primed;
} KernelState;

typedef char delayx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

#define KNOB_SMOOTH 0.1f

TS_INLINE DelayState *work_state(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(DelayState))
        return 0;
    return (DelayState *)wb[0];
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *DL_RESTRICT eff = (float *)ctx[1];   /* only this pointer touches the bus here */
    KernelState *s    = (KernelState *)instance[2];
    DelayState *d     = work_state(instance);
    DelayCoeffs k;
    float wl_b[SH_FRAMES], wr_b[SH_FRAMES];
    int i;

    unsigned ok = d != 0;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kt   = coef[SH_PARAM_TIME];
    float kr   = coef[SH_PARAM_REGEN];
    float km   = coef[SH_PARAM_MIX];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(kr >= 0.0f && kr <= 1.0f)) ok = 0;
    if (!(km >= 0.0f && km <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->fb = kr; s->mix = km;
    } else {
        s->fb  += KNOB_SMOOTH * (kr - s->fb);
        s->mix += KNOB_SMOOTH * (km - s->mix);
    }
    delay_coeffs(&k, 2000.0f * kt, 0.92f * s->fb, s->mix);
    if (s->primed != 1.0f) {        /* a reset line: counters only, no 512 KB clear */
        d->wp = 0; d->written = 0; d->lp = 0.0f; d->x1 = 0.0f;
        delay_snap(d, &k);
        s->primed = 1.0f;
    }

    /* the whole block through the core, stage by stage (docs/C6745_DESIGN.md) */
    delay_block(d, &k, eff, wl_b, wr_b, SH_FRAMES);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wl = wl_b[i], wr = wr_b[i], a, b;
        if (!(wl > -8.0f && wl < 8.0f)) wl = 0.0f;
        if (!(wr > -8.0f && wr < 8.0f)) wr = 0.0f;
        a = da + fade * (wl - da);
        b = db + fade * (wr - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
}

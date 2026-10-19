/* mistrx.c - "CF Mistress": the mistress_g1.h core as a G1 effect. Mono DSP on channel A, written to both
 * channels; bypass crossfade per channel. Guard prologue and output clamp as in muffx.c.
 * The DSP state (MistressState, larger than the 392-byte slot state) lives at the start of the
 * slot's work buffer: instance[3] -> {base, end, size}, 0x81330 B per slot, the buffer
 * stock DELAY_3S uses (docs/helpers/DELAY_MEM_SONNET_2026-10-17.md). Stock zeroes it
 * only at boot, so the first block after each load zeroes our part of it (the small
 * slot state, zeroed by the loader, carries the primed flag).
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "mistress_g1.h"

typedef struct {
    float p1, p2, p3, p4;           /* knobs smoothed per block */
    float primed;
} KernelState;

typedef char mistrx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

#define KNOB_SMOOTH 0.1f

TS_INLINE MistressState *work_state(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(MistressState))
        return 0;
    return (MistressState *)wb[0];
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *restrict eff = (float *)ctx[1];   /* only this pointer touches the bus here */
    KernelState *s    = (KernelState *)instance[2];
    MistressState *m  = work_state(instance);
    MistressCoeffs k;
    float wetb[SH_FRAMES];
    int i;

    unsigned ok = m != 0;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kr   = coef[SH_PARAM_RATE];
    float kg   = coef[SH_PARAM_RANGE];
    float kc   = coef[SH_PARAM_COLOR];
    float kx   = coef[SH_PARAM_MATRIX];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kr >= 0.0f && kr <= 1.0f)) ok = 0;
    if (!(kg >= 0.0f && kg <= 1.0f)) ok = 0;
    if (!(kc >= 0.0f && kc <= 1.0f)) ok = 0;
    if (!(kx >= 0.0f && kx <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        volatile uint32_t *w = (volatile uint32_t *)m;   /* no memset call */
        unsigned n;
        for (n = 0; n < sizeof(MistressState) / 4u; n++)
            w[n] = 0u;
        s->p1 = kr; s->p2 = kg; s->p3 = kc; s->primed = 1.0f;
    } else {
        s->p1 += KNOB_SMOOTH * (kr - s->p1);
        s->p2 += KNOB_SMOOTH * (kg - s->p2);
        s->p3 += KNOB_SMOOTH * (kc - s->p3);
    }
    /* Rate 0..100 -> 0.05..10 Hz (square taper), Range -> depth, Color -> feedback
       0..0.95, Matrix on/off; mix 1 = the pedal's hardwired 50/50. */
    mistress_coeffs(&k, 0.05f + 9.95f * s->p1 * s->p1, s->p2, 0.95f * s->p3,
                    kx >= 0.5f ? 1.0f : 0.0f, 1.0f);

    /* the whole block through the core, stage by stage (docs/C6745_DESIGN.md) */
    mistress_block(m, &k, eff, wetb, SH_FRAMES);

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

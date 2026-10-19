/* cfm_pre.c - "CFM Pre": Preamp stage of the CF Master split variant (2 slots).
 * Hosts DynaComp, Ram's Head Big Muff, and Electric Mistress in sequence.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "dynacomp_g1.h"
#include "muff_g1.h"
#include "mistress_g1.h"

typedef struct {
    MuffState muff;
    DynaState dyna;
    float m_sus, m_tone, m_vol;
    float fl_rate, fl_range, fl_color;
    float dy_sens, dy_out;
    float primed;
} CfmPreState;

typedef char cfm_pre_state_fits[(sizeof(CfmPreState) <= SH_STATE_BYTES) ? 1 : -1];

TS_INLINE MistressState *cfm_pre_work(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb) return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(MistressState))
        return 0;
    return (MistressState *)wb[0];
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *restrict eff = (float *)ctx[1];
    CfmPreState *s = (CfmPreState *)instance[2];
    MistressState *m = cfm_pre_work(instance);
    float buf_a[SH_FRAMES], buf_b[SH_FRAMES];
    int i;

    unsigned ok = (m != 0);
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif

    float fade = coef[SH_COEFF_BYPASS];
    float k_ms = coef[SH_PARAM_MUFF_SUST];
    float k_mt = coef[SH_PARAM_MUFF_TONE];
    float k_mv = coef[SH_PARAM_MUFF_VOL];
    float k_mon = coef[SH_PARAM_MUFF_ON];
    float k_fr = coef[SH_PARAM_MIST_RATE];
    float k_fg = coef[SH_PARAM_MIST_RANG];
    float k_fc = coef[SH_PARAM_MIST_COLR];
    float k_fx = coef[SH_PARAM_MIST_MTRX];
    float k_ds = coef[SH_PARAM_DYNA_SENS];
    float k_do = coef[SH_PARAM_DYNA_OUT];
    float k_don = coef[SH_PARAM_DYNA_ON];
    float k_lvl = coef[SH_PARAM_PRE_LEVEL];

    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        volatile uint32_t *w = (volatile uint32_t *)m;
        unsigned n;
        for (n = 0; n < sizeof(MistressState) / 4u; n++) w[n] = 0u;
        s->m_sus = k_ms; s->m_tone = k_mt; s->m_vol = k_mv;
        s->fl_rate = k_fr; s->fl_range = k_fg; s->fl_color = k_fc;
        s->dy_sens = k_ds; s->dy_out = k_do;
        s->primed = 1.0f;
    } else {
        s->m_sus += 0.1f * (k_ms - s->m_sus);
        s->m_tone += 0.1f * (k_mt - s->m_tone);
        s->m_vol += 0.1f * (k_mv - s->m_vol);
        s->fl_rate += 0.1f * (k_fr - s->fl_rate);
        s->fl_range += 0.1f * (k_fg - s->fl_range);
        s->fl_color += 0.1f * (k_fc - s->fl_color);
        s->dy_sens += 0.1f * (k_ds - s->dy_sens);
        s->dy_out += 0.1f * (k_do - s->dy_out);
    }

    /* 1. Optional DynaComp */
    if (k_don >= 0.5f) {
        DynaCoeffs dc;
        dynacomp_coeffs(&dc, s->dy_sens, s->dy_out);
        dynacomp_block(&s->dyna, &dc, eff, buf_a, SH_FRAMES);
    } else {
        for (i = 0; i < SH_FRAMES; ++i) buf_a[i] = eff[i];
    }

    /* 2. Ram's Head Big Muff */
    if (k_mon >= 0.5f) {
        MuffCoeffs mc;
        muff_coeffs(&mc, s->m_sus, s->m_tone, 0.5f * s->m_vol);
        muff_block(&s->muff, &mc, buf_a, buf_b, SH_FRAMES);
    } else {
        for (i = 0; i < SH_FRAMES; ++i) buf_b[i] = buf_a[i];
    }

    /* 3. Electric Mistress */
    {
        MistressCoeffs fc;
        mistress_coeffs(&fc, 0.05f + 9.95f * s->fl_rate * s->fl_rate,
                        s->fl_range, 0.95f * s->fl_color, k_fx >= 0.5f ? 1.0f : 0.0f, 1.0f);
        mistress_block(m, &fc, buf_b, buf_a, SH_FRAMES);
    }

    /* Master output scaling and mixdown */
    float out_gain = k_lvl * 1.5f;
    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = buf_a[i] * out_gain;
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

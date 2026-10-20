/* cfm_amp.c - "CFM Amp": Amp and Rotary stage of the CF Master split variant (3 slots).
 * Hosts MXR DDS-1 Delay, Hiwatt DR103 / WEM 4x12, and Alembic F-2B / Yamaha RA-200.
 * Reuses the co-scheduled Watt NFB + RA-200 rotary core from cfmaster_kernel.h.
 */
#define CFM_STAGE_OFF_MUFF   1
#define CFM_STAGE_OFF_MISTRX 1

#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
unsigned __c6xabi_fixfu(float f) { return (unsigned)(int)f; }
#endif
#include "sh_params.h"
#include "cfmaster_kernel.h"

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *HW_RESTRICT eff = (float *)ctx[1];
    CfmKernelState *s = (CfmKernelState *)instance[2];
    CfmWorkBuffer *w  = cfm_work(instance);
    int i;

    unsigned ok = (w != 0);
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif

    float fade = coef[SH_COEFF_BYPASS];
    float k_ad = coef[SH_PARAM_AMP_DRIVE];
    float k_am = coef[SH_PARAM_AMP_MSTR];
    float k_at = coef[SH_PARAM_AMP_TREB];
    float k_ab = coef[SH_PARAM_AMP_BASS];
    float k_dt = coef[SH_PARAM_DLY_TIME];
    float k_df = coef[SH_PARAM_DLY_FDBK];
    float k_dm = coef[SH_PARAM_DLY_MIX];
    float k_cs = coef[SH_PARAM_CAB_SIM];
    float k_rr = coef[SH_PARAM_ROTOR];
    float k_rs = coef[SH_PARAM_ROT_SPEED];
    float k_rm = coef[SH_PARAM_RA200_MIX];
    float k_rb = coef[SH_PARAM_RIG_BLEND];

    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(k_ad >= 0.0f && k_ad <= 1.0f)) ok = 0;
    if (!(k_am >= 0.0f && k_am <= 1.0f)) ok = 0;
    if (!(k_at >= 0.0f && k_at <= 1.0f)) ok = 0;
    if (!(k_ab >= 0.0f && k_ab <= 1.0f)) ok = 0;
    if (!(k_dt >= 0.0f && k_dt <= 1.0f)) ok = 0;
    if (!(k_df >= 0.0f && k_df <= 1.0f)) ok = 0;
    if (!(k_dm >= 0.0f && k_dm <= 1.0f)) ok = 0;
    if (!(k_cs >= 0.0f && k_cs <= 1.0f)) ok = 0;
    if (!(k_rr >= 0.0f && k_rr <= 1.0f)) ok = 0;
    if (!(k_rs >= 0.0f && k_rs <= 1.0f)) ok = 0;
    if (!(k_rm >= 0.0f && k_rm <= 1.0f)) ok = 0;
    if (!(k_rb >= 0.0f && k_rb <= 1.0f)) ok = 0;

    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    int rotor = k_rr < 0.25f ? 0 : (k_rr < 0.75f ? 1 : 2);
    int fresh = (s->primed != 1.0f);

    if (fresh) {
        volatile uint32_t *wb_u32 = (volatile uint32_t *)w;
        unsigned n;
        for (n = 0; n < sizeof(CfmWorkBuffer) / 4u; n++)
            wb_u32[n] = 0u;

        s->dly_time   = 1000.0f * k_dt;
        s->dly_mix    = k_dm;
        s->amp_drv    = k_ad;
        s->amp_mstr   = k_am;
        s->rotor_mode = (float)rotor;
        s->rot_spd    = k_rs;
        s->rig_blend  = k_rb;

        /* Delay snap */
        w->delay.wp = 0; w->delay.written = 0; w->delay.lp = 0.0f; w->delay.x1 = 0.0f;
        DelayCoeffs dk;
        delay_coeffs(&dk, s->dly_time, 0.92f * k_df, s->dly_mix);
        delay_snap(&w->delay, &dk);

        /* Derive networks */
        hw_coeffs(&w->hw_cache.k, s->amp_drv, k_at, 0.50f, k_ab, s->amp_mstr, 0.50f);
        w->hw_cache.key[0] = s->amp_drv;
        w->hw_cache.key[1] = k_at;
        w->hw_cache.key[2] = 0.50f;
        w->hw_cache.key[3] = k_ab;
        w->hw_cache.key[4] = s->amp_mstr;
        w->hw_cache.key[5] = 0.50f;
        w->hw_cache.fs = HW_FS_OS;

        ra_derive(w->ra_k.n1, w->ra_k.n2, 3, 0.55f, 0.70f, 0.45f, 0.50f, 1);
        w->ra_key[0] = 0.55f; w->ra_key[1] = 0.70f; w->ra_key[2] = 0.45f;
        w->ra_key[3] = 0.50f; w->ra_key[4] = 1.0f;
        w->ra_k.gx = rotor == 0 ? 1.0f : 0.0f;
        w->ra_k.out = k_rm;

        s->primed = 1.0f;
    } else {
        s->dly_time  += CFM_KNOB_SMOOTH * (1000.0f * k_dt - s->dly_time);
        s->dly_mix   += CFM_KNOB_SMOOTH * (k_dm - s->dly_mix);
        s->amp_drv   += CFM_KNOB_SMOOTH * (k_ad - s->amp_drv);
        s->amp_mstr  += CFM_KNOB_SMOOTH * (k_am - s->amp_mstr);
        s->rotor_mode = (float)rotor;
        s->rot_spd   += CFM_KNOB_SMOOTH * (k_rs - s->rot_spd);
        s->rig_blend += CFM_KNOB_SMOOTH * (k_rb - s->rig_blend);

        if (w->hw_cache.key[0] != s->amp_drv || w->hw_cache.key[1] != k_at ||
            w->hw_cache.key[3] != k_ab || w->hw_cache.key[4] != s->amp_mstr) {
            hw_coeffs(&w->hw_cache.k, s->amp_drv, k_at, 0.50f, k_ab, s->amp_mstr, 0.50f);
            w->hw_cache.key[0] = s->amp_drv;
            w->hw_cache.key[1] = k_at;
            w->hw_cache.key[3] = k_ab;
            w->hw_cache.key[4] = s->amp_mstr;
        }
    }

    ra_rotor_coeffs(&w->ra_k, &w->ra, s->rot_spd, rotor);
    w->ra_k.out = k_rm;

    cfm_process_block(s, w, eff, fade);
}

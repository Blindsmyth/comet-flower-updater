/* cfmaster_kernel.h - CF Master: David Gilmour's 1979 Comfortably Numb studio rig
 * (Ram's Head Muff -> Electric Mistress -> MXR DDS-1 Delay -> Split:
 *   Hiwatt DR103 / WEM 4x12 || Alembic F-2B / 2x Yamaha RA-200 Rotary)
 * Designed for the TMS320C6745 DSP to the rules in docs/C6745_DESIGN.md.
 *
 * C6745 Architectural Highlights:
 * 1. Independent Work in the Serial NFB Loop:
 *    CF Watt's NFB loop is serial by design (~8.2k cycles/block at 2x, ~200 idle cycles
 *    per sample). The independent Alembic F-2B + Yamaha RA-200 rotary section
 *    (crossover biquads, angle phasor, and 6 Lagrange mic reads) is co-scheduled
 *    directly inside the idle functional units of the NFB loop.
 * 2. Stage-Off Profiling Switches:
 *    Compile-time switches CFM_STAGE_OFF_* allow profiling any single stage or
 *    subset of stages in isolation on hardware using tools/ua_bench.py.
 * 3. Memory Layout:
 *    Small per-instance state (CfmKernelState = 52 B <= 64 B before guard word) in instance[2].
 *    Bulk state, filters and delay lines (CfmWorkBuffer <= 529,200 B) in instance[3].
 */
#ifndef CFMASTER_KERNEL_H
#define CFMASTER_KERNEL_H

#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"

/* Stage-off profiling switches (0 = active, 1 = bypass stage) */
#ifndef CFM_STAGE_OFF_MUFF
#define CFM_STAGE_OFF_MUFF   0
#endif
#ifndef CFM_STAGE_OFF_MISTRX
#define CFM_STAGE_OFF_MISTRX 0
#endif
#ifndef CFM_STAGE_OFF_DELAY
#define CFM_STAGE_OFF_DELAY  0
#endif
#ifndef CFM_STAGE_OFF_WATT
#define CFM_STAGE_OFF_WATT   0
#endif
#ifndef CFM_STAGE_OFF_RA200
#define CFM_STAGE_OFF_RA200  0
#endif

/* Preamp/Muff oversampling and nodal analysis configuration */
#define MNA_MAXN 10
#define MNA_MAXU 1
#ifndef HW_OS
#define HW_OS 2
#endif

#include "muff_g1.h"
#include "hiwatt_amp.h"
#include "hiwatt_cab.h"
#include "mistress_g1.h"
#if defined(__TI_COMPILER_VERSION__)
#define CE2_SAT_BLOB
#endif
#include "delay_g1.h"
#include "ra200_g1.h"

#define CFM_KNOB_SMOOTH 0.1f

/* --- Per-Instance Slot State (instance[2] words 0..12, guard word at 16) - */
typedef struct {
    float muff_sus, muff_tone, muff_vol;
    float mist_rate, mist_color;
    float dly_time, dly_mix;
    float amp_drv, amp_mstr;
    float rot_spd, rig_blend;
    float rotor_mode;               /* 0 = off, 1 = slow, 2 = fast */
    float primed;
} CfmKernelState;

typedef char cfm_state_fits[(sizeof(CfmKernelState) <= SH_STATE_BYTES) ? 1 : -1];

/* --- Cached Network Coefficients for Hiwatt ------------------------------ */
typedef struct {
    float key[6];                   /* vol, tre, mid, bas, mas, pre */
    float fs;
    HwCoeffs k;
} HwCoeffCache;

/* --- Bulk State & Delay Lines in Slot Work Buffer (instance[3]) ---------- */
typedef struct {
    MuffState muff;                 /* 132 B */
    HwState hw;                     /* 292 B */
    HwCoeffCache hw_cache;          /* ~396 B */
    RaState ra;                     /* 848 B */
    RaCoeffs ra_k;                  /* ~160 B */
    float ra_key[5];                /* 20 B */
    MistressState mistress;         /* ~2120 B */
    uint32_t align_pad[4];
    DelayState delay;               /* 524,308 B */
} CfmWorkBuffer;

/* Check that the work buffer fits within the 0x81330 (529,200 B) allocation */
typedef char cfm_work_fits[(sizeof(CfmWorkBuffer) <= 0x81330u) ? 1 : -1];

TS_INLINE CfmWorkBuffer *cfm_work(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(CfmWorkBuffer))
        return 0;
    return (CfmWorkBuffer *)wb[0];
}

/* --- Co-scheduled Hiwatt NFB loop + Yamaha RA-200 Rotary Processing ------ */
/* The 32 iterations of the 2x Hiwatt NFB loop interleave the 16 samples of
 * RA-200 rotary filtering, crossover, and mic reads. During the ~200 cycles of
 * serial latency per NFB sample, the C6745 functional units execute the RA-200.
 */
TS_INLINE void cfm_watt_ra_block(HwState *HW_RESTRICT hs, const HwCoeffs *HW_RESTRICT hk,
                                 RaState *HW_RESTRICT rs, const RaCoeffs *HW_RESTRICT rk,
                                 const float *HW_RESTRICT in_watt_2x,
                                 const float *HW_RESTRICT in_ra_1x,
                                 float *HW_RESTRICT out_watt_1x,
                                 float *HW_RESTRICT out_ra_L,
                                 float *HW_RESTRICT out_ra_R)
{
    float watt_2x[HW_NB];
    float lo[RA_NB], cs[2][2][RA_NB];
    unsigned int wp0 = rs->wp;
    int n;

    /* Precalculate rotor phasor angles for the 16 base-rate samples */
    int c;
    for (c = 0; c < 2; ++c) {
        float p0 = rs->phi[c], dp = rk->dphi[c];
        for (n = 0; n < RA_NB; ++n) {
            float p = p0 + dp * (float)(n + 1);
            p -= p > 3.14159265f ? 6.28318531f : 0.0f;
            ra_cossin(p, &cs[c][0][n], &cs[c][1][n]);
        }
        p0 += dp * (float)RA_NB;
        p0 -= p0 > 3.14159265f ? 6.28318531f : 0.0f;
        rs->phi[c] = p0;
    }

    /* Hiwatt preamp rail ramp */
    float pre = 1.0f - 0.3f * HW_SAG_DEPTH * hs->sag;
    float p0 = hs->pre_last != 0.0f ? hs->pre_last : pre;
    float dp = (pre - p0) * (1.0f / (float)HW_NB);
    hs->pre_last = pre;

    /* The Co-Scheduled Execution Loop:
     * HW_NB = 32 samples (2x oversampled Hiwatt NFB loop).
     * Iterations 0..15:  NFB sample n  + RA-200 crossover & line write for sample n.
     * Iterations 16..31: NFB sample n  + RA-200 fixed speaker EQ & mic reads for sample (n - 16).
     */
    {
        /* RA-200 Crossover & Speaker EQ state locals */
        float x0 = rs->xo[0], x1 = rs->xo[1], x2 = rs->xo[2], x3 = rs->xo[3];
        float x4 = rs->xo[4], x5 = rs->xo[5], x6 = rs->xo[6], x7 = rs->xo[7];
        float e0 = rs->eq[4], e1 = rs->eq[5], gx = rk->gx;
        float f0 = rs->eq[0], f1 = rs->eq[1], f2 = rs->eq[2], f3 = rs->eq[3];

        /* Hiwatt NFB Partial setup */
        const float *HW_RESTRICT m = hk->bh;
#define DA(i, j) MNA_DA(m, 5, 2, i, j)
#define DB(i, u) MNA_DB(m, 5, 2, i, u)
#define CY(i)    MNA_CY(m, 5, 2, i)
        const float c1 = CY(0) * DB(0, 1) + CY(1) * DB(1, 1) + CY(2) * DB(2, 1)
                       + CY(3) * DB(3, 1) + CY(4) * DB(4, 1);
        const float k1 = MNA_DY(m, 5, 2, 1) + c1;
        float hx0 = hs->xbh[0], hx1 = hs->xbh[1], hx2 = hs->xbh[2], hx3 = hs->xbh[3], hx4 = hs->xbh[4];
        float ub1 = hs->ub1, sag = hs->sag, axp = hs->ax[3], resid = hs->resid;
        float u0 = HW_H3 * in_watt_2x[0], s0 = u0 + hs->ub0;
        float q0, q1, q2, q3, q4, P;

#define CFM_NFB_PARTIAL()                                                       \
        q0 = DB(0, 0) * s0 + DA(0, 0) * hx0 + DA(0, 1) * hx1 + DA(0, 2) * hx2 + DA(0, 3) * hx3 + DA(0, 4) * hx4; \
        q1 = DB(1, 0) * s0 + DA(1, 0) * hx0 + DA(1, 1) * hx1 + DA(1, 2) * hx2 + DA(1, 3) * hx3 + DA(1, 4) * hx4; \
        q2 = DB(2, 0) * s0 + DA(2, 0) * hx0 + DA(2, 1) * hx1 + DA(2, 2) * hx2 + DA(2, 3) * hx3 + DA(2, 4) * hx4; \
        q3 = DB(3, 0) * s0 + DA(3, 0) * hx0 + DA(3, 1) * hx1 + DA(3, 2) * hx2 + DA(3, 3) * hx3 + DA(3, 4) * hx4; \
        q4 = DB(4, 0) * s0 + DA(4, 0) * hx0 + DA(4, 1) * hx1 + DA(4, 2) * hx2 + DA(4, 3) * hx3 + DA(4, 4) * hx4; \
        P = MNA_DY(m, 5, 2, 0) * u0 + (CY(0) * (hx0 + q0) + CY(1) * (hx1 + q1))               \
          + (CY(2) * (hx2 + q2) + CY(3) * (hx3 + q3) + CY(4) * (hx4 + q4));

        CFM_NFB_PARTIAL()

        for (n = 0; n < HW_NB; ++n) {
            /* 1. Serial Hiwatt NFB Step */
            float u1 = -resid, s1 = u1 + ub1, d, xi, y, r, rail, rpw;
            int ok;
            d = P + k1 * u1 + c1 * ub1;
            hx0 += q0 + DB(0, 1) * s1;
            hx1 += q1 + DB(1, 1) * s1;
            hx2 += q2 + DB(2, 1) * s1;
            hx3 += q3 + DB(3, 1) * s1;
            hx4 += q4 + DB(4, 1) * s1;
            ub1 = u1;
            {
                float u0n = HW_H3 * in_watt_2x[n + 1 < HW_NB ? n + 1 : n];
                s0 = u0n + u0;
                u0 = u0n;
                CFM_NFB_PARTIAL()
            }
            xi = d * (1.0f / HW_HPI);
            rail = p0 + dp * (float)(n + 1);
            y = hw_tube_fast(xi, axp, HW_BPI, HW_KPI, rail, HW_IPI, &ok);
            if (!ok) { float t = axp; y = hw_tube_adaa(xi, &t, HW_BPI, HW_KPI, rail, HW_IPI); }
            axp = xi;
            r = y < 0.0f ? -y : y;
            sag += (r - sag) * (r > sag ? HW_SAG_ATT : HW_SAG_REL);
            rpw = 1.0f - HW_SAG_DEPTH * sag;
            y = hw_tube(-y * HW_APIHPI * (0.5f / HW_HPWR), HW_BPW, HW_KPW, rpw, HW_IPW);
            y *= HW_VTAP;
            resid += HW_RESID_A * ((y - HW_KTAPLIN * d) - resid);
            watt_2x[n] = y * HW_OUT;

            /* 2. Interleaved Independent RA-200 Work */
            if (n < RA_NB) {
                /* Half 1 (iterations 0..15): Crossover, rotary delay write */
                float v = in_ra_1x[n] * RA_PRE_OUT;
                float l2 = RA_BQ(&x2, &x3, RA_XO_LP, RA_BQ(&x0, &x1, RA_XO_LP, v));
                float hi = RA_BQ(&x6, &x7, RA_XO_HP, RA_BQ(&x4, &x5, RA_XO_HP, v));
                lo[n] = l2 + gx * hi;
                rs->line[(wp0 + (unsigned int)n) & RA_LMASK] = RA_BQ(&e0, &e1, RA_RT_LP, (1.0f - gx) * hi);
            } else {
                /* Half 2 (iterations 16..31): Fixed speaker filter & mic reads for sample m */
                int m_idx = n - RA_NB;
                float lo_filtered = RA_BQ(&f2, &f3, RA_FX_LP, RA_BQ(&f0, &f1, RA_FX_HP, lo[m_idx]));
                unsigned int wp = (wp0 + (unsigned int)m_idx) & RA_LMASK;
                float micL = ra_mic(rs->line, wp, cs[0][0][m_idx], cs[0][1][m_idx]);
                float micR = ra_mic(rs->line, wp, cs[1][0][m_idx], cs[1][1][m_idx]);
                out_ra_L[m_idx] = rk->out * (lo_filtered + micL);
                out_ra_R[m_idx] = rk->out * (lo_filtered + micR);
            }
        }

        /* Save RA-200 states */
        rs->xo[0] = x0; rs->xo[1] = x1; rs->xo[2] = x2; rs->xo[3] = x3;
        rs->xo[4] = x4; rs->xo[5] = x5; rs->xo[6] = x6; rs->xo[7] = x7;
        rs->eq[4] = e0; rs->eq[5] = e1;
        rs->eq[0] = f0; rs->eq[1] = f1; rs->eq[2] = f2; rs->eq[3] = f3;
        rs->wp = (wp0 + RA_NB) & RA_LMASK;

        /* Save Hiwatt NFB states */
        hs->xbh[0] = hx0; hs->xbh[1] = hx1; hs->xbh[2] = hx2; hs->xbh[3] = hx3; hs->xbh[4] = hx4;
        hs->ub0 = u0; hs->ub1 = ub1; hs->sag = sag; hs->ax[3] = axp; hs->resid = resid;
#undef CFM_NFB_PARTIAL
#undef DA
#undef DB
#undef CY
    }

    /* Decimate Hiwatt 2x down to 1x */
    hbi1_down_blk(&hs->dn1, watt_2x, out_watt_1x, 16);
}

/* --- Main Block Processing for the 1979 Comfortably Numb Rig ------------- */
TS_INLINE void cfm_process_block(CfmKernelState *HW_RESTRICT s,
                                CfmWorkBuffer *HW_RESTRICT w,
                                float *HW_RESTRICT eff,
                                float fade)
{
    float b_muff[SH_FRAMES];
    float b_mist[SH_FRAMES];
    float dly_outL[SH_FRAMES], dly_outR[SH_FRAMES];
    float b_split[SH_FRAMES];
    float watt_out[SH_FRAMES];
    float ra_outL[SH_FRAMES], ra_outR[SH_FRAMES];
    int i;

    /* ---- 1. Ram's Head Big Muff ----------------------------------------- */
#if !CFM_STAGE_OFF_MUFF
    {
        MuffCoeffs mk;
        muff_coeffs(&mk, s->muff_sus, s->muff_tone, 0.5f * s->muff_vol);
        muff_block(&w->muff, &mk, eff, b_muff, SH_FRAMES);
    }
#else
    for (i = 0; i < SH_FRAMES; ++i) b_muff[i] = eff[i];
#endif

    /* ---- 2. Electric Mistress Flanger ----------------------------------- */
#if !CFM_STAGE_OFF_MISTRX
    {
        MistressCoeffs mist_k;
        mistress_coeffs(&mist_k, 0.05f + 9.95f * s->mist_rate * s->mist_rate,
                        0.7f, 0.95f * s->mist_color, 0.0f, 1.0f);
        mistress_block(&w->mistress, &mist_k, b_muff, b_mist, SH_FRAMES);
    }
#else
    for (i = 0; i < SH_FRAMES; ++i) b_mist[i] = b_muff[i];
#endif

    /* ---- 3. MXR DDS-1 Digital Delay (480 ms) ---------------------------- */
#if !CFM_STAGE_OFF_DELAY
    {
        DelayCoeffs dk;
        delay_coeffs(&dk, s->dly_time, 0.25f, s->dly_mix);
        delay_block(&w->delay, &dk, b_mist, dly_outL, dly_outR, SH_FRAMES);
        for (i = 0; i < SH_FRAMES; ++i) b_split[i] = dly_outL[i];
    }
#else
    for (i = 0; i < SH_FRAMES; ++i) b_split[i] = b_mist[i];
#endif

    /* ---- 4. Split to Amps: Hiwatt DR103 / WEM || Alembic F-2B / RA-200 -- */
#if !CFM_STAGE_OFF_WATT && !CFM_STAGE_OFF_RA200
    {
        /* A. Hiwatt Preamp passes (1x -> 2x upsampled) */
        float hw_pre_2x[HW_NB];
        float hw_v3_2x[HW_NB];
        hbi1_up_blk(&w->hw.up1, b_split, hw_pre_2x, 16);
        {
            float dx = w->hw.dcx, dy = w->hw.dcy;
            for (i = 0; i < HW_NB; ++i) {
                float v = hw_pre_2x[i] * HW_IN_SCALE, y = v - dx + HW_DC_R * dy;
                dx = v; dy = y;
                hw_pre_2x[i] = y * (1.0f / HW_H1);
            }
            w->hw.dcx = dx; w->hw.dcy = dy;
        }

        /* 3 preamp triode passes + 2 linear networks (V1, V2, tone stack, V3a) */
        {
            float tub[HW_NB];
            float pre = 1.0f - 0.3f * HW_SAG_DEPTH * w->hw.sag;
            float p0 = w->hw.pre_last != 0.0f ? w->hw.pre_last : pre;
            float dp = (pre - p0) * (1.0f / (float)HW_NB);
            int st;
            for (st = 0; st < 3; ++st) {
                const float *tp = hw_pre_par[st];
                hw_tube_block(hw_pre_2x, tub, &w->hw.ax[st], tp[0], tp[1], p0, dp, tp[2]);
                if (st == 0) {
                    hw_net2_block(w->hw_cache.k.v1, w->hw.xv1, &w->hw.uv1, tub, HW_MU3 * HW_H1, hw_pre_2x);
                    for (i = 0; i < HW_NB; ++i) hw_pre_2x[i] *= 1.0f / HW_H2;
                } else if (st == 1) {
                    hw_net5_block(w->hw_cache.k.st, w->hw.xst, &w->hw.ust, tub, HW_MU3 * HW_H2, hw_pre_2x);
                    for (i = 0; i < HW_NB; ++i) hw_pre_2x[i] *= 1.0f / HW_H3;
                }
            }
            for (i = 0; i < HW_NB; ++i) hw_v3_2x[i] = tub[i];
        }

        /* B. Alembic F-2B Preamp passes (at 1x) */
        float f2b_out[RA_NB];
        {
            float fa[RA_NB], fb[RA_NB];
            int st;
            for (i = 0; i < RA_NB; ++i) fa[i] = b_split[i] * (HW_IN_SCALE / RA_H);
            for (st = 0; st < 2; ++st) {
                ra_tube_block(fa, fb, &w->ra.ax[st]);
                if (st == 0) {
                    ra_net5_block(w->ra_k.n1, w->ra.x1, &w->ra.u1, fb, HW_MU3 * RA_H, fa);
                    for (i = 0; i < RA_NB; ++i) fa[i] *= 1.0f / RA_H;
                } else {
                    ra_net2_block(w->ra_k.n2, w->ra.x2, &w->ra.u2, fb, HW_MU3 * RA_H, fa);
                }
            }
            for (i = 0; i < RA_NB; ++i) f2b_out[i] = fa[i];
        }

        /* C. Co-Scheduled Hiwatt Power NFB Loop + Yamaha RA-200 Rotary */
        cfm_watt_ra_block(&w->hw, &w->hw_cache.k, &w->ra, &w->ra_k,
                          hw_v3_2x, f2b_out, watt_out, ra_outL, ra_outR);

        /* D. Hiwatt WEM 4x12 Cab filter */
        hw_cab_block(&w->hw, watt_out);
    }
#elif !CFM_STAGE_OFF_WATT
    /* Watt alone: runs standard hw_block with cab */
    for (i = 0; i < SH_FRAMES; ++i) watt_out[i] = b_split[i];
    hw_block(&w->hw, &w->hw_cache.k, watt_out, 1);
    for (i = 0; i < SH_FRAMES; ++i) { ra_outL[i] = 0.0f; ra_outR[i] = 0.0f; }
#elif !CFM_STAGE_OFF_RA200
    /* RA200 alone */
    ra_block(&w->ra, &w->ra_k, b_split, ra_outL, ra_outR);
    for (i = 0; i < SH_FRAMES; ++i) watt_out[i] = 0.0f;
#else
    for (i = 0; i < SH_FRAMES; ++i) {
        watt_out[i] = b_split[i];
        ra_outL[i] = b_split[i];
        ra_outR[i] = b_split[i];
    }
#endif

    /* ---- 5. Master Stereo Mixdown & Crossfade --------------------------- */
    {
        float blend = s->rig_blend;
        float watt_gain = 1.0f - 0.5f * blend;
        float ra_gain   = 0.5f + 0.5f * blend;

        for (i = 0; i < SH_FRAMES; ++i) {
            float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
            float wetL = watt_out[i] * watt_gain + ra_outL[i] * ra_gain;
            float wetR = watt_out[i] * watt_gain + ra_outR[i] * ra_gain;
            float a, b;

            if (!(wetL > -8.0f && wetL < 8.0f)) wetL = 0.0f;
            if (!(wetR > -8.0f && wetR < 8.0f)) wetR = 0.0f;

            a = da + fade * (wetL - da);
            b = db + fade * (wetR - db);

            if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
            if (!(b > -8.0f && b < 8.0f)) b = 0.0f;

            eff[i] = a;
            eff[i + SH_CH_B_OFFSET] = b;
        }
    }
}

#endif /* CFMASTER_KERNEL_H */

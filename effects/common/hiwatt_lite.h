/* hiwatt_lite.h - CF WattL: the cheaper Hiwatt core (same API as hiwatt_amp.h).
 * Starts as a verbatim copy of hiwatt_amp.h; the CF WattL job
 * (docs/helpers/HIWATT_LITE_BRIEF_2026-10-23.md) makes it cheaper.
 *
 * Original header of hiwatt_amp.h:
 * hiwatt_amp.h - Hiwatt DR103 Custom 100 (1971, #2130) for the Zoom G1 Four.
 *
 * A port of Comet Flower's desktop HiwattDR103Processor (the circuit model,
 * not the lean mobile line): the same chain at 4x (176.4 kHz),
 *   jack -> 68k/1M divider -> 5 Hz DC guard -> V1 tube -> V1 network ->
 *   V2 tube -> tone stack + master -> V3a tube -> back half (V3a, CF,
 *   presence, NFB divider, PI cathodes; linear NFB loop closed inside) ->
 *   PI tube -> EL34 push-pull tube with solid-state sag -> 16-ohm tap volts
 *   -> nonlinear NFB residual (30 kHz guard LP, one sample late)
 * then the datasheet Fane 4x12 cab at base rate.
 *
 * Differences from the desktop, each measured (tests/host/hiwatt_*):
 *   - the three networks are capacitor-state systems without the desktop's
 *     stray capacitors (hiwatt_nets.h), all re-derived in float every block
 *     by straight-line code generated for their fixed topologies
 *     (hiwatt_netgen.h, tools/gen_hw_nets.py; no knob tables);
 *   - ADAA in float, with the antiderivative split so it does not need the
 *     desktop's double precision (see hw_tube_adaa), on V1, V2, V3a and the
 *     PI; the EL34 pair without ADAA (no loss in worst alias on the bench);
 *   - polyphase IIR half-bands of our own design (os_hbiir.h);
 *   - the preamp and PI ceilings follow the sag as a ramp over each 16-sample
 *     block, one block late (the desktop: every sample; a per-block step
 *     left sidebands at -78 dB when the sag works hard); the power stage
 *     follows it per sample.
 * Tube transfer, bias points, headroom calibration, sag and NFB constants are
 * the desktop's (HiwattDR103Processor.cpp, AmpStages.h).
 *
 * Processing is block-oriented and stage-major (hw_block): resampling, each
 * preamp tube and each network run over a whole block before the next, with
 * their states in locals, so the C674x compiler can software-pipeline them;
 * only the NFB loop (back half, PI, sag, power, residual) runs sample by
 * sample, and its chain sets the cost (hw_nfb_block). Measured on the pedal,
 * the first sample-major version cost ~224k cycles per block (2026-10-05);
 * the 2026-10-15 redesign is ~36k static (docs/DR103_REDESIGN_2026-10-15.md).
 */
#ifndef HIWATT_LITE_H
#define HIWATT_LITE_H

#include "ts808_sd.h"          /* sd_expf, ts_rcp, TS_INLINE */
#include "os_hbiir.h"
#include "hiwatt_netgen.h"     /* the networks, straight-line (tools/gen_hw_nets.py) */
#include "hiwatt_cab.h"
#include "hw_blob.h"

/* Oversampling factor (build option; the effect is 4x, CF Watt2x is the 2x
 * build used to hear and measure what 4x buys, tools/ua_ab.py). The rate-
 * dependent constants: DC guard 1 - 2 pi 5 / fs, sag 1 - exp(-1 / (tau fs)),
 * guard LP 1 - exp(-2 pi 30k / fs); the 4x literals are the original ones. */
#ifndef HW_OS
#define HW_OS 4
#endif
#if HW_OS == 4
#define HW_FS_OS     176400.0f
#define HW_DC_R      0.9998219051783679f      /* 5 Hz DC guard at 176.4k */
#define HW_SAG_ATT   0.0011331443546039877f   /* 5 ms at 176.4k */
#define HW_SAG_REL   0.0002834065447940848f   /* 20 ms */
#define HW_RESID_A   0.6565002619092772f      /* 30 kHz guard LP */
#elif HW_OS == 2
#define HW_FS_OS     88200.0f
#define HW_DC_R      0.9996438103567359f      /* 5 Hz DC guard at 88.2k */
#define HW_SAG_ATT   0.002265004693079553f   /* 5 ms at 88.2k */
#define HW_SAG_REL   0.0005667327703184899f   /* 20 ms */
#define HW_RESID_A   0.8820079299316048f      /* 30 kHz guard LP */
#else
#error "HW_OS must be 2 or 4"
#endif
#define HW_IN_SCALE  1.8726591760299625f      /* 2 V full scale * 1M/(1M+68k) */
#define HW_H1        2.4f                     /* stage input clip points, Vpk */
#define HW_H2        3.8f
#define HW_H3        2.4f
#define HW_HPI       0.96f
#define HW_HPWR      38.0f
#define HW_APIHPI    (48.5f * 0.96f)
#define HW_VTAP      56.57f                   /* 100 W into the 16-ohm tap, peak */
#define HW_OUT       (1.0f / 62.0f)
#define HW_SAG_DEPTH 0.15f
#define HW_GRID      0.08f                    /* slope above the plate ceiling */
#define HW_LN2       0.6931471805599453f
#define HW_NB        (16 * HW_OS)             /* oversampled samples per 16-frame block */

/* restrict: without it the compiler assumes the block buffers may overlap and
 * serialises the tube fast pass (ii 123 instead of the resource bound) */
#if defined(__cplusplus)
#define HW_RESTRICT __restrict
#else
#define HW_RESTRICT restrict
#endif

/* per-stage bias, negative-half scale 1 - asym*0.15, idle output (subtracted) */
#define HW_B1  0.03f
#define HW_K1  0.9775f
#define HW_I1  0.029991003238820143f
#define HW_B2  (-0.02f)
#define HW_K2  0.985f
#define HW_I2  (-0.01969737375353197f)
#define HW_B3  0.02f
#define HW_K3  0.982f
#define HW_I3  0.019997333759930933f
#define HW_BPI (-0.05f)
#define HW_KPI 0.988f
#define HW_IPI (-0.04935887445838542f)
#define HW_BPW (-0.08f)
#define HW_KPW 0.997f
#define HW_IPW (-0.07959027980379797f)

typedef struct {
    HbiState1 up1, dn1;             /* 1x <-> 2x */
    HbiState2 up2, dn2;             /* 2x <-> 4x */
    float ax[4];                    /* ADAA: previous input of V1, V2, V3a, PI */
    float dcx, dcy;                 /* input DC guard */
    float xv1[2], xst[5], xbh[5];   /* network states (capacitor volts) */
    float uv1, ust, ub0, ub1;       /* previous network inputs */
    float resid, sag;               /* NFB residual, sag envelope */
    float pre_last;                 /* preamp ceiling at the end of the last block */
    float cab[HW_CAB_N][2];         /* cab biquads, TDF-II */
} HwState;                          /* 73 floats = 292 B, all zero = reset */

#define HW_V1_SZ MNA_SS_SIZE(2, 1)
#define HW_ST_SZ MNA_SS_SIZE(5, 2)              /* the stack: second input unused */
#define HW_BH_SZ MNA_SS_SIZE(5, 2)
typedef struct {
    float v1[HW_V1_SZ], st[HW_ST_SZ], bh[HW_BH_SZ];   /* packed (mna_ss.h) */
} HwCoeffs;                                          /* 93 floats */

/* knobs 0..1: Volume (Normal 470k-A), Treble, Middle, Bass, Master, Presence.
 * Every block (hiwatt_netgen.h; was ~25k cycles measured for the stack's
 * generic solve, plus 20.6 KB of V1 / back-half tables). The stack and the
 * back half share one copy of the dense tail (code size). */
TS_INLINE void hw_coeffs(HwCoeffs *k, float vol, float tre, float mid, float bas,
                         float mas, float pre)
{
    HwTail w;                       /* one, reused: the frame stays small */
    int i;
    hw_v1_derive(vol, HW_FS_OS, k->v1);
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
    for (i = 0; i < 2; ++i) {
        if (i)
            hw_bh_head(pre, HW_FS_OS, &w);
        else
            hw_stack_head(tre, mid, bas, mas, HW_FS_OS, &w);
        hw_tail_derive(&w, i ? k->bh : k->st);
    }
}

/* tanh, branch-free: odd polynomial below 0.25 (relative accuracy for small
 * signals, 8e-9), else a 256-segment cubic table on [0, 9] (abs. 4e-8).
 * ~40 cycles of latency instead of ~110 for exp + reciprocal. */
TS_INLINE float hw_tanh_acc(float m)
{
    float a = m < 0.0f ? -m : m, m2 = m * m, m4 = m2 * m2, p, xt, f, v;
    const float *c;
    int i;
    p = m * ((1.0f - m2 * (1.0f / 3)) + m4 * ((2.0f / 15 - m2 * (17.0f / 315))
                                              + m4 * (62.0f / 2835)));
    xt = (a < HW_TANH_XMAX - 0.001f ? a : HW_TANH_XMAX - 0.001f) * (HW_TANH_N / HW_TANH_XMAX);
    i = (int)xt;
    f = xt - (float)i;
    c = hw_tanhtab + 4 * i;
    v = (c[0] + f * c[1]) + (f * f) * (c[2] + f * c[3]);
    if (m < 0.0f) v = -v;
    return a < 0.25f ? p : v;
}

/* AmpStages::tubeStage minus its idle output (the networks see AC only) */
TS_INLINE float hw_tube(float x, float bias, float kneg, float ceil, float idle)
{
    float u = x + bias, y;
    if (u > ceil) u = ceil + (u - ceil) * HW_GRID;
    y = hw_tanh_acc(u);
    if (y < 0.0f) y *= kneg;
    return y - idle;
}

/* ADAA in float. The desktop's antiderivative (AmpStages::tubeStageF: asym-
 * scaled negative half, tanh, grid clip above the ceiling c with slope a =
 * 0.08) makes the ADAA output, inside one region, the mean of a tanh:
 *   u < 0:       k * mean tanh(u)        over the step
 *   0 <= u <= c:     mean tanh(u)
 *   u > c:           mean tanh(t),  t = a u + c (1 - a)
 * and the mean of tanh over [p, q] has an exact form with no cancellation,
 *   mean = atanh(tanh(m) tanh(d)) / d = tanh(m) [tanh(d)/d] [atanh(z)/z],
 *   m = (p+q)/2, d = (q-p)/2, z = tanh(m) tanh(d),
 * whose last two factors are short series for small steps. Its error is
 * relative to the output (~1e-7), so small signals get no absolute noise
 * floor (the direct F(x) - F(x1) quotient leaves ~1e-7 absolute, which the
 * tone stack's 50 dB bass cut turned into a -63 dB floor at low levels).
 * Steps >= HW_ADAA_BIG use the direct quotient, well conditioned there. */
#define HW_ADAA_BIG 0.25f

/* mean of tanh over [p, p + 2d], |d| < HW_ADAA_BIG / 2 (times a, region 2) */
TS_INLINE float hw_mean_tanh(float p, float d)
{
    /* tanh(d)/d and tanh(d) depend on the step only, off the critical path;
     * atanh(z)/z in Estrin form, z^8/9 dropped (|z| < tanh(1/8): < 7e-9) */
    float tm = hw_tanh_acc(p + d), d2 = d * d, z, z2, z4;
    float tdd = 1.0f - d2 * (1.0f / 3 - d2 * (2.0f / 15 - d2 * (17.0f / 315 - d2 * (62.0f / 2835))));
    float td = d * tdd, tt = tm * tdd;
    z = tm * td;
    z2 = z * z;
    z4 = z2 * z2;
    return tt * ((1.0f + z2 * (1.0f / 3)) + z4 * (1.0f / 5 + z2 * (1.0f / 7)));
}

TS_INLINE float hw_g(float t)            /* log1p(e^-2t), t >= 0 */
{
    float z = sd_expf(-2.0f * t);
    float sv = z * ts_rcp(2.0f + z), s2 = sv * sv;   /* log1p(z) = 2 atanh(z/(2+z)) */
    return 2.0f * sv * (1.0f + s2 * (1.0f / 3 + s2 * (1.0f / 5 + s2 * (1.0f / 7
           + s2 * (1.0f / 9 + s2 * (1.0f / 11 + s2 * (1.0f / 13)))))));
}

/* ADAA output over [ua, ua + du] inside one region. Every region's transfer
 * is W tanh(A u + B): (k, 1, 0) below zero, (1, 1, 0) up to the ceiling,
 * (1, a, c(1-a)) above it, so one code path serves all three (code size: the
 * kernel must fit the G1's 30 KB code region with five stages inlined). */
TS_INLINE float hw_q(int reg, float ua, float du, float kneg, float c)
{
    float W = reg == 0 ? kneg : 1.0f;
    float A = reg == 2 ? HW_GRID : 1.0f;
    float t1 = A * ua + (reg == 2 ? c * (1.0f - HW_GRID) : 0.0f), dt = A * du;
    float ad = du < 0.0f ? -du : du;
    if (ad < HW_ADAA_BIG)
        return W * hw_mean_tanh(t1, 0.5f * dt);
    {   /* large step: ln cosh t = |t| + g(|t|) - ln2, t keeps its sign in a region */
        float t2 = t1 + dt, a1 = t1 < 0.0f ? -t1 : t1, a2 = t2 < 0.0f ? -t2 : t2;
        /* (|t2| - |t1|) / dt is exactly the sign of t inside a region */
        return W * ((t1 < 0.0f ? -1.0f : 1.0f) + (hw_g(a2) - hw_g(a1)) * ts_rcp(dt));
    }
}

/* ADAA tube stage. A step that crosses a region boundary is split there (F is
 * continuous), so every piece uses the same-region formula. */
TS_INLINE float hw_tube_adaa(float x, float *x1, float bias, float kneg, float ceil,
                             float idle)
{
    /* everything in u: the bias addition rounds u and u1 independently, so
     * the step must be u - u1 itself for the pieces to sum to it */
    float u = x + bias, u1 = *x1 + bias, du = u - u1, lo, hi, acc = 0.0f;
    int r, rlo, rhi;
    *x1 = x;
    if (du == 0.0f) return hw_q(u < 0.0f ? 0 : (u <= ceil ? 1 : 2), u, 0.0f, kneg, ceil) - idle;
    lo = du > 0.0f ? u1 : u;
    hi = du > 0.0f ? u : u1;
    rlo = lo < 0.0f ? 0 : (lo <= ceil ? 1 : 2);
    rhi = hi < 0.0f ? 0 : (hi <= ceil ? 1 : 2);
    for (r = rlo; r <= rhi; ++r) {                 /* integrate lo -> hi by region */
        float a = r == rlo ? lo : (r == 1 ? 0.0f : ceil);
        float b = r == rhi ? hi : (r == 0 ? 0.0f : ceil);
        if (b > a) acc += (b - a) * hw_q(r, a, b - a, kneg, ceil);
    }
    return acc * ts_rcp(hi - lo) - idle;
}

/* the cab over a 16-sample block, in place, in two passes (biquads 0-4,
 * then 5-8): a sample loop outside, the biquads unrolled inside with their
 * states in locals, so the compiler pipelines across samples. All nine in one
 * loop need 45 coefficients + 18 states: register pressure pushed it from
 * the resource bound (23) to ii 79. */
#define HW_CAB_PASS(first, cnt)                                                \
    for (i = first; i < first + cnt; ++i) { z[i][0] = s->cab[i][0]; z[i][1] = s->cab[i][1]; } \
    for (n = 0; n < 16; ++n) {                                                 \
        float x = io[n];                                                       \
        HW_CAB_UNROLL(cnt)                                                     \
        for (i = first; i < first + cnt; ++i) {                                \
            const float *c = hw_cab[i];                                        \
            float y = c[0] * x + z[i][0];                                      \
            z[i][0] = c[1] * x - c[3] * y + z[i][1];                           \
            z[i][1] = c[2] * x - c[4] * y;                                     \
            x = y;                                                             \
        }                                                                      \
        io[n] = x;                                                             \
    }                                                                          \
    for (i = first; i < first + cnt; ++i) { s->cab[i][0] = z[i][0]; s->cab[i][1] = z[i][1]; }
#if defined(__TI_COMPILER_VERSION__)
#define HW_CAB_PRAGMA(x) _Pragma(#x)
#define HW_CAB_UNROLL(cnt) HW_CAB_PRAGMA(UNROLL(cnt))
#else
#define HW_CAB_UNROLL(cnt)
#endif
TS_INLINE void hw_cab_block(HwState *s, float *io)
{
    float z[HW_CAB_N][2];
    int i, n;
    HW_CAB_PASS(0, 5)
    HW_CAB_PASS(5, 4)
}
#undef HW_CAB_PASS

/* bias, negative-half scale, idle output of V1, V2, V3a (PI and EL34: inline) */
static const float hw_pre_par[3][3] = {
    { HW_B1, HW_K1, HW_I1 }, { HW_B2, HW_K2, HW_I2 }, { HW_B3, HW_K3, HW_I3 },
};

/* Fast ADAA: the same-region, small-step case (nearly every sample), with no
 * branches and no division, so a loop over a block software-pipelines.
 * Sets *ok to 0 when the step crosses a region boundary or is large; the
 * caller then uses hw_tube_adaa for that sample. */
TS_INLINE float hw_tube_fast(float x, float x1, float bias, float kneg, float ceil,
                             float idle, int *ok)
{
    float u = x + bias, u1 = x1 + bias, du = u - u1, adu = du < 0.0f ? -du : du;
    int r = u < 0.0f ? 0 : (u <= ceil ? 1 : 2), r1 = u1 < 0.0f ? 0 : (u1 <= ceil ? 1 : 2);
    float W = r1 == 0 ? kneg : 1.0f, A = r1 == 2 ? HW_GRID : 1.0f;
    float t1 = A * u1 + (r1 == 2 ? ceil * (1.0f - HW_GRID) : 0.0f);
    *ok = (r == r1) & (adu < HW_ADAA_BIG);
    return W * hw_mean_tanh(t1, 0.5f * A * du) - idle;
}

/* the test of hw_tube_fast alone: same region and a small step */
TS_INLINE int hw_fast_ok(float x, float x1, float bias, float ceil)
{
    float u = x + bias, u1 = x1 + bias, du = u - u1;
    int r = u < 0.0f ? 0 : (u <= ceil ? 1 : 2), r1 = u1 < 0.0f ? 0 : (u1 <= ceil ? 1 : 2);
    return (r == r1) & (du < HW_ADAA_BIG) & (du > -HW_ADAA_BIG);
}

/* one preamp tube stage over the block: y[n] from x[n] (x scaled to the
 * stage's clip units), previous input in *x1, ceiling c0 + dc (n + 1) */
TS_INLINE void hw_tube_block(const float *HW_RESTRICT x, float *HW_RESTRICT y, float *x1,
                             float bias, float kneg, float c0, float dc, float idle)
{
    float d_buf[HW_NB], w_buf[HW_NB];
    int n;
    float prev = *x1;

    /* Pass 1: input geometry, region selection, and tanh(m) */
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(HW_NB, HW_NB, HW_NB)
#endif
    for (n = 0; n < HW_NB; ++n) {
        float xp = n == 0 ? prev : x[n - 1];
        float c = c0 + dc * (float)(n + 1);
        float u1 = xp + bias, du = x[n] - xp;
        int r1 = u1 < 0.0f ? 0 : (u1 <= c ? 1 : 2);
        float W = r1 == 0 ? kneg : 1.0f;
        float A = r1 == 2 ? HW_GRID : 1.0f;
        float t1 = A * u1 + (r1 == 2 ? c * (1.0f - HW_GRID) : 0.0f);
        float d = 0.5f * A * du;
        y[n] = hw_tanh_acc(t1 + d);
        d_buf[n] = d;
        w_buf[n] = W;
    }

    /* Pass 2: tanh(d)/d, atanh(z)/z series, and scaling */
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(HW_NB, HW_NB, HW_NB)
#endif
    for (n = 0; n < HW_NB; ++n) {
        float d = d_buf[n], tm = y[n], W = w_buf[n];
        float d2 = d * d, z, z2, z4;
        float tdd = 1.0f - d2 * (1.0f / 3 - d2 * (2.0f / 15 - d2 * (17.0f / 315 - d2 * (62.0f / 2835))));
        float td = d * tdd, tt = tm * tdd;
        z = tm * td;
        z2 = z * z;
        z4 = z2 * z2;
        y[n] = W * (tt * ((1.0f + z2 * (1.0f / 3)) + z4 * (1.0f / 5 + z2 * (1.0f / 7)))) - idle;
    }
    /* rare exact fix-ups. The test is recomputed in its own pass, cheaply (no
     * tanh; storing a flag from the fast pass costs it ii 46 instead of 26,
     * register pressure), and branch-free: it lists the samples to fix, so
     * only those run the branchy exact path (a fix-up test inside one loop
     * kept that loop from pipelining: ~40 cycles per sample). */
    {
        unsigned char idx[HW_NB];   /* bytes: the frame stays small */
        int cnt = 0, i;
        for (n = 0; n < HW_NB; ++n) {
            float xp = n == 0 ? prev : x[n - 1], c = c0 + dc * (float)(n + 1);
            idx[cnt] = n;
            cnt += !hw_fast_ok(x[n], xp, bias, c);
        }
        for (i = 0; i < cnt; ++i) {
            float xp, c, t;
            n = idx[i];
            xp = n == 0 ? prev : x[n - 1];
            c = c0 + dc * (float)(n + 1);
            t = xp;
            y[n] = hw_tube_adaa(x[n], &t, bias, kneg, c, idle);
        }
    }
    *x1 = x[HW_NB - 1];
}

/* One-input networks over the block: y[n] = net(g * v[n]), delta form
 * (mna_ss.h). Written per size with the products summed as trees: the
 * sequential "acc +=" chain set the loop-carried bound (stack: 36 cycles per
 * sample); the compiler may not reassociate floats itself. States and the
 * previous input in locals (through the pointers the recurrence went via
 * memory). */
TS_INLINE void hw_net2_block(const float *HW_RESTRICT m, float *HW_RESTRICT xs,
                             float *HW_RESTRICT up, const float *HW_RESTRICT v, float g,
                             float *HW_RESTRICT y)
{
    float x0 = xs[0], x1 = xs[1], ul = *up;
    const float a00 = MNA_DA(m, 2, 1, 0, 0), a01 = MNA_DA(m, 2, 1, 0, 1);
    const float a10 = MNA_DA(m, 2, 1, 1, 0), a11 = MNA_DA(m, 2, 1, 1, 1);
    const float b0 = MNA_DB(m, 2, 1, 0, 0), b1 = MNA_DB(m, 2, 1, 1, 0);
    const float c0 = MNA_CY(m, 2, 1, 0), c1 = MNA_CY(m, 2, 1, 1), e = MNA_DY(m, 2, 1, 0);
    int n;
    for (n = 0; n < HW_NB; ++n) {
        float u = g * v[n], su = u + ul;
        float d0 = (b0 * su + a00 * x0) + a01 * x1;
        float d1 = (b1 * su + a11 * x1) + a10 * x0;
        x0 += d0;
        x1 += d1;
        ul = u;
        y[n] = e * u + (c0 * x0 + c1 * x1);
    }
    xs[0] = x0; xs[1] = x1; *up = ul;
}

TS_INLINE void hw_net5_block(const float *HW_RESTRICT m, float *HW_RESTRICT xs,
                             float *HW_RESTRICT up, const float *HW_RESTRICT v, float g,
                             float *HW_RESTRICT y)
{
#define A(i, j) MNA_DA(m, 5, 2, i, j)
#define ROW(i) ((MNA_DB(m, 5, 2, i, 0) * su + A(i, 0) * x0) \
                + ((A(i, 1) * x1 + A(i, 2) * x2) + (A(i, 3) * x3 + A(i, 4) * x4)))
    float x0 = xs[0], x1 = xs[1], x2 = xs[2], x3 = xs[3], x4 = xs[4], ul = *up;
    int n;
    for (n = 0; n < HW_NB; ++n) {
        float u = g * v[n], su = u + ul;
        float d0 = ROW(0), d1 = ROW(1), d2 = ROW(2), d3 = ROW(3), d4 = ROW(4);
        x0 += d0; x1 += d1; x2 += d2; x3 += d3; x4 += d4;
        ul = u;
        y[n] = MNA_DY(m, 5, 2, 0) * u + ((MNA_CY(m, 5, 2, 0) * x0 + MNA_CY(m, 5, 2, 1) * x1)
               + (MNA_CY(m, 5, 2, 2) * x2 + (MNA_CY(m, 5, 2, 3) * x3 + MNA_CY(m, 5, 2, 4) * x4)));
    }
    xs[0] = x0; xs[1] = x1; xs[2] = x2; xs[3] = x3; xs[4] = x4; *up = ul;
#undef ROW
#undef A
}

/* The NFB loop over the block: back half (u0 = V3a grid volts, x[] in H3
 * units; u1 = -residual), PI, sag, power stage, tap, residual; y[] = output.
 *
 * The residual closes a loop through the PI, the sag and the power stage, one
 * sample late, so this loop is serial: its cost is the length of that chain.
 * Variants scored on the 16x bench (tests/host/hiwatt_accuracy.cpp) to allow
 * pipelining, all rejected: residual 2-4 samples late (max harmonic error
 * 16 -> 25-32 dB); a branch-free PI with a midpoint fallback (worst alias
 * -46 -> -30 dB); the NFB section at 2x (23 dB / -39 dB).
 * What shortens the chain instead:
 *   - the residual-independent part of the back half (q, P) for sample n+1
 *     is computed in iteration n, so d is one multiply-add after the residual;
 *   - the PI rail ramps over the block like the preamp rails (no bench change);
 *   - locals instead of the struct (the recurrences went through memory). */
TS_INLINE void hw_nfb_block(HwState *s, const float *HW_RESTRICT m,
                            const float *HW_RESTRICT x, float *HW_RESTRICT out,
                            float p0, float dp)
{
#define DA(i, j) MNA_DA(m, 5, 2, i, j)
#define DB(i, u) MNA_DB(m, 5, 2, i, u)
#define CY(i)    MNA_CY(m, 5, 2, i)
    /* d = DY0 u0 + DY1 u1 + CY . (xo + q + DB1 s1), s1 = u1 + ub1:
     *   = P + k1 u1 + c1 ub1,  P = DY0 u0 + CY . (xo + q) */
    const float c1 = CY(0) * DB(0, 1) + CY(1) * DB(1, 1) + CY(2) * DB(2, 1)
                   + CY(3) * DB(3, 1) + CY(4) * DB(4, 1);
    const float k1 = MNA_DY(m, 5, 2, 1) + c1;
    float x0 = s->xbh[0], x1 = s->xbh[1], x2 = s->xbh[2], x3 = s->xbh[3], x4 = s->xbh[4];
    float ub1 = s->ub1, sag = s->sag, axp = s->ax[3], resid = s->resid;
    float u0 = HW_H3 * x[0], s0 = u0 + s->ub0;
    float q0, q1, q2, q3, q4, P;
    int n;
#define HW_NFB_PARTIAL()                                                        \
    q0 = DB(0, 0) * s0 + DA(0, 0) * x0 + DA(0, 1) * x1 + DA(0, 2) * x2 + DA(0, 3) * x3 + DA(0, 4) * x4; \
    q1 = DB(1, 0) * s0 + DA(1, 0) * x0 + DA(1, 1) * x1 + DA(1, 2) * x2 + DA(1, 3) * x3 + DA(1, 4) * x4; \
    q2 = DB(2, 0) * s0 + DA(2, 0) * x0 + DA(2, 1) * x1 + DA(2, 2) * x2 + DA(2, 3) * x3 + DA(2, 4) * x4; \
    q3 = DB(3, 0) * s0 + DA(3, 0) * x0 + DA(3, 1) * x1 + DA(3, 2) * x2 + DA(3, 3) * x3 + DA(3, 4) * x4; \
    q4 = DB(4, 0) * s0 + DA(4, 0) * x0 + DA(4, 1) * x1 + DA(4, 2) * x2 + DA(4, 3) * x3 + DA(4, 4) * x4; \
    P = MNA_DY(m, 5, 2, 0) * u0 + (CY(0) * (x0 + q0) + CY(1) * (x1 + q1))                \
      + (CY(2) * (x2 + q2) + CY(3) * (x3 + q3) + CY(4) * (x4 + q4));
    HW_NFB_PARTIAL()
    for (n = 0; n < HW_NB; ++n) {
        float u1 = -resid, s1 = u1 + ub1, d, xi, y, r, rail, rpw;
        int ok;
        d = P + k1 * u1 + c1 * ub1;
        x0 += q0 + DB(0, 1) * s1;                   /* delta form: the small */
        x1 += q1 + DB(1, 1) * s1;                   /* step first, then the  */
        x2 += q2 + DB(2, 1) * s1;                   /* state                 */
        x3 += q3 + DB(3, 1) * s1;
        x4 += q4 + DB(4, 1) * s1;
        ub1 = u1;
        {                                           /* sample n+1's partials */
            float u0n = HW_H3 * x[n + 1 < HW_NB ? n + 1 : n];
            s0 = u0n + u0;
            u0 = u0n;
            HW_NFB_PARTIAL()
        }

        /* PI (LTP), ADAA, preamp rail (ramped over the block) */
        xi = d * (1.0f / HW_HPI);
        rail = p0 + dp * (float)(n + 1);
        y = hw_tube_fast(xi, axp, HW_BPI, HW_KPI, rail, HW_IPI, &ok);
        if (!ok) { float t = axp; y = hw_tube_adaa(xi, &t, HW_BPI, HW_KPI, rail, HW_IPI); }
        axp = xi;
        r = y < 0.0f ? -y : y;                      /* sag from the PI output */
        sag += (r - sag) * (r > sag ? HW_SAG_ATT : HW_SAG_REL);
        rpw = 1.0f - HW_SAG_DEPTH * sag;
        /* PI diff output (the LTP inverts grid a) -> per-side EL34 grid vs 38 V.
         * The EL34 pair runs without ADAA: on the 16x reference bench it adds
         * nothing to the worst alias (-46.6 dB with V1/V2/V3a/PI ADAA only,
         * tests/host/hiwatt_accuracy.cpp masks), and it sits in this loop. */
        y = hw_tube(-y * HW_APIHPI * (0.5f / HW_HPWR), HW_BPW, HW_KPW, rpw, HW_IPW);
        y *= HW_VTAP;                               /* 16-ohm tap volts */
        resid += HW_RESID_A * ((y - HW_KTAPLIN * d) - resid);
        out[n] = y * HW_OUT;
    }
    s->xbh[0] = x0; s->xbh[1] = x1; s->xbh[2] = x2; s->xbh[3] = x3; s->xbh[4] = x4;
    s->ub0 = u0; s->ub1 = ub1; s->sag = sag; s->ax[3] = axp; s->resid = resid;
#undef HW_NFB_PARTIAL
#undef DA
#undef DB
#undef CY
}

/* One 16-frame block through the amp, in place; the cab unless cab_on is 0. */
TS_INLINE void hw_block(HwState *s, const HwCoeffs *k, float *io, int cab_on)
{
    float a[HW_NB], b[HW_NB];
    float pre, p0, dp;
    int n, st;

#if HW_OS == 4
    hbi1_up_blk(&s->up1, io, b, 16);                /* 1x -> 2x -> 4x, stage-major */
    hbi2_up_blk(&s->up2, b, a, 32);
#else
    hbi1_up_blk(&s->up1, io, a, 16);                /* 1x -> 2x */
#endif
    {                                               /* jack volts, DC guard, V1 units */
        float dx = s->dcx, dy = s->dcy;
        for (n = 0; n < HW_NB; ++n) {
            float v = a[n] * HW_IN_SCALE, y = v - dx + HW_DC_R * dy;
            dx = v;
            dy = y;
            a[n] = y * (1.0f / HW_H1);
        }
        s->dcx = dx;
        s->dcy = dy;
    }
    /* preamp rails: 30 % of the sag, ramped over the block from last block's
     * end (all-zero state: pre_last 0 means "not set yet") */
    pre = 1.0f - 0.3f * HW_SAG_DEPTH * s->sag;
    p0 = s->pre_last != 0.0f ? s->pre_last : pre;
    dp = (pre - p0) * (1.0f / HW_NB);
    s->pre_last = pre;

    /* V1 -> V1 net -> V2 -> tone stack -> V3a, one stage per pass (one
     * inlined copy of the tube code: .text must fit the 30 KB code region) */
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
    for (st = 0; st < 3; ++st) {
        const float *tp = hw_pre_par[st];
        hw_tube_block(a, b, &s->ax[st], tp[0], tp[1], p0, dp, tp[2]);
        if (st == 0) {
            hw_net2_block(k->v1, s->xv1, &s->uv1, b, HW_MU3 * HW_H1, a);
            for (n = 0; n < HW_NB; ++n) a[n] *= 1.0f / HW_H2;
        } else if (st == 1) {
            hw_net5_block(k->st, s->xst, &s->ust, b, HW_MU3 * HW_H2, a);
            for (n = 0; n < HW_NB; ++n) a[n] *= 1.0f / HW_H3;
        }
    }

    hw_nfb_block(s, k->bh, b, a, p0, dp);

#if HW_OS == 4
    hbi2_down_blk(&s->dn2, a, b, 32);               /* 4x -> 2x -> 1x, cab */
    hbi1_down_blk(&s->dn1, b, io, 16);
#else
    hbi1_down_blk(&s->dn1, a, io, 16);              /* 2x -> 1x, cab */
#endif
    if (cab_on)
        hw_cab_block(s, io);
}

#endif /* HIWATT_LITE_H */

/* hiwatt_amp.h - Hiwatt DR103 Custom 100 (1971, #2130) for the Zoom G1 Four.
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
 *     stray capacitors (hiwatt_nets.h); the tone stack (4 knobs) is
 *     re-derived in float every block, the V1 network (Volume) and the back
 *     half (Presence) come from tables derived at all 101 knob positions;
 *   - ADAA in float, with the antiderivative split so it does not need the
 *     desktop's double precision (see hw_tube_adaa);
 *   - polyphase IIR half-bands of our own design (os_hbiir.h);
 *   - the preamp tube ceilings follow the sag as a ramp over each 16-sample
 *     block, one block late (the desktop: every sample; a per-block step
 *     left sidebands at -78 dB when the sag works hard); the PI and power
 *     stages follow it per sample.
 * Tube transfer, bias points, headroom calibration, sag and NFB constants are
 * the desktop's (HiwattDR103Processor.cpp, AmpStages.h).
 *
 * Processing is block-oriented and stage-major (hw_block): each preamp tube
 * and network runs over all 64 4x samples of a block before the next, so the
 * C674x compiler can software-pipeline them; only the NFB loop (back half,
 * PI, power) runs sample by sample. Measured on the pedal, the first
 * sample-major version cost ~224k cycles per block (2026-10-05).
 */
#ifndef HIWATT_AMP_H
#define HIWATT_AMP_H

#include "ts808_sd.h"          /* sd_expf, ts_rcp, TS_INLINE */
#include "os_hbiir.h"
#include "hiwatt_nets.h"
#include "hiwatt_cab.h"
#include "hw_blob.h"

#define HW_FS_OS     176400.0f
#define HW_IN_SCALE  1.8726591760299625f      /* 2 V full scale * 1M/(1M+68k) */
#define HW_DC_R      0.9998219051783679f      /* 5 Hz DC guard at 176.4k */
#define HW_SAG_ATT   0.0011331443546039877f   /* 5 ms at 176.4k */
#define HW_SAG_REL   0.0002834065447940848f   /* 20 ms */
#define HW_RESID_A   0.6565002619092772f      /* 30 kHz guard LP */
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
#define HW_NB        64                       /* 4x samples per 16-frame block */
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
    float ax[5];                    /* ADAA: previous input of each tube stage */
    float dcx, dcy;                 /* input DC guard */
    float xv1[2], xst[5], xbh[5];   /* network states (capacitor volts) */
    float uv1, ust, ub0, ub1;       /* previous network inputs */
    float resid, sag;               /* NFB residual, sag envelope */
    float pre_last;                 /* preamp ceiling at the end of the last block */
    float cab[HW_CAB_N][2];         /* cab biquads, TDF-II */
} HwState;                          /* 74 floats = 296 B, all zero = reset */

#define HW_V1_SZ MNA_SS_SIZE(2, 1)
#define HW_ST_SZ MNA_SS_SIZE(5, 1)
#define HW_BH_SZ MNA_SS_SIZE(5, 2)
typedef struct {
    float v1[HW_V1_SZ], st[HW_ST_SZ], bh[HW_BH_SZ];   /* packed (mna_ss.h) */
} HwCoeffs;                                          /* 87 floats */

/* a table system at knob position kn (0..1): exact at the 101 positions */
TS_INLINE void hw_tabsys(float *out, int base, int sz, float kn)
{
    float pos = (kn < 0.0f ? 0.0f : (kn > 1.0f ? 1.0f : kn)) * 100.0f, fr;
    int i = (int)pos, j;
    const float *a, *b;
    if (i > 99) i = 99;
    fr = pos - (float)i;
    a = hw_blob + base + i * sz;
    b = a + sz;
    for (j = 0; j < sz; ++j) out[j] = a[j] + fr * (b[j] - a[j]);
}

/* knobs 0..1: Volume (Normal 470k-A), Treble, Middle, Bass, Master, Presence */
TS_INLINE void hw_coeffs(HwCoeffs *k, float vol, float tre, float mid, float bas,
                         float mas, float pre)
{
    hw_tabsys(k->v1, HW_BLOB_V1, HW_V1_SZ, vol);
    hw_tabsys(k->bh, HW_BLOB_BH, HW_BH_SZ, pre);
    {
        MnaNet n;
        float w[MNA_MAXN];
        hw_stack(&n, w, tre, mid, bas, mas);
        mna_derive(&n, w, HW_FS_OS, k->st);
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
    float tm = hw_tanh_acc(p + d), d2 = d * d, z, z2;
    float tdd = 1.0f - d2 * (1.0f / 3 - d2 * (2.0f / 15 - d2 * (17.0f / 315 - d2 * (62.0f / 2835))));
    z = tm * d * tdd;
    z2 = z * z;
    return tm * tdd * (1.0f + z2 * (1.0f / 3 + z2 * (1.0f / 5 + z2 * (1.0f / 7 + z2 * (1.0f / 9)))));
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

TS_INLINE float hw_cabinet(HwState *s, float x)
{
    int i;
    for (i = 0; i < HW_CAB_N; ++i) {
        const float *c = hw_cab[i];
        float y = c[0] * x + s->cab[i][0];
        s->cab[i][0] = c[1] * x - c[3] * y + s->cab[i][1];
        s->cab[i][1] = c[2] * x - c[4] * y;
        x = y;
    }
    return x;
}

/* bias, negative-half scale, idle output of V1, V2, V3a, PI, EL34 pair */
static const float hw_pre_par[5][3] = {
    { HW_B1, HW_K1, HW_I1 }, { HW_B2, HW_K2, HW_I2 }, { HW_B3, HW_K3, HW_I3 },
    { HW_BPI, HW_KPI, HW_IPI }, { HW_BPW, HW_KPW, HW_IPW },
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
    int n, ok;
    float prev = *x1;
    for (n = 0; n < HW_NB; ++n) {                   /* pipelined fast pass */
        float xp = n == 0 ? prev : x[n - 1], c = c0 + dc * (float)(n + 1);
        y[n] = hw_tube_fast(x[n], xp, bias, kneg, c, idle, &ok);
    }
    /* rare exact fix-ups. The test is recomputed here, cheaply (no tanh):
     * storing a flag from the fast pass costs it ii 46 instead of 26
     * (register pressure). */
    for (n = 0; n < HW_NB; ++n) {
        float xp = n == 0 ? prev : x[n - 1], c = c0 + dc * (float)(n + 1);
        if (!hw_fast_ok(x[n], xp, bias, c)) {
            float t = xp;
            y[n] = hw_tube_adaa(x[n], &t, bias, kneg, c, idle);
        }
    }
    *x1 = x[HW_NB - 1];
}

/* a one-input network over the block: y[n] = net(g * v[n]) */
TS_INLINE void hw_net_block(const float *HW_RESTRICT m, int k, float *HW_RESTRICT xs,
                            float *HW_RESTRICT up, const float *HW_RESTRICT v, float g,
                            float *HW_RESTRICT y)
{
    int n, i, j;
    for (n = 0; n < HW_NB; ++n) {
        float u = g * v[n], su = u + *up, dx[MNA_MAXK], o = MNA_DY(m, k, 1, 0) * u;
        for (i = 0; i < k; ++i) {
            float acc = MNA_DB(m, k, 1, i, 0) * su;
            for (j = 0; j < k; ++j) acc += MNA_DA(m, k, 1, i, j) * xs[j];
            dx[i] = acc;
        }
        for (i = 0; i < k; ++i) {
            xs[i] += dx[i];
            o += MNA_CY(m, k, 1, i) * xs[i];
        }
        *up = u;
        y[n] = o;
    }
}

/* One 16-frame block through the amp, in place; the cab unless cab_on is 0. */
TS_INLINE void hw_block(HwState *s, const HwCoeffs *k, float *io, int cab_on)
{
    float a[HW_NB], b[HW_NB];
    float pre, p0, dp;
    int n, ok, st;

    for (n = 0; n < 16; ++n) {                      /* 1x -> 4x */
        float p, q;
        hbi_up1(&s->up1, io[n], &p, &q);
        hbi_up2(&s->up2, p, &a[4 * n], &a[4 * n + 1]);
        hbi_up2(&s->up2, q, &a[4 * n + 2], &a[4 * n + 3]);
    }
    for (n = 0; n < HW_NB; ++n) {                   /* jack volts, DC guard, V1 units */
        float v = a[n] * HW_IN_SCALE, y = v - s->dcx + HW_DC_R * s->dcy;
        s->dcx = v;
        s->dcy = y;
        a[n] = y * (1.0f / HW_H1);
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
            hw_net_block(k->v1, 2, s->xv1, &s->uv1, b, HW_MU3 * HW_H1, a);
            for (n = 0; n < HW_NB; ++n) a[n] *= 1.0f / HW_H2;
        } else if (st == 1) {
            hw_net_block(k->st, 5, s->xst, &s->ust, b, HW_MU3 * HW_H2, a);
            for (n = 0; n < HW_NB; ++n) a[n] *= 1.0f / HW_H3;
        }
    }

    /* the NFB loop, sample by sample: back half (u0 = V3a grid volts,
     * u1 = -residual), PI, sag, power stage, tap, residual */
    for (n = 0; n < HW_NB; ++n) {
        const float *m = k->bh;
        float u0 = HW_H3 * b[n], u1 = -s->resid, s0 = u0 + s->ub0, s1 = u1 + s->ub1;
        float d = MNA_DY(m, 5, 2, 0) * u0 + MNA_DY(m, 5, 2, 1) * u1, dx[5], xi, y, r, t, rail;
        int i, j;
        /* fully unrolled: as a 5-trip software-pipelined loop it costs ii 30 */
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(5)
#endif
        for (i = 0; i < 5; ++i) {
            float acc = MNA_DB(m, 5, 2, i, 0) * s0 + MNA_DB(m, 5, 2, i, 1) * s1;
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(5)
#endif
            for (j = 0; j < 5; ++j) acc += MNA_DA(m, 5, 2, i, j) * s->xbh[j];
            dx[i] = acc;
        }
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(5)
#endif
        for (i = 0; i < 5; ++i) {
            s->xbh[i] += dx[i];
            d += MNA_CY(m, 5, 2, i) * s->xbh[i];
        }
        s->ub0 = u0;
        s->ub1 = u1;

        /* PI (LTP), then the EL34 pair: one pass each (one inlined copy) */
        y = d * (1.0f / HW_HPI);
        rail = 1.0f - 0.3f * HW_SAG_DEPTH * s->sag; /* PI: preamp rail */
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
        for (st = 3; st < 5; ++st) {
            const float *tp = hw_pre_par[st];
            xi = y;
            y = hw_tube_fast(xi, s->ax[st], tp[0], tp[1], rail, tp[2], &ok);
            if (!ok) { t = s->ax[st]; y = hw_tube_adaa(xi, &t, tp[0], tp[1], rail, tp[2]); }
            s->ax[st] = xi;
            if (st == 3) {
                r = y < 0.0f ? -y : y;              /* sag from the PI output */
                s->sag += (r - s->sag) * (r > s->sag ? HW_SAG_ATT : HW_SAG_REL);
                rail = 1.0f - HW_SAG_DEPTH * s->sag;
                /* PI diff output (the LTP inverts grid a) -> per-side EL34 grid vs 38 V */
                y = -y * HW_APIHPI * (0.5f / HW_HPWR);
            }
        }
        y *= HW_VTAP;                               /* 16-ohm tap volts */
        s->resid += HW_RESID_A * ((y - HW_KTAPLIN * d) - s->resid);
        a[n] = y * HW_OUT;
    }

    for (n = 0; n < 16; ++n) {                      /* 4x -> 1x, cab */
        float p = hbi_down2(&s->dn2, a[4 * n], a[4 * n + 1]);
        float q = hbi_down2(&s->dn2, a[4 * n + 2], a[4 * n + 3]);
        float x = hbi_down1(&s->dn1, p, q);
        io[n] = cab_on ? hw_cabinet(s, x) : x;
    }
}

#endif /* HIWATT_AMP_H */

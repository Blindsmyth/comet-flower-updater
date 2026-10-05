/* hiwatt_amp.h - Hiwatt DR103 Custom 100 (1971, #2130) for the Zoom G1 Four.
 *
 * A port of Comet Flower's desktop HiwattDR103Processor (the circuit model,
 * not the lean mobile line): the same per-sample chain at 4x (176.4 kHz),
 *   jack -> 68k/1M divider -> 5 Hz DC guard -> V1 tube -> V1 network ->
 *   V2 tube -> tone stack + master -> V3a tube -> back half (V3a, CF,
 *   presence, NFB divider, PI cathodes; linear NFB loop closed inside) ->
 *   PI tube -> EL34 push-pull tube with solid-state sag -> 16-ohm tap volts
 *   -> nonlinear NFB residual (30 kHz guard LP, one sample late)
 * then the datasheet Fane 4x12 cab at base rate.
 *
 * Differences from the desktop, each measured (tests/host/hiwatt_*):
 *   - the three networks are capacitor-state systems without the desktop's
 *     stray capacitors, re-derived in float every block (hiwatt_nets.h);
 *   - ADAA in float, with the antiderivative split so it does not need the
 *     desktop's double precision (see hw_tube_adaa);
 *   - polyphase IIR half-bands of our own design (os_hbiir.h), like the
 *     desktop's JUCE oversampler but with stated stopbands.
 * Tube transfer, bias points, headroom calibration, sag and NFB constants are
 * the desktop's (HiwattDR103Processor.cpp, AmpStages.h).
 */
#ifndef HIWATT_AMP_H
#define HIWATT_AMP_H

#include "ts808_sd.h"          /* sd_expf, ts_rcp, TS_INLINE */
#include "os_halfband.h"
#include "os_hbiir.h"
#include "hiwatt_nets.h"
#include "hiwatt_cab.h"

#define HW_FS_OS     176400.0f
#define HW_IN_SCALE  1.8726591760299625f      /* 2 V full scale * 1M/(1M+68k) */
#define HW_DC_R      0.9998219051783679f      /* 5 Hz DC guard at 176.4k */
#define HW_H1        2.4f                     /* stage input clip points, Vpk */
#define HW_H2        3.8f
#define HW_H3        2.4f
#define HW_HPI       0.96f
#define HW_HPWR      38.0f
#define HW_APIHPI    (48.5f * 0.96f)
#define HW_VTAP      56.57f                   /* 100 W into the 16-ohm tap, peak */
#define HW_OUT       (1.0f / 62.0f)
#define HW_SAG_ATT   0.0011331443546039877f   /* 5 ms at 176.4k */
#define HW_SAG_REL   0.0002834065447940848f   /* 20 ms */
#define HW_SAG_DEPTH 0.15f
#define HW_RESID_A   0.6565002619092772f      /* 30 kHz guard LP */
#define HW_GRID      0.08f                    /* slope above the plate ceiling */

/* HW_ADAA 1: first-order antiderivative anti-aliasing on every tube stage
 * (as the desktop ships), in float without its cancellation problem. */
#ifndef HW_ADAA
#define HW_ADAA 1
#endif
/* HW_OS_IIR 1: polyphase IIR half-bands (os_hbiir.h); 0: the FIR half-bands
 * of Green 808X (os_halfband.h), whose ~-77 dB image rejection lets the tubes
 * intermodulate the upsampling images into a -65..-80 dB floor. */
#ifndef HW_OS_IIR
#define HW_OS_IIR 1
#endif
#define HW_LN2 0.6931471805599453f

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
#if HW_OS_IIR
    HbiState1 up1, dn1;             /* 1x <-> 2x */
    HbiState2 up2, dn2;             /* 2x <-> 4x */
#else
    TsxHB6 os1;                     /* 1x <-> 2x */
    TsxHB3 os2;                     /* 2x <-> 4x */
#endif
    float ax[5];                    /* ADAA: previous input of each tube stage */
    float dcx, dcy;                 /* input DC guard */
    float xv1[2], xst[5], xbh[5];   /* network states (capacitor volts) */
    float uv1, ust, ub0, ub1;       /* previous network inputs */
    float resid, sag;               /* NFB residual, sag envelope */
    float cab[HW_CAB_N][2];         /* cab biquads, TDF-II */
} HwState;                          /* 73 floats = 292 B (IIR), all zero = reset */

typedef struct {
    MnaSS v1, st, bh;
} HwCoeffs;

/* knobs 0..1: Volume (Normal 470k-A), Treble, Middle, Bass, Master, Presence */
TS_INLINE void hw_coeffs(HwCoeffs *k, float vol, float tre, float mid, float bas,
                         float mas, float pre)
{
    MnaNet n;
    float w[MNA_MAXN];
    hw_v1net(&n, w, vol);
    mna_derive(&n, w, HW_FS_OS, &k->v1);
    hw_stack(&n, w, tre, mid, bas, mas);
    mna_derive(&n, w, HW_FS_OS, &k->st);
    hw_backhalf(&n, w, pre);
    mna_derive(&n, w, HW_FS_OS, &k->bh);
}

TS_INLINE float hw_tanh(float u)
{
    float a = u < 0.0f ? -u : u, e, t;
    if (a > 9.0f) a = 9.0f;
    e = sd_expf(-2.0f * a);
    t = (1.0f - e) * ts_rcp(1.0f + e);
    return u < 0.0f ? -t : t;
}

/* AmpStages::tubeStage minus its idle output (the networks see AC only) */
TS_INLINE float hw_tube(float x, float bias, float kneg, float ceil, float idle)
{
    float u = x + bias, y;
    if (u > ceil) u = ceil + (u - ceil) * HW_GRID;
    y = hw_tanh(u);
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

/* tanh with relative accuracy for small arguments (expm1 series) */
TS_INLINE float hw_tanh_acc(float m)
{
    float a = m < 0.0f ? -m : m, t;
    if (a < 0.25f) {
        float x = -2.0f * a;
        float em = x * (1.0f + x * (0.5f + x * (1.0f / 6 + x * (1.0f / 24 + x * (1.0f / 120
                 + x * (1.0f / 720 + x * (1.0f / 5040 + x * (1.0f / 40320 + x * (1.0f / 362880)))))))));
        t = -em * ts_rcp(2.0f + em);
    } else {
        float e;
        if (a > 9.0f) a = 9.0f;
        e = sd_expf(-2.0f * a);
        t = (1.0f - e) * ts_rcp(1.0f + e);
    }
    return m < 0.0f ? -t : t;
}

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

/* t(u) of each region: region 0 uses -u, so that t >= 0 for hw_g */
TS_INLINE float hw_treg(int reg, float u, float c)
{
    return reg == 0 ? -u : (reg == 1 ? u : HW_GRID * u + c * (1.0f - HW_GRID));
}

/* ADAA output over [ua, ua + du] inside one region */
TS_INLINE float hw_q(int reg, float ua, float du, float kneg, float c)
{
    float ad = du < 0.0f ? -du : du;
    if (ad < HW_ADAA_BIG) {
        if (reg == 0) return kneg * hw_mean_tanh(ua, 0.5f * du);
        if (reg == 1) return hw_mean_tanh(ua, 0.5f * du);
        return hw_mean_tanh(hw_treg(2, ua, c), 0.5f * HW_GRID * du);
    }
    {   /* large step: F = slope u + W g(t) per region, |g| < ln2, |du| >= 0.25 */
        float t1 = hw_treg(reg, ua, c);
        float dq = (hw_g(hw_treg(reg, ua + du, c)) - hw_g(t1)) * ts_rcp(du);
        return reg == 0 ? -kneg + kneg * dq : 1.0f + (reg == 1 ? dq : dq * (1.0f / HW_GRID));
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

#if HW_ADAA
#define HW_TUBE(i, x, b, k, c, idle) hw_tube_adaa(x, &s->ax[i], b, k, c, idle)
#else
#define HW_TUBE(i, x, b, k, c, idle) hw_tube(x, b, k, c, idle)
#endif

/* one step of a k-state network with input u (previous input up) */
TS_INLINE float hw_net(const MnaSS *m, float *x, int k, int col, float u, float up)
{
    float su = u + up, dx[MNA_MAXK], y = m->dy[col] * u;
    int i, j;
    for (i = 0; i < k; ++i) {
        float a = m->db[i][col] * su;
        for (j = 0; j < k; ++j) a += m->da[i][j] * x[j];
        dx[i] = a;
    }
    for (i = 0; i < k; ++i) {
        x[i] += dx[i];
        y += m->cy[i] * x[i];
    }
    return y;
}

/* one 4x sample through the amp; returns 16-ohm tap volts * HW_OUT */
TS_INLINE float hw_stage(HwState *s, const HwCoeffs *k, float in)
{
    float v, y, u, d, ypi, yp, tap, r, rail, pre;
    int i;

    v = in * HW_IN_SCALE;
    y = v - s->dcx + HW_DC_R * s->dcy;
    s->dcx = v;
    s->dcy = y;
    pre = 1.0f - 0.3f * HW_SAG_DEPTH * s->sag;   /* preamp rails: 30 % of sag */

    y = HW_TUBE(0, y * (1.0f / HW_H1), HW_B1, HW_K1, pre, HW_I1);
    u = HW_MU3 * HW_H1 * y;
    y = hw_net(&k->v1, s->xv1, 2, 0, u, s->uv1);
    s->uv1 = u;

    y = HW_TUBE(1, y * (1.0f / HW_H2), HW_B2, HW_K2, pre, HW_I2);
    u = HW_MU3 * HW_H2 * y;
    y = hw_net(&k->st, s->xst, 5, 0, u, s->ust);
    s->ust = u;

    y = HW_TUBE(2, y * (1.0f / HW_H3), HW_B3, HW_K3, pre, HW_I3);
    {   /* back half: u0 = V3a grid volts, u1 = -residual (POL_NFB) */
        float u0 = HW_H3 * y, u1 = -s->resid, s0 = u0 + s->ub0, s1 = u1 + s->ub1;
        float dx[5];
        d = k->bh.dy[0] * u0 + k->bh.dy[1] * u1;
        for (i = 0; i < 5; ++i) {
            float a = k->bh.db[i][0] * s0 + k->bh.db[i][1] * s1;
            int j;
            for (j = 0; j < 5; ++j) a += k->bh.da[i][j] * s->xbh[j];
            dx[i] = a;
        }
        for (i = 0; i < 5; ++i) {
            s->xbh[i] += dx[i];
            d += k->bh.cy[i] * s->xbh[i];
        }
        s->ub0 = u0;
        s->ub1 = u1;
    }

    ypi = HW_TUBE(3, d * (1.0f / HW_HPI), HW_BPI, HW_KPI, pre, HW_IPI);
    r = ypi < 0.0f ? -ypi : ypi;
    s->sag += (r - s->sag) * (r > s->sag ? HW_SAG_ATT : HW_SAG_REL);
    rail = 1.0f - HW_SAG_DEPTH * s->sag;
    /* PI diff output (the LTP inverts grid a) -> per-side EL34 grid vs 38 V */
    yp = HW_TUBE(4, -ypi * HW_APIHPI * (0.5f / HW_HPWR), HW_BPW, HW_KPW, rail, HW_IPW);
    tap = HW_VTAP * yp;
    s->resid += HW_RESID_A * ((tap - HW_KTAPLIN * d) - s->resid);
    return tap * HW_OUT;
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

/* one base-rate sample: 4x amp, then the cab unless cab_on is 0 */
TS_INLINE float hw_process(HwState *s, const HwCoeffs *k, float x, int cab_on)
{
    float a1, b1, a2, b2, c2, d2;
#if HW_OS_IIR
    hbi_up1(&s->up1, x, &a1, &b1);
    hbi_up2(&s->up2, a1, &a2, &b2);
    hbi_up2(&s->up2, b1, &c2, &d2);
#else
    tsx_up6(&s->os1, x, &a1, &b1);
    tsx_up3(&s->os2, a1, &a2, &b2);
    tsx_up3(&s->os2, b1, &c2, &d2);
#endif
    a2 = hw_stage(s, k, a2);
    b2 = hw_stage(s, k, b2);
    c2 = hw_stage(s, k, c2);
    d2 = hw_stage(s, k, d2);
#if HW_OS_IIR
    a1 = hbi_down2(&s->dn2, a2, b2);
    b1 = hbi_down2(&s->dn2, c2, d2);
    x = hbi_down1(&s->dn1, a1, b1);
#else
    a1 = tsx_down3(&s->os2, a2, b2);
    b1 = tsx_down3(&s->os2, c2, d2);
    x = tsx_down6(&s->os1, a1, b1);
#endif
    return cab_on ? hw_cabinet(s, x) : x;
}

#endif /* HIWATT_AMP_H */

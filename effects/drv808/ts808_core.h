/* ts808_core.h - TS808-style drive for the Zoom G1 Four, in portable C.
 *
 * A port of Comet Flower's MobileDsp::DriveMobileCore (DriveMobileCore.h,
 * ADAAWaveshaper.h TS808DiodeClipper, MobilePrimitives.h Oversampler2x /
 * OnePoleTPT / Biquad). Same circuit model and component values:
 *   720 Hz feedback ground-leg split (C3/R4), non-inverting clipping stage
 *   y = x + clip((G-1)x) with first-order ADAA, drive-dependent 51 pF
 *   softening pole, 723 Hz post-clip pole (R7/C5), pole-zero tone (R8/C6),
 *   5 Hz output coupling, 2x half-band oversampling (6 tap pairs).
 *
 * What changes for the pedal (no calls, no libm, no divide instruction,
 * ~184 B of state):
 *   - divisions use a reciprocal: the C674x RCPSP seed plus two Newton
 *     steps on the pedal, an emulated 8-bit seed plus the same steps on a PC
 *   - tan/pow become sin/cos/exp polynomials, evaluated once per 16-sample
 *     block (the original also computes them per control block)
 *   - oversampler histories are plain shift registers (32 floats), not the
 *     mirrored 3x64-float buffers
 *   - the ADAA's previous antiderivative is recomputed from the previous
 *     input instead of stored as a double (no 8-byte-aligned state)
 *   - base rate is the pedal's 44.1 kHz; fixed filter constants are
 *     precomputed for it
 *
 * Compiled by both the pedal kernel (drv808.c) and the PC harness
 * (tests/host/drv808_compare.cpp), so the harness tests this exact code.
 */
#ifndef TS808_CORE_H
#define TS808_CORE_H

#if defined(__TI_COMPILER_VERSION__)
#  define TS_INLINE static inline __attribute__((always_inline))
#elif defined(_MSC_VER)
#  define TS_INLINE static __forceinline
#else
#  define TS_INLINE static inline
#endif

/* --- constants at base rate 44100 Hz / oversampled 88200 Hz ------------- */
#define TS_OS_RATE      88200.0f
#define TS_G_FB         0.025009745731949806f   /* one-pole g, 720 Hz @ 88.2k */
#define TS_G_POST       0.025111380964517593f   /* 723 Hz @ 88.2k */
#define TS_G_DC         0.00035606283927336335f /* 5 Hz @ 44.1k */
#define TS_TONE_INV_A0  0.10489422082901001f    /* 1 / (1 + k/wp), wp = 2pi*3290 */
#define TS_TONE_A1      (-0.79021155834198f)    /* (1 - k/wp) / a0 */
#define TS_TONE_K       176400.0f               /* bilinear k = 2 * osRate */
#define TS_LN_RATIO     3.8208537101745605f     /* ln(33000 / 723) */
#define TS_PI           3.14159265358979f

/* half-band FIR, Oversampler2x::prepare(6), float32 */
#define OS_C0  0.3093908131122589f
#define OS_C1 -0.08205419033765793f
#define OS_C2  0.030557531863451004f
#define OS_C3 -0.010060779750347137f
#define OS_C4  0.0023494274355471134f
#define OS_C5 -0.00018280815856996924f

/* TS808DiodeClipper{0.6, 0.08} (MA150) */
#define CL_VF    0.6f
#define CL_KNEE  0.08f
#define CL_LB    0.52f
#define CL_UB    0.68f
#define CL_INV2K 6.25f                           /* 1 / (2 * knee) */

typedef struct {
    float xh[12];          /* upsampler history, [0] newest */
    float eh[7];           /* downsampler even-phase history */
    float oh[13];          /* downsampler odd-phase history */
    float s_fb, s_soft, s_post, z_tone, s_dc;
    float x1;              /* ADAA previous input */
} Ts808State;              /* 38 floats = 152 bytes, all zero = reset */

typedef struct {           /* per-block coefficients, never stored */
    float gm1, inv_gm1, g_soft, b0, b1, gain;
} Ts808Coeffs;

/* --- arithmetic without calls -------------------------------------------- */
#if defined(__TI_COMPILER_VERSION__)
TS_INLINE float ts_rcp_seed(float x) { return _rcpsp(x); }
#else
#include <string.h>
/* emulate RCPSP's ~8-bit seed so the PC harness exercises the Newton steps */
TS_INLINE float ts_rcp_seed(float x)
{
    float r = 1.0f / x;
    unsigned u;
    memcpy(&u, &r, 4);
    u &= 0xFFFF8000u;
    memcpy(&r, &u, 4);
    return r;
}
#endif

TS_INLINE float ts_rcp(float x)
{
    float r = ts_rcp_seed(x);
    r = r * (2.0f - x * r);
    r = r * (2.0f - x * r);
    return r;
}

/* tan(w)/(1+tan(w)) = sin/(sin+cos), w in [0, 1.45] */
TS_INLINE float ts_onepole_g(float fc, float sr_inv_pi)
{
    float w = fc * sr_inv_pi;
    float w2 = w * w;
    float s = w * (1.0f + w2 * (-1.0f/6 + w2 * (1.0f/120 + w2 * (-1.0f/5040
              + w2 * (1.0f/362880 + w2 * (-1.0f/39916800))))));
    float c = 1.0f + w2 * (-0.5f + w2 * (1.0f/24 + w2 * (-1.0f/720
              + w2 * (1.0f/40320 + w2 * (-1.0f/3628800 + w2 * (1.0f/479001600))))));
    return s * ts_rcp(s + c);
}

/* exp(y) for y in [0, 4]: (Taylor of exp(y/8))^8 */
TS_INLINE float ts_exp_pos(float y)
{
    float u = y * 0.125f;
    float e = 1.0f + u * (1.0f + u * (0.5f + u * (1.0f/6 + u * (1.0f/24
              + u * (1.0f/120 + u * (1.0f/720 + u * (1.0f/5040 + u * (1.0f/40320))))))));
    e = e * e; e = e * e; e = e * e;
    return e;
}

TS_INLINE float ts_clamp(float x, float lo, float hi)
{
    return x < lo ? lo : (x > hi ? hi : x);
}

/* --- control rate: DriveMobileCore::setParams ---------------------------- */
/* drive 0..10, tone 0..1, gain = linear output gain */
TS_INLINE void ts808_coeffs(Ts808Coeffs *k, float drive, float tone, float gain)
{
    float d = ts_clamp(drive, 0.0f, 10.0f);
    float dn = d * 0.1f;
    float rdrive = 51000.0f + dn * dn * 500000.0f;
    float gm1 = rdrive * (1.0f / 4700.0f);       /* (1 + R/4.7k) - 1 */
    float fsoft;
    if (gm1 < 0.001f) gm1 = 0.001f;
    k->gm1 = gm1;
    k->inv_gm1 = ts_rcp(gm1);
    fsoft = ts_rcp(6.2831853f * rdrive * 51.0e-12f);
    if (fsoft > TS_OS_RATE * 0.45f) fsoft = TS_OS_RATE * 0.45f;
    k->g_soft = ts_onepole_g(fsoft, TS_PI / TS_OS_RATE);

    {
        float t = ts_clamp(tone, 0.0f, 1.0f);
        float fz = 723.0f * ts_exp_pos((1.0f - t) * TS_LN_RATIO);
        float kwz;
        if (fz > 0.45f * TS_OS_RATE) fz = 0.45f * TS_OS_RATE;
        kwz = TS_TONE_K * ts_rcp(6.2831853f * fz);
        k->b0 = (1.0f + kwz) * TS_TONE_INV_A0;
        k->b1 = (1.0f - kwz) * TS_TONE_INV_A0;
    }
    k->gain = gain;
}

/* --- audio rate ----------------------------------------------------------- */
TS_INLINE float ts_clip_f(float x)
{
    float a = x < 0.0f ? -x : x;
    float y;
    if (a < CL_LB) return x;
    if (a < CL_UB) {
        float t = (a - CL_LB) * CL_INV2K;
        y = CL_LB + CL_KNEE * t * (2.0f - t);
    } else {
        y = CL_VF;
    }
    return x < 0.0f ? -y : y;
}

TS_INLINE double ts_clip_F(double x)
{
    /* the original derives these from float Vf/knee; constant-folded here */
    const double vf = (double)CL_VF, kn = (double)CL_KNEE;
    const double lb = (double)(CL_VF - CL_KNEE), ub = (double)(CL_VF + CL_KNEE);
    const double i2k = 1.0 / (2.0 * kn), i12k2 = 1.0 / (12.0 * kn * kn);
    const double full = 2.0 * kn;
    double a = x < 0.0 ? -x : x;
    double base = 0.5 * lb * lb;
    if (a < lb) return 0.5 * a * a;
    if (a < ub) {
        double dx = a - lb;
        return base + lb * dx + kn * (dx * dx * i2k - dx * dx * dx * i12k2);
    }
    return base + (lb * full + kn * (full * full * i2k - full * full * full * i12k2))
         + vf * (a - ub);
}

TS_INLINE float ts_onepole_lp(float *s, float g, float x)
{
    float v = (x - *s) * g;
    float y = v + *s;
    *s = y + v;
    return y;
}

TS_INLINE float ts_stage(Ts808State *st, const Ts808Coeffs *k, float v)
{
    float input_hp = v - ts_onepole_lp(&st->s_fb, TS_G_FB, v);
    float input_lp = v - input_hp;
    float y;

    /* f(u) = u + clip(g u);  F(u) = u^2/2 + F_clip(g u) / g */
    {
        double g = (double)k->gm1, ig = (double)k->inv_gm1;
        double x = (double)input_hp, xp = (double)st->x1;
        double ad0 = 0.5 * x * x + ig * ts_clip_F(g * x);
        double ad1 = 0.5 * xp * xp + ig * ts_clip_F(g * xp);
        double diff = x - xp;
        if ((diff < 0.0 ? -diff : diff) > 1.0e-5) {
            y = (float)(ad0 - ad1) * ts_rcp((float)diff);
        } else {
            float m = (float)(0.5 * (x + xp));
            y = m + ts_clip_f(k->gm1 * m);
        }
        st->x1 = input_hp;
    }

    y = ts_onepole_lp(&st->s_soft, k->g_soft, y);
    y = ts_onepole_lp(&st->s_post, TS_G_POST, y + input_lp);
    {   /* TDF-II biquad with b2 = a2 = 0 */
        float out = k->b0 * y + st->z_tone;
        st->z_tone = k->b1 * y - TS_TONE_A1 * out;
        return out;
    }
}

TS_INLINE float ts808_process(Ts808State *st, const Ts808Coeffs *k, float x)
{
    int i;
    float a, b, acc;

    /* up: even phase = centre tap delay, odd phase = symmetric FIR */
    for (i = 11; i > 0; --i) st->xh[i] = st->xh[i - 1];
    st->xh[0] = x;
    a = st->xh[6];
    b = 2.0f * (OS_C0 * (st->xh[6] + st->xh[5]) + OS_C1 * (st->xh[7] + st->xh[4])
              + OS_C2 * (st->xh[8] + st->xh[3]) + OS_C3 * (st->xh[9] + st->xh[2])
              + OS_C4 * (st->xh[10] + st->xh[1]) + OS_C5 * (st->xh[11] + st->xh[0]));

    a = ts_stage(st, k, a);
    b = ts_stage(st, k, b);

    /* down */
    for (i = 6; i > 0; --i) st->eh[i] = st->eh[i - 1];
    st->eh[0] = a;
    for (i = 12; i > 0; --i) st->oh[i] = st->oh[i - 1];
    st->oh[0] = b;
    acc = 0.5f * st->eh[6]
        + OS_C0 * (st->oh[7] + st->oh[6]) + OS_C1 * (st->oh[8] + st->oh[5])
        + OS_C2 * (st->oh[9] + st->oh[4]) + OS_C3 * (st->oh[10] + st->oh[3])
        + OS_C4 * (st->oh[11] + st->oh[2]) + OS_C5 * (st->oh[12] + st->oh[1]);

    /* 5 Hz DC block (base rate), then level */
    acc = acc - ts_onepole_lp(&st->s_dc, TS_G_DC, acc);
    return acc * k->gain;
}

#endif /* TS808_CORE_H */

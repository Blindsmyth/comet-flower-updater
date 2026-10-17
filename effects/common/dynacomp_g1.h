/* dynacomp_g1.h - CF Dyna Comp core for the G1X Four (MXR Dyna Comp, port of
 * Comet Flower's DynaCompProcessor). Shared by the pedal kernel and the PC bench
 * (tests/host/dynacomp_accuracy.cpp).
 *
 * CONTRACT:
 *   typedef struct { ... } DynaCompState;    zero-initialised = silent start
 *   typedef struct { ... } DynaCompCoeffs;
 *   void  dynacomp_coeffs(DynaCompCoeffs *k, float sustain, float output_db);
 *   float dynacomp_process(DynaCompState *s, const DynaCompCoeffs *k, float x);
 */
#ifndef DYNACOMP_G1_H
#define DYNACOMP_G1_H

#include "ts808_core.h"         /* TS_INLINE, ts_clamp, ts_rcp */

/* Precomputed filter coefficients at 44.1 kHz */
/* High-shelf pre-emphasis: 2000 Hz, Q = 0.70710678, gain = 1.5 (+3.52 dB) */
#define DC_PRE_B0  1.4404678461164175f
#define DC_PRE_B1 -2.3602247800677130f
#define DC_PRE_B2  1.0004217688846135f
#define DC_PRE_A1 -1.5600390475562558f
#define DC_PRE_A2  0.6407038824895739f

/* High-shelf de-emphasis: 2000 Hz, Q = 0.70710678, gain = 1/1.5 (-3.52 dB) */
#define DC_DE_B0   0.6942188974894901f
#define DC_DE_B1  -1.0830085876350581f
#define DC_DE_B2   0.4447887429191478f
#define DC_DE_A1  -1.6385126446459821f
#define DC_DE_A2   0.6945116974195620f

/* One-pole TPT high-pass at 80 Hz */
#define DC_HP_G    0.005666800353471778f

/* Envelope detector ballistics */
#define DC_ATTACK_COEFF  0.9954751208601006f  /* exp(-1 / (0.005 * 44100)) */
#define DC_RELEASE_COEFF 0.9999244170666624f  /* exp(-1 / (0.300 * 44100)) */

/* CompressorMath constants for 8:1 ratio, 6 dB knee */
#define DC_SLOPE        (-0.875f)             /* 1.0/8.0 - 1.0 */
#define DC_HALF_KNEE    3.0f                  /* kneeDb * 0.5 */
#define DC_INV_2KNEE    (1.0f / 12.0f)        /* 1.0 / (2.0 * kneeDb) */
#define DC_INV_1P2      0.8333333333333334f   /* 1.0 / 1.2 */
#define DC_KNEE_RATIO   0.7079457843841379f   /* 10^(-3/20) */

typedef struct {
    float v1_pre;
    float v2_pre;
    float v1_de;
    float v2_de;
    float s_hp;
    float adaa_x1;
    float adaa_ad1;
    float envelope;
} DynaCompState;

typedef struct {
    float threshold;
    float inv_threshold;
    float autoMakeup;
    float outTrim;
} DynaCompCoeffs;

/* --- Fast, libm-free arithmetic helpers ----------------------------------- */

TS_INLINE float dc_absf(float x)
{
    return x < 0.0f ? -x : x;
}

/* exp(x) for x in [-80, 80], float, bit-accurate, no calls, branch-free */
TS_INLINE float dc_expf(float x)
{
    union { float f; unsigned u; } s;
    float kf, r, p;
    int k;
    x = ts_clamp(x, -80.0f, 80.0f);
    kf = x * 1.44269504f;
    k = (int)(kf + (kf >= 0.0f ? 0.5f : -0.5f));
    r = x - (float)k * 0.693145752f - (float)k * 1.42860677e-06f;
    p = 1.0f + r * (1.0f + r * (0.5f + r * (1.0f/6 + r * (1.0f/24
        + r * (1.0f/120 + r * (1.0f/720 + r * (1.0f/5040)))))));
    s.u = (unsigned)(k + 127) << 23;
    return p * s.f;
}

/* 10^(db / 20) = exp(db * ln(10)/20) */
TS_INLINE float dc_exp_db(float db)
{
    return dc_expf(db * 0.11512925464970228f);
}

/* 20 * log10(x) for x > 0, float, no calls, branch-free */
TS_INLINE float dc_20log10(float x)
{
    union { float f; unsigned u; } v;
    v.f = x;
    int e = (int)(v.u >> 23) - 127;
    v.u = (v.u & 0x007FFFFFu) | 0x3F800000u;
    float vf_half = v.f * 0.5f;
    int cond = (v.f > 1.41421356f);
    v.f = cond ? vf_half : v.f;
    e = cond ? (e + 1) : e;
    float s = (v.f - 1.0f) * ts_rcp(v.f + 1.0f);
    float z = s * s;
    float p = s * (2.0f + z * (0.66666784f + z * (0.3997835f + z * 0.2983262f)));
    return (float)e * 6.020599913279624f + p * 8.685889638065037f;
}

/* log(1 + w) on [0, 1] via degree-8 Horner polynomial */
TS_INLINE float dc_log1p(float w)
{
    float p = -0.00632052f;
    p =  0.03545882f + w * p;
    p = -0.09413391f + w * p;
    p =  0.16648205f + w * p;
    p = -0.24010053f + w * p;
    p =  0.33161391f + w * p;
    p = -0.49984781f + w * p;
    p =  0.99999509f + w * p;
    return w * p;
}

/* ln(cosh(z)) = |z| + log1p(exp(-2|z|)) - ln(2)
 * Branch-free evaluation: computes Taylor expansion for small |z| and general form
 * for large |z|, selecting with a predicated value ternary. */
TS_INLINE float dc_ln_cosh(float z)
{
    float a = dc_absf(z);
    float a_taylor = ts_clamp(a, 0.0f, 0.2f);
    float z2 = a_taylor * a_taylor;
    float val_taylor = z2 * (0.5f + z2 * (-0.08333333333333333f + z2 * (0.022222222222222223f - z2 * 0.006746031746031746f)));
    float w = dc_expf(-2.0f * a);
    float val_large = a + dc_log1p(w) - 0.6931471805599453f;
    return (a < 0.2f) ? val_taylor : val_large;
}

/* tanh(t) = sign(t) * (1 - exp(-2|t|)) / (1 + exp(-2|t|)), branch-free */
TS_INLINE float dc_tanhf(float t)
{
    float a = dc_absf(t);
    float w = dc_expf(-2.0f * a);
    float th = (1.0f - w) * ts_rcp(1.0f + w);
    return t < 0.0f ? -th : th;
}

TS_INLINE float dc_gain_reduction_db(float overDb)
{
    float t = overDb + DC_HALF_KNEE;
    float gr_knee = DC_SLOPE * t * t * DC_INV_2KNEE;
    float gr_above = DC_SLOPE * overDb;
    float gr = (overDb < DC_HALF_KNEE) ? gr_knee : gr_above;
    return (overDb <= -DC_HALF_KNEE) ? 0.0f : gr;
}

TS_INLINE void dynacomp_coeffs(DynaCompCoeffs *k, float sustain, float output_db)
{
    float s = ts_clamp(sustain, 0.0f, 10.0f) * 0.1f;
    float sc = (1.0f - s) * (1.0f - s);
    float threshold = 0.80f * sc + 0.005f;
    float thresholdDb = dc_20log10(threshold);
    float autoMakeupDb = -dc_gain_reduction_db(-12.0f - thresholdDb);
    float outDb = ts_clamp(output_db, -60.0f, 24.0f);

    k->threshold = threshold;
    k->inv_threshold = ts_rcp(threshold);
    k->autoMakeup = dc_exp_db(autoMakeupDb);
    k->outTrim = dc_exp_db(outDb);
}

TS_INLINE float dynacomp_process(DynaCompState *s, const DynaCompCoeffs *k, float x)
{
    /* 1. Envelope detector: pure select with no side effects in arms */
    float maxAbs = dc_absf(x);
    float env = s->envelope;
    float env_att = DC_ATTACK_COEFF * (env - maxAbs) + maxAbs;
    float env_rel = DC_RELEASE_COEFF * env;
    env_rel = (env_rel < 1.0e-9f) ? 0.0f : env_rel;
    env = (maxAbs > env) ? env_att : env_rel;
    s->envelope = env;

    /* 2. Gain computer: branch-free soft-knee gain calculation */
    float ratio = env * k->inv_threshold;
    float ratio_eval = (ratio > DC_KNEE_RATIO) ? ratio : DC_KNEE_RATIO;
    float overDb = dc_20log10(ratio_eval);
    float grDb = dc_gain_reduction_db(overDb);
    float gr_exp = (grDb < 0.0f) ? dc_exp_db(grDb) : 1.0f;
    float gr = (ratio > DC_KNEE_RATIO) ? gr_exp : 1.0f;

    /* 3. Pre-emphasis high shelf (DF2T) */
    float v = DC_PRE_B0 * x + s->v1_pre;
    s->v1_pre = DC_PRE_B1 * x - DC_PRE_A1 * v + s->v2_pre;
    s->v2_pre = DC_PRE_B2 * x - DC_PRE_A2 * v;

    /* 4. Gain reduction + makeup */
    v *= gr;
    v *= k->autoMakeup;

    /* 5. ADAA tanh(v / 1.2) * 1.2: no division on hot path */
    {
        float ad0 = 1.2f * dc_ln_cosh(v * DC_INV_1P2);
        float diff = v - s->adaa_x1;
        float abs_diff = dc_absf(diff);
        float diff_safe = (abs_diff > 1.0e-5f) ? diff : 1.0f;
        float adaa_secant = (ad0 - s->adaa_ad1) * ts_rcp(diff_safe);
        float adaa_mid = dc_tanhf(0.5f * (v + s->adaa_x1) * DC_INV_1P2);
        float adaa_out = (abs_diff > 1.0e-5f) ? adaa_secant : adaa_mid;
        s->adaa_x1 = v;
        s->adaa_ad1 = ad0;
        v = adaa_out * 1.2f;
    }

    /* 6. De-emphasis high shelf (DF2T) */
    float y_de = DC_DE_B0 * v + s->v1_de;
    s->v1_de = DC_DE_B1 * v - DC_DE_A1 * y_de + s->v2_de;
    s->v2_de = DC_DE_B2 * v - DC_DE_A2 * y_de;
    v = y_de;

    /* 7. Output high-pass 80 Hz (OnePoleTPT) */
    float v_hp = (v - s->s_hp) * DC_HP_G;
    float lp = v_hp + s->s_hp;
    s->s_hp = lp + v_hp;
    v = v - lp;

    /* 8. Output trim */
    v *= k->outTrim;

    return v;
}

#endif /* DYNACOMP_G1_H */

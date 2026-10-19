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

/* The per-sample work in steps that take each state value by pointer: the
 * per-sample path (dynacomp_process) passes the state fields, the block path
 * (dynacomp_block) passes scalar locals, so the arithmetic is written once and
 * both are bit-identical (tests/host/dynacomp_block_test.cpp). Only the
 * envelope and the three filters are recurrences; the gain computer and the
 * ADAA are pure per sample and pipeline on the units (docs/C6745_DESIGN.md). */

/* 1. Envelope detector: pure select with no side effects in arms */
TS_INLINE float dc_env_step(float *envp, float x)
{
    float maxAbs = dc_absf(x);
    float env = *envp;
    float env_att = DC_ATTACK_COEFF * (env - maxAbs) + maxAbs;
    float env_rel = DC_RELEASE_COEFF * env;
    env_rel = (env_rel < 1.0e-9f) ? 0.0f : env_rel;
    env = (maxAbs > env) ? env_att : env_rel;
    *envp = env;
    return env;
}

/* 3. Pre-emphasis high shelf (DF2T) */
TS_INLINE float dc_pre_step(float *v1, float *v2, float x)
{
    float v = DC_PRE_B0 * x + *v1;
    *v1 = DC_PRE_B1 * x - DC_PRE_A1 * v + *v2;
    *v2 = DC_PRE_B2 * x - DC_PRE_A2 * v;
    return v;
}

/* 2 + 4. Gain computer (branch-free soft knee) applied to v, then makeup */
TS_INLINE float dc_gain_apply(const DynaCompCoeffs *k, float env, float v)
{
    float ratio = env * k->inv_threshold;
    float ratio_eval = (ratio > DC_KNEE_RATIO) ? ratio : DC_KNEE_RATIO;
    float overDb = dc_20log10(ratio_eval);
    float grDb = dc_gain_reduction_db(overDb);
    float e_db = dc_exp_db(grDb);    /* always computed, then selected: as a ?: arm cl6x made it a branch */
    float gr_exp = (grDb < 0.0f) ? e_db : 1.0f;
    float gr = (ratio > DC_KNEE_RATIO) ? gr_exp : 1.0f;
    v *= gr;
    v *= k->autoMakeup;
    return v;
}

/* 5. ADAA tanh(v / 1.2) * 1.2: no division on hot path. Its two expensive
 * parts are pure functions (the antiderivative of v, the tanh at the midpoint
 * with the previous input), so the block path computes them in their own
 * passes; dc_adaa_mix only combines. */
TS_INLINE float dc_adaa_ad(float v) { return 1.2f * dc_ln_cosh(v * DC_INV_1P2); }
TS_INLINE float dc_adaa_mid(float v, float x1) { return dc_tanhf(0.5f * (v + x1) * DC_INV_1P2); }
TS_INLINE float dc_adaa_mix(float v, float x1, float ad0, float ad1, float adaa_mid)
{
    float diff = v - x1;
    float abs_diff = dc_absf(diff);
    float diff_safe = (abs_diff > 1.0e-5f) ? diff : 1.0f;
    float adaa_secant = (ad0 - ad1) * ts_rcp(diff_safe);
    float adaa_out = (abs_diff > 1.0e-5f) ? adaa_secant : adaa_mid;
    return adaa_out * 1.2f;
}
TS_INLINE float dc_adaa_step(float *x1, float *ad1, float v)
{
    float ad0 = dc_adaa_ad(v);
    float out = dc_adaa_mix(v, *x1, ad0, *ad1, dc_adaa_mid(v, *x1));
    *x1 = v;
    *ad1 = ad0;
    return out;
}

/* 6-8. De-emphasis high shelf (DF2T), output high-pass 80 Hz (OnePoleTPT), trim */
TS_INLINE float dc_post_step(float *v1, float *v2, float *shp, const DynaCompCoeffs *k, float v)
{
    float y_de = DC_DE_B0 * v + *v1;
    *v1 = DC_DE_B1 * v - DC_DE_A1 * y_de + *v2;
    *v2 = DC_DE_B2 * v - DC_DE_A2 * y_de;
    v = y_de;

    float v_hp = (v - *shp) * DC_HP_G;
    float lp = v_hp + *shp;
    *shp = lp + v_hp;
    v = v - lp;

    v *= k->outTrim;
    return v;
}

TS_INLINE float dynacomp_process(DynaCompState *s, const DynaCompCoeffs *k, float x)
{
    float env = dc_env_step(&s->envelope, x);
    float v = dc_pre_step(&s->v1_pre, &s->v2_pre, x);
    v = dc_gain_apply(k, env, v);
    v = dc_adaa_step(&s->adaa_x1, &s->adaa_ad1, v);
    return dc_post_step(&s->v1_de, &s->v2_de, &s->s_hp, k, v);
}

/* Block form for the C6745: the same arithmetic over n samples, stage-major,
 * state in scalar locals. n <= DC_BLK_MAX. */
#define DC_BLK_MAX 16
#if defined(__TI_COMPILER_VERSION__)
#define DC_LOOP _Pragma("MUST_ITERATE(1, DC_BLK_MAX)")
#else
#define DC_LOOP
#endif
#if defined(__TI_COMPILER_VERSION__)
#define DC_RESTRICT restrict
#else
#define DC_RESTRICT __restrict
#endif
TS_INLINE void dynacomp_block(DynaCompState *DC_RESTRICT s, const DynaCompCoeffs *DC_RESTRICT k,
                              const float *DC_RESTRICT in, float *DC_RESTRICT out, int n)
{
    float env[DC_BLK_MAX], v[DC_BLK_MAX];
    int i;
    {   /* envelope and pre-emphasis: two independent recurrences in one loop */
        float e = s->envelope, p1 = s->v1_pre, p2 = s->v2_pre;
        DC_LOOP
        for (i = 0; i < n; ++i) {
            env[i] = dc_env_step(&e, in[i]);
            v[i] = dc_pre_step(&p1, &p2, in[i]);
        }
        s->envelope = e; s->v1_pre = p1; s->v2_pre = p2;
    }
    DC_LOOP
    for (i = 0; i < n; ++i)              /* gain computer: no recurrence */
        v[i] = dc_gain_apply(k, env[i], v[i]);
    {   /* ADAA: the pure parts in their own passes (one exp each), then the mix */
        float ad[DC_BLK_MAX], mid[DC_BLK_MAX];
        float x1 = s->adaa_x1, ad1 = s->adaa_ad1;
        DC_LOOP
        for (i = 0; i < n; ++i)
            ad[i] = dc_adaa_ad(v[i]);
        DC_LOOP
        for (i = 0; i < n; ++i)
            mid[i] = dc_adaa_mid(v[i], i ? v[i - 1] : x1);
        DC_LOOP
        for (i = 0; i < n; ++i) {
            float vi = v[i];
            v[i] = dc_adaa_mix(vi, x1, ad[i], ad1, mid[i]);
            x1 = vi;
            ad1 = ad[i];
        }
        s->adaa_x1 = x1; s->adaa_ad1 = ad1;
    }
    {
        float d1 = s->v1_de, d2 = s->v2_de, hp = s->s_hp;
        DC_LOOP
        for (i = 0; i < n; ++i)
            out[i] = dc_post_step(&d1, &d2, &hp, k, v[i]);
        s->v1_de = d1; s->v2_de = d2; s->s_hp = hp;
    }
}

#endif /* DYNACOMP_G1_H */

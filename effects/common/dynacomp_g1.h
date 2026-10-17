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

#include <math.h>
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
#define DC_DB_TO_NEPER  0.11512925464970228f  /* ln(10) / 20 */

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
    float thresholdDb;
    float autoMakeup;
    float outTrim;
} DynaCompCoeffs;

TS_INLINE float dc_gain_reduction_db(float overDb)
{
    if (overDb <= -DC_HALF_KNEE) return 0.0f;
    if (overDb < DC_HALF_KNEE) {
        float t = overDb + DC_HALF_KNEE;
        return DC_SLOPE * t * t * DC_INV_2KNEE;
    }
    return DC_SLOPE * overDb;
}

TS_INLINE void dynacomp_coeffs(DynaCompCoeffs *k, float sustain, float output_db)
{
    float s = ts_clamp(sustain, 0.0f, 10.0f) * 0.1f;
    float sc = (1.0f - s) * (1.0f - s);
    float threshold = 0.80f * sc + 0.005f;
    float thresholdDb = 20.0f * log10f(threshold > 1.0e-9f ? threshold : 1.0e-9f);
    float gr_ref = dc_gain_reduction_db(-12.0f - thresholdDb);
    float autoMakeupDb = -gr_ref;
    float outDb = ts_clamp(output_db, -60.0f, 24.0f);

    k->threshold = threshold;
    k->thresholdDb = thresholdDb;
    k->autoMakeup = powf(10.0f, autoMakeupDb * 0.05f);
    k->outTrim = powf(10.0f, outDb * 0.05f);
}

TS_INLINE float dc_ln_cosh(float z)
{
    float a = fabsf(z);
    return a + log1pf(expf(-2.0f * a)) - 0.6931471805599453f;
}

TS_INLINE float dynacomp_process(DynaCompState *s, const DynaCompCoeffs *k, float x)
{
    /* 1. Envelope detector */
    float maxAbs = fabsf(x);
    float env = s->envelope;
    if (maxAbs > env) {
        env = DC_ATTACK_COEFF * (env - maxAbs) + maxAbs;
    } else {
        env = DC_RELEASE_COEFF * env;
        if (env < 1.0e-9f) env = 0.0f;
    }
    s->envelope = env;

    /* 2. Gain computer */
    float gr = 1.0f;
    if (env > 1.0e-9f && k->threshold > 1.0e-9f) {
        float overDb = 20.0f * log10f(env / k->threshold);
        float grDb = dc_gain_reduction_db(overDb);
        if (grDb < 0.0f) {
            gr = expf(grDb * DC_DB_TO_NEPER);
        }
    }

    /* 3. Pre-emphasis high shelf (DF2T) */
    float v = DC_PRE_B0 * x + s->v1_pre;
    s->v1_pre = DC_PRE_B1 * x - DC_PRE_A1 * v + s->v2_pre;
    s->v2_pre = DC_PRE_B2 * x - DC_PRE_A2 * v;

    /* 4. Gain reduction + makeup */
    v *= gr;
    v *= k->autoMakeup;

    /* 5. ADAA tanh(v / 1.2) * 1.2 */
    {
        float ad0 = 1.2f * dc_ln_cosh(v * (1.0f / 1.2f));
        float diff = v - s->adaa_x1;
        float adaa_out;
        if (fabsf(diff) > 1.0e-5f) {
            adaa_out = (ad0 - s->adaa_ad1) / diff;
        } else {
            adaa_out = tanhf(0.5f * (v + s->adaa_x1) * (1.0f / 1.2f));
        }
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

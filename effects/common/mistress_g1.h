/* mistress_g1.h - CF Mistress core for the G1X Four (EHX Electric Mistress
 * V2, port of Comet Flower's FlangerProcessor). Shared by the pedal kernel
 * (an effects/<name>/<name>.c this kit does not include) and the PC bench
 * (tests/host/mistress_accuracy.cpp).
 *
 * CONTRACT (the bench depends on exactly this; do not change):
 *   typedef struct { ... } MistressState;    zero-initialised = silent start,
 *         LFO phase 0 -- matches the desktop's channel-0 reset phase
 *   typedef struct { ... } MistressCoeffs;
 *   void  mistress_coeffs(MistressCoeffs *k, float rate, float depth,
 *                          float feedback, float matrix, float mix);
 *         rate     0.01..10  Hz, direct LFO frequency (Comet Flower "Rate")
 *         depth    0..1      sweep width fraction (Comet Flower "Range")
 *         feedback 0..0.95   BBD feedback amount (Comet Flower "Color")
 *         matrix   0.0 or 1.0 (Comet Flower "Matrix": LFO bypassed, depth
 *                  sets a static delay instead of sweeping one)
 *         mix      0..1      dry/wet (hardwired 50/50 at mix=1)
 *         Called once per 16-sample block; may be costly-ish but no loops
 *         over more than a few dozen items.
 *   float mistress_process(MistressState *s, const MistressCoeffs *k, float x);
 *         one 44.1 kHz input sample -> one output sample. Mono, no added
 *         latency: the bench compares candidate and reference sample for
 *         sample, so any internal oversampling you add must stay sample-
 *         synchronous (zero or exactly-compensated group delay).
 */
#ifndef MISTRESS_G1_H
#define MISTRESS_G1_H

#include "ts808_core.h"         /* TS_INLINE, ts_clamp, ts_rcp, ts_exp_pos */

/* --- Fixed filter constants at 44.1 kHz ---------------------------------- */
#define MISTRESS_G_PRE_HP   5.666800353e-03f /* 80 Hz TPT HPF */
#define MISTRESS_G_PRE_A    5.347844448e-01f /* 12 kHz TPT LPF */
#define MISTRESS_G_POST_DC  3.560628324e-04f /* 5 Hz TPT HPF */
#define MISTRESS_G_POST_A   3.905532020e-01f /* 8 kHz TPT LPF */

/* preB: 12 kHz, Q 0.70710678 RBJ Low-Pass */
#define MISTRESS_PRE_B_B0   3.347852841e-01f
#define MISTRESS_PRE_B_B1   6.695705681e-01f
#define MISTRESS_PRE_B_B2   3.347852841e-01f
#define MISTRESS_PRE_B_A1   1.628747993e-01f
#define MISTRESS_PRE_B_A2   1.762663370e-01f

/* postB: 8 kHz, Q 0.70710678 RBJ Low-Pass */
#define MISTRESS_POST_B_B0  1.772450255e-01f
#define MISTRESS_POST_B_B1  3.544900511e-01f
#define MISTRESS_POST_B_B2  1.772450255e-01f
#define MISTRESS_POST_B_A1 (-5.087175281e-01f)
#define MISTRESS_POST_B_A2  2.176976303e-01f

/* postC: 8.5 kHz, Q 0.5 RBJ Low-Pass */
#define MISTRESS_POST_C_B0  1.673459603e-01f
#define MISTRESS_POST_C_B1  3.346919207e-01f
#define MISTRESS_POST_C_B2  1.673459603e-01f
#define MISTRESS_POST_C_A1 (-3.636823763e-01f)
#define MISTRESS_POST_C_A2  3.306621771e-02f

#define MISTRESS_BUF_SIZE   512
#define MISTRESS_BUF_MASK   511u

typedef struct {
    float buf[MISTRESS_BUF_SIZE];
    int   wp;
    float lfoPhase;
    float ctiState;
    float feedbackState;
    float adaa_x1;
    float adaa_ad1;
    float s_preHP;
    float s_preA;
    float v1_preB, v2_preB;
    float s_postDc;
    float s_postA;
    float v1_postB, v2_postB;
    float v1_postC, v2_postC;
} MistressState;

typedef struct {
    float phaseInc;
    float depth;
    float depthRangeMs;
    float feedbackGain;
    int   matrixMode;
    float dryGain;
    float wetGain;
} MistressCoeffs;

/* Two-segment exponential-triangle LFO (FlangerProcessor.cpp lines 43-68) */
TS_INLINE float mistress_lfo_shape(float phi)
{
    const float riseK = 2.0f;
    const float fallK = 1.8f;
    const float invRise = 0.15651764274966567f; /* 1.0 / (exp(2.0) - 1.0) */
    const float invFall = 1.1980336336214532f;  /* 1.0 / (1.0 - exp(-1.8)) */
    float p_rise = ts_clamp(phi * 2.0f, 0.0f, 1.0f);
    float shape_rise = (ts_exp_pos(riseK * p_rise) - 1.0f) * invRise;
    float p_fall = ts_clamp((phi - 0.5f) * 2.0f, 0.0f, 1.0f);
    float e_pos = ts_exp_pos(fallK * p_fall);
    float e_neg = ts_rcp(e_pos);
    float shape_fall = 1.0f - (1.0f - e_neg) * invFall;
    return (phi < 0.5f) ? shape_rise : shape_fall;
}

TS_INLINE float mistress_tanh(float m)
{
    float a = m < 0.0f ? -m : m;
    float e2 = ts_exp_pos(2.0f * a);
    float t = 1.0f - 2.0f * ts_rcp(e2 + 1.0f);
    float res = (a < 1.0e-4f) ? a : t;
    return m < 0.0f ? -res : res;
}

TS_INLINE float mistress_mean_tanh(float p, float d)
{
    float tm = mistress_tanh(p + d);
    float d2 = d * d;
    float tdd = 1.0f - d2 * (1.0f / 3.0f - d2 * (2.0f / 15.0f - d2 * (17.0f / 315.0f - d2 * (62.0f / 2835.0f))));
    float td = d * tdd;
    float tt = tm * tdd;
    float z = tm * td;
    float z2 = z * z;
    float z4 = z2 * z2;
    return tt * ((1.0f + z2 * (1.0f / 3.0f)) + z4 * (1.0f / 5.0f + z2 * (1.0f / 7.0f)));
}

TS_INLINE float mistress_ln_cosh(float z)
{
    float a = z < 0.0f ? -z : z;
    float approx = 0.5f * a * a;
    float e2 = ts_exp_pos(2.0f * a);
    float w = ts_rcp(e2);
    float sv = w * ts_rcp(2.0f + w);
    float s2 = sv * sv;
    float log1p_w = 2.0f * sv * (1.0f + s2 * (1.0f / 3.0f + s2 * (1.0f / 5.0f + s2 * (1.0f / 7.0f
                    + s2 * (1.0f / 9.0f + s2 * (1.0f / 11.0f + s2 * (1.0f / 13.0f)))))));
    float full = a + log1p_w - 0.6931471805599453f;
    return (a < 1.0e-4f) ? approx : full;
}

TS_INLINE float mistress_adaa_process(MistressState *s, float x)
{
    float x1 = s->adaa_x1;
    float diff = x - x1;
    float ad = diff < 0.0f ? -diff : diff;
    float ad0 = mistress_ln_cosh(x);
    float safe_diff = (ad < 0.2f) ? 1.0f : diff;
    float out_large = (ad0 - s->adaa_ad1) * ts_rcp(safe_diff);
    float out_small = mistress_mean_tanh(x1, 0.5f * diff);
    float out = (ad < 0.2f) ? out_small : out_large;
    s->adaa_x1 = x;
    s->adaa_ad1 = ad0;
    return out;
}

TS_INLINE void mistress_coeffs(MistressCoeffs *k, float rate, float depth,
                               float feedback, float matrix, float mix)
{
    k->phaseInc = rate * (1.0f / 44100.0f);
    k->depth = depth;
    k->depthRangeMs = depth * (6.4f - 0.64f);
    k->feedbackGain = feedback * 0.94f;
    k->matrixMode = (matrix != 0.0f);
    k->dryGain = 1.0f - mix * 0.5f;
    k->wetGain = mix * 0.5f;
}

TS_INLINE float mistress_process(MistressState *s, const MistressCoeffs *k, float x)
{
    /* 1. Pre-BBD coupling-cap HPF (80 Hz, TPT) */
    float v_hp = (x - s->s_preHP) * MISTRESS_G_PRE_HP;
    float lp_hp = v_hp + s->s_preHP;
    s->s_preHP = lp_hp + v_hp;
    float drySample = x - lp_hp;

    /* 2. LFO phase accumulator */
    float lfoPhase = s->lfoPhase + k->phaseInc;
    lfoPhase -= (lfoPhase >= 1.0f) ? 1.0f : 0.0f;
    s->lfoPhase = lfoPhase;

    /* 3. Delay time calculation */
    float lfo_shape = mistress_lfo_shape(lfoPhase);
    float shape = k->matrixMode ? 1.0f : lfo_shape;
    float u = shape * k->depth;
    float delayMs = 0.64f + shape * k->depthRangeMs;
    float delayInSamples = delayMs * 44.1f;

    /* 4. CTI cutoff and alpha */
    float ctiCutoff = 8000.0f - 5500.0f * u;
    float z = ctiCutoff * (6.28318530717958647692f / 44100.0f);
    float ctiAlpha = 1.0f - ts_rcp(ts_exp_pos(z));

    /* 5. Pre-BBD anti-alias LPF cascade (12 kHz 1st-order + 12 kHz Q 0.707 biquad) */
    float v_preA = (drySample - s->s_preA) * MISTRESS_G_PRE_A;
    float preFiltered = v_preA + s->s_preA;
    s->s_preA = preFiltered + v_preA;

    float y_preB = MISTRESS_PRE_B_B0 * preFiltered + s->v1_preB;
    s->v1_preB = MISTRESS_PRE_B_B1 * preFiltered - MISTRESS_PRE_B_A1 * y_preB + s->v2_preB;
    s->v2_preB = MISTRESS_PRE_B_B2 * preFiltered - MISTRESS_PRE_B_A2 * y_preB;
    preFiltered = y_preB;

    /* 6. Feedback ADAA tanh clip */
    float fbSignal = mistress_adaa_process(s, s->feedbackState);

    /* 7. Feedback sum & delay write */
    float bbdIn = preFiltered + fbSignal * k->feedbackGain;
    unsigned int wp = (unsigned int)s->wp;
    s->buf[wp] = bbdIn;
    wp = (wp + 1u) & MISTRESS_BUF_MASK;
    s->wp = (int)wp;

    /* 8. Lagrange 3rd-order fractional delay read */
    int M = (int)delayInSamples;
    float mu = delayInSamples - (float)M;
    float pm1 = s->buf[(wp - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p0  = s->buf[(wp - 1u - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p1  = s->buf[(wp - 2u - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p2  = s->buf[(wp - 3u - (unsigned int)M) & MISTRESS_BUF_MASK];

    float m1 = mu - 1.0f;
    float m2 = mu - 2.0f;
    float p1_mu = mu + 1.0f;
    float Lm1 = -mu * m1 * m2 * (1.0f / 6.0f);
    float L0  =  p1_mu * m1 * m2 * 0.5f;
    float L1  = -p1_mu * mu * m2 * 0.5f;
    float L2  =  p1_mu * mu * m1 * (1.0f / 6.0f);
    float wetSample = Lm1 * pm1 + L0 * p0 + L1 * p1 + L2 * p2;

    /* 9. CTI one-pole low-pass */
    s->ctiState += ctiAlpha * (wetSample - s->ctiState);
    wetSample = s->ctiState;
    s->feedbackState = wetSample;

    /* 10. Post-BBD DC block HPF (5 Hz) + reconstruction LPF cascade (8 kHz 1st + 8 kHz biquad + 8.5 kHz biquad) */
    float v_postDc = (wetSample - s->s_postDc) * MISTRESS_G_POST_DC;
    float lp_postDc = v_postDc + s->s_postDc;
    s->s_postDc = lp_postDc + v_postDc;
    float postFiltered = wetSample - lp_postDc;

    float v_postA = (postFiltered - s->s_postA) * MISTRESS_G_POST_A;
    postFiltered = v_postA + s->s_postA;
    s->s_postA = postFiltered + v_postA;

    float y_postB = MISTRESS_POST_B_B0 * postFiltered + s->v1_postB;
    s->v1_postB = MISTRESS_POST_B_B1 * postFiltered - MISTRESS_POST_B_A1 * y_postB + s->v2_postB;
    s->v2_postB = MISTRESS_POST_B_B2 * postFiltered - MISTRESS_POST_B_A2 * y_postB;
    postFiltered = y_postB;

    float y_postC = MISTRESS_POST_C_B0 * postFiltered + s->v1_postC;
    s->v1_postC = MISTRESS_POST_C_B1 * postFiltered - MISTRESS_POST_C_A1 * y_postC + s->v2_postC;
    s->v2_postC = MISTRESS_POST_C_B2 * postFiltered - MISTRESS_POST_C_A2 * y_postC;
    postFiltered = y_postC;

    /* 11. Dry/wet mix */
    return drySample * k->dryGain + postFiltered * k->wetGain;
}

#endif /* MISTRESS_G1_H */

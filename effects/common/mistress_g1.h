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

/* the ADAA in parts: ad0 and the small-step mean are pure functions of the
 * input and the previous input, so the block path runs them as passes */
TS_INLINE float mistress_adaa_mix(float x, float x1, float ad0, float ad1, float out_small)
{
    float diff = x - x1;
    float ad = diff < 0.0f ? -diff : diff;
    float safe_diff = (ad < 0.2f) ? 1.0f : diff;
    float out_large = (ad0 - ad1) * ts_rcp(safe_diff);
    return (ad < 0.2f) ? out_small : out_large;
}

TS_INLINE float mistress_adaa_step(float *x1p, float *ad1p, float x)
{
    float x1 = *x1p;
    float ad0 = mistress_ln_cosh(x);
    float out = mistress_adaa_mix(x, x1, ad0, *ad1p, mistress_mean_tanh(x1, 0.5f * (x - x1)));
    *x1p = x;
    *ad1p = ad0;
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

/* The per-sample work in steps that take each state value by pointer: the
 * per-sample path (mistress_process) passes the state fields, the block path
 * (mistress_block) passes scalar locals; the arithmetic is written once and
 * both are bit-identical (tests/host/mistress_block_test.cpp). */

/* 1 + 5. Pre-BBD coupling-cap HPF (80 Hz, TPT), then the anti-alias LPF cascade
 * (12 kHz 1st-order + 12 kHz Q 0.707 biquad); *dry = the high-passed input */
TS_INLINE float mistress_pre_step(float *hp, float *sa, float *b1, float *b2, float x, float *dry)
{
    float v_hp = (x - *hp) * MISTRESS_G_PRE_HP;
    float lp_hp = v_hp + *hp;
    *hp = lp_hp + v_hp;
    float drySample = x - lp_hp;
    *dry = drySample;

    float v_preA = (drySample - *sa) * MISTRESS_G_PRE_A;
    float preFiltered = v_preA + *sa;
    *sa = preFiltered + v_preA;

    float y_preB = MISTRESS_PRE_B_B0 * preFiltered + *b1;
    *b1 = MISTRESS_PRE_B_B1 * preFiltered - MISTRESS_PRE_B_A1 * y_preB + *b2;
    *b2 = MISTRESS_PRE_B_B2 * preFiltered - MISTRESS_PRE_B_A2 * y_preB;
    return y_preB;
}

/* 2. LFO phase accumulator */
TS_INLINE float mistress_phase_step(float *ph, const MistressCoeffs *k)
{
    float lfoPhase = *ph + k->phaseInc;
    lfoPhase -= (lfoPhase >= 1.0f) ? 1.0f : 0.0f;
    *ph = lfoPhase;
    return lfoPhase;
}

/* 3 + 4. Delay time (samples) and CTI alpha from the phase: pure */
TS_INLINE float mistress_mod(const MistressCoeffs *k, float lfoPhase, float *ctiAlpha)
{
    float lfo_shape = mistress_lfo_shape(lfoPhase);
    float shape = k->matrixMode ? 1.0f : lfo_shape;
    float u = shape * k->depth;
    float delayMs = 0.64f + shape * k->depthRangeMs;
    float delayInSamples = delayMs * 44.1f;

    float ctiCutoff = 8000.0f - 5500.0f * u;
    float z = ctiCutoff * (6.28318530717958647692f / 44100.0f);
    *ctiAlpha = 1.0f - ts_rcp(ts_exp_pos(z));
    return delayInSamples;
}

/* 8. Lagrange 3rd-order fractional delay read; wp = the write position after
 * this sample's write. The shortest delay is 0.64 ms = 28.2 samples, so a
 * read never reaches a sample written less than 28 samples earlier. */
TS_INLINE float mistress_read(const float *buf, unsigned int wp, float delayInSamples)
{
    int M = (int)delayInSamples;
    float mu = delayInSamples - (float)M;
    float pm1 = buf[(wp - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p0  = buf[(wp - 1u - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p1  = buf[(wp - 2u - (unsigned int)M) & MISTRESS_BUF_MASK];
    float p2  = buf[(wp - 3u - (unsigned int)M) & MISTRESS_BUF_MASK];

    float m1 = mu - 1.0f;
    float m2 = mu - 2.0f;
    float p1_mu = mu + 1.0f;
    float Lm1 = -mu * m1 * m2 * (1.0f / 6.0f);
    float L0  =  p1_mu * m1 * m2 * 0.5f;
    float L1  = -p1_mu * mu * m2 * 0.5f;
    float L2  =  p1_mu * mu * m1 * (1.0f / 6.0f);
    return Lm1 * pm1 + L0 * p0 + L1 * p1 + L2 * p2;
}

/* 9. CTI one-pole low-pass */
TS_INLINE float mistress_cti_step(float *cti, float alpha, float wet)
{
    *cti += alpha * (wet - *cti);
    return *cti;
}

/* 10 + 11. Post-BBD DC block HPF (5 Hz) + reconstruction LPF cascade (8 kHz 1st
 * + 8 kHz biquad + 8.5 kHz biquad), then the dry/wet mix */
TS_INLINE float mistress_post_step(float *dc, float *sa, float *b1, float *b2, float *c1, float *c2,
                                   const MistressCoeffs *k, float wetSample, float drySample)
{
    float v_postDc = (wetSample - *dc) * MISTRESS_G_POST_DC;
    float lp_postDc = v_postDc + *dc;
    *dc = lp_postDc + v_postDc;
    float postFiltered = wetSample - lp_postDc;

    float v_postA = (postFiltered - *sa) * MISTRESS_G_POST_A;
    postFiltered = v_postA + *sa;
    *sa = postFiltered + v_postA;

    float y_postB = MISTRESS_POST_B_B0 * postFiltered + *b1;
    *b1 = MISTRESS_POST_B_B1 * postFiltered - MISTRESS_POST_B_A1 * y_postB + *b2;
    *b2 = MISTRESS_POST_B_B2 * postFiltered - MISTRESS_POST_B_A2 * y_postB;
    postFiltered = y_postB;

    float y_postC = MISTRESS_POST_C_B0 * postFiltered + *c1;
    *c1 = MISTRESS_POST_C_B1 * postFiltered - MISTRESS_POST_C_A1 * y_postC + *c2;
    *c2 = MISTRESS_POST_C_B2 * postFiltered - MISTRESS_POST_C_A2 * y_postC;
    postFiltered = y_postC;

    return drySample * k->dryGain + postFiltered * k->wetGain;
}

TS_INLINE float mistress_process(MistressState *s, const MistressCoeffs *k, float x)
{
    float drySample, ctiAlpha;
    float preFiltered = mistress_pre_step(&s->s_preHP, &s->s_preA, &s->v1_preB, &s->v2_preB, x, &drySample);
    float lfoPhase = mistress_phase_step(&s->lfoPhase, k);
    float delayInSamples = mistress_mod(k, lfoPhase, &ctiAlpha);

    /* 6. Feedback ADAA tanh clip */
    float fbSignal = mistress_adaa_step(&s->adaa_x1, &s->adaa_ad1, s->feedbackState);

    /* 7. Feedback sum & delay write */
    float bbdIn = preFiltered + fbSignal * k->feedbackGain;
    unsigned int wp = (unsigned int)s->wp;
    s->buf[wp] = bbdIn;
    wp = (wp + 1u) & MISTRESS_BUF_MASK;
    s->wp = (int)wp;

    float wetSample = mistress_cti_step(&s->ctiState, ctiAlpha, mistress_read(s->buf, wp, delayInSamples));
    s->feedbackState = wetSample;

    return mistress_post_step(&s->s_postDc, &s->s_postA, &s->v1_postB, &s->v2_postB,
                              &s->v1_postC, &s->v2_postC, k, wetSample, drySample);
}

/* Block form for the C6745 (docs/C6745_DESIGN.md): the same arithmetic over n
 * <= 16 samples, stage-major. The reads never reach this block's writes
 * (shortest delay 28 samples), so the only true recurrence left is the CTI
 * one-pole; the feedback clip runs on the CTI outputs afterwards and the
 * writes come last. */
#define MISTRESS_BLK_MAX 16
#if defined(__TI_COMPILER_VERSION__)
#define MISTRESS_RESTRICT restrict
#define MISTRESS_LOOP _Pragma("MUST_ITERATE(1, MISTRESS_BLK_MAX)")
#else
#define MISTRESS_RESTRICT __restrict
#define MISTRESS_LOOP
#endif
TS_INLINE void mistress_block(MistressState *MISTRESS_RESTRICT s, const MistressCoeffs *MISTRESS_RESTRICT k,
                              const float *MISTRESS_RESTRICT in, float *MISTRESS_RESTRICT out, int n)
{
    float dry[MISTRESS_BLK_MAX], pre[MISTRESS_BLK_MAX], dly[MISTRESS_BLK_MAX], alpha[MISTRESS_BLK_MAX];
    float wet[MISTRESS_BLK_MAX], ad[MISTRESS_BLK_MAX], mid[MISTRESS_BLK_MAX];
    unsigned int wp0 = (unsigned int)s->wp;
    int i;
    {   /* pre filters (three short recurrences) */
        float hp = s->s_preHP, sa = s->s_preA, b1 = s->v1_preB, b2 = s->v2_preB;
        MISTRESS_LOOP
        for (i = 0; i < n; ++i)
            pre[i] = mistress_pre_step(&hp, &sa, &b1, &b2, in[i], &dry[i]);
        s->s_preHP = hp; s->s_preA = sa; s->v1_preB = b1; s->v2_preB = b2;
    }
    {   /* LFO phase, then the modulation (pure) */
        float ph = s->lfoPhase;
        MISTRESS_LOOP
        for (i = 0; i < n; ++i)
            dly[i] = mistress_phase_step(&ph, k);
        s->lfoPhase = ph;
    }
    MISTRESS_LOOP
    for (i = 0; i < n; ++i)
        dly[i] = mistress_mod(k, dly[i], &alpha[i]);
    MISTRESS_LOOP
    for (i = 0; i < n; ++i)                 /* reads: older samples only */
        wet[i] = mistress_read(s->buf, (wp0 + (unsigned int)i + 1u) & MISTRESS_BUF_MASK, dly[i]);
    {   /* the CTI one-pole: the one recurrence */
        float cti = s->ctiState;
        MISTRESS_LOOP
        for (i = 0; i < n; ++i)
            wet[i] = mistress_cti_step(&cti, alpha[i], wet[i]);
        s->ctiState = cti;
    }
    {   /* feedback clip of the previous sample's wet: pure passes, then the writes */
        float fs = s->feedbackState, x1 = s->adaa_x1, ad1 = s->adaa_ad1, g = k->feedbackGain;
        MISTRESS_LOOP
        for (i = 0; i < n; ++i)
            ad[i] = mistress_ln_cosh(i ? wet[i - 1] : fs);
        MISTRESS_LOOP
        for (i = 0; i < n; ++i) {
            float xi = i ? wet[i - 1] : fs, xp = i > 1 ? wet[i - 2] : (i ? fs : x1);
            mid[i] = mistress_mean_tanh(xp, 0.5f * (xi - xp));
        }
        MISTRESS_LOOP
        for (i = 0; i < n; ++i) {
            float xi = i ? wet[i - 1] : fs;
            float fb = mistress_adaa_mix(xi, x1, ad[i], ad1, mid[i]);
            s->buf[(wp0 + (unsigned int)i) & MISTRESS_BUF_MASK] = pre[i] + fb * g;
            x1 = xi;
            ad1 = ad[i];
        }
        s->adaa_x1 = x1; s->adaa_ad1 = ad1;
        s->feedbackState = wet[n - 1];
        s->wp = (int)((wp0 + (unsigned int)n) & MISTRESS_BUF_MASK);
    }
    {   /* post filters and mix */
        float dc = s->s_postDc, sa = s->s_postA, b1 = s->v1_postB, b2 = s->v2_postB;
        float c1 = s->v1_postC, c2 = s->v2_postC;
        MISTRESS_LOOP
        for (i = 0; i < n; ++i)
            out[i] = mistress_post_step(&dc, &sa, &b1, &b2, &c1, &c2, k, wet[i], dry[i]);
        s->s_postDc = dc; s->s_postA = sa; s->v1_postB = b1; s->v2_postB = b2;
        s->v1_postC = c1; s->v2_postC = c2;
    }
}

#endif /* MISTRESS_G1_H */

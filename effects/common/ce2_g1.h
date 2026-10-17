/* ce2_g1.h - CF CE-2 core for the G1X Four (Boss CE-2 chorus, MN3007 BBD,
 * port of Comet Flower's ChorusProcessor). Shared by the pedal kernel (an
 * effects/<name>/<name>.c this kit does not include) and the PC bench
 * (tests/host/ce2_accuracy.cpp).
 *
 * CONTRACT (the bench depends on exactly this; do not change):
 *   typedef struct { ... } Ce2State;    zero-initialised = silent start,
 *         LFO phase 0 -- matches the desktop's channel-0 reset phase
 *   typedef struct { ... } Ce2Coeffs;
 *   void  ce2_coeffs(Ce2Coeffs *k, float rate, float depth, float mix);
 *         rate  0.1..8.0  (Comet Flower "Rate", APVTS knob units; maps
 *               LINEARLY to an LFO frequency of 0.1..3.5 Hz, matching the
 *               desktop's jmap -- do this mapping inside ce2_coeffs, not
 *               in the caller)
 *         depth 0..1      (Comet Flower "Depth"); sweep width = 5 ms * depth
 *         mix   0..1      (Comet Flower "Mix"); wet weight = 0.5 * mix,
 *               dry weight always 0.5 (the CE-2's hardwired summing amp)
 *         Called once per 16-sample block; may be costly-ish but no loops
 *         over more than a few dozen items.
 *   float ce2_process(Ce2State *s, const Ce2Coeffs *k, float x);
 *         one 44.1 kHz input sample -> one output sample. Mono, no added
 *         latency: the bench compares candidate and reference sample for
 *         sample, so any internal oversampling you add must stay sample-
 *         synchronous (zero or exactly-compensated group delay).
 */
#ifndef CE2_G1_H
#define CE2_G1_H

#include "ts808_core.h"         /* TS_INLINE, ts_clamp, ts_rcp */
#include <math.h>

/* --- Fixed filter coefficients at 44100 Hz --- */
/* Pre-emphasis: High shelf +15 dB, 979 Hz, Q 0.70710678 */
#define CE2_PRE_B0   5.1523022638e+00f
#define CE2_PRE_B1  -9.6448137581e+00f
#define CE2_PRE_B2   4.5322870492e+00f
#define CE2_PRE_A1  -1.6987661970e+00f
#define CE2_PRE_A2   7.3854175192e-01f

/* De-emphasis: High shelf -15 dB, 979 Hz, Q 0.70710678 */
#define CE2_DE_B0    1.9408799189e-01f
#define CE2_DE_B1   -3.2971011988e-01f
#define CE2_DE_B2    1.4334208556e-01f
#define CE2_DE_A1   -1.8719425345e+00f
#define CE2_DE_A2    8.7966249205e-01f

/* Anti-alias filters: 48 Hz HPF, 6.6 kHz LP1, 6.6 kHz LP2 (Q 0.70710678) */
#define CE2_AA_HP_G     3.4077812199e-03f
#define CE2_AA_LP1_G    3.3694925612e-01f
#define CE2_AA_LP2_B0   1.3063087650e-01f
#define CE2_AA_LP2_B1   2.6126175300e-01f
#define CE2_AA_LP2_B2   1.3063087650e-01f
#define CE2_AA_LP2_A1  -7.5041172788e-01f
#define CE2_AA_LP2_A2   2.7293523387e-01f

/* Reconstruction filters: 14.6 Hz HPF, 6.9 kHz LP1, 6.9 kHz LP2 (Q 0.70710678) */
#define CE2_RECON_HP_G     1.0389935031e-03f
#define CE2_RECON_LP1_G    3.4869123995e-01f
#define CE2_RECON_LP2_B0   1.4024284605e-01f
#define CE2_RECON_LP2_B1   2.8048569210e-01f
#define CE2_RECON_LP2_B2   1.4024284605e-01f
#define CE2_RECON_LP2_A1  -6.9810814731e-01f
#define CE2_RECON_LP2_A2   2.5907953150e-01f

/* 72 Hz LFO smoothing coefficient */
#define CE2_LFO_SMOOTH_COEFF 1.0205825215e-02f

typedef struct {
    float pre_v1, pre_v2;
    float aa_hp_s;
    float aa_lp1_s;
    float aa_lp2_v1, aa_lp2_v2;
    float sat_x1, sat_ad1;
    float delay_buf[1024];
    int delay_wp;
    float lfo_phase;
    float lfo_smoothed;
    float cti_state;
    float recon_hp_s;
    float recon_lp1_s;
    float recon_lp2_v1, recon_lp2_v2;
    float de_v1, de_v2;
} Ce2State;

typedef struct {
    float phaseInc;
    float sweepMs;
    float wetGain;
} Ce2Coeffs;

TS_INLINE void ce2_coeffs(Ce2Coeffs *k, float rate, float depth, float mix)
{
    float rate_c = ts_clamp(rate, 0.1f, 8.0f);
    float depth_c = ts_clamp(depth, 0.0f, 1.0f);
    float mix_c = ts_clamp(mix, 0.0f, 1.0f);

    /* APVTS knob 0.1..8.0 linearly mapped to 0.1..3.5 Hz */
    float rateHz = 0.1f + (rate_c - 0.1f) * (3.4f / 7.9f);
    k->phaseInc = rateHz * (1.0f / 44100.0f);
    k->sweepMs = 5.0f * depth_c;
    k->wetGain = 0.5f * mix_c;
}

TS_INLINE float ce2_ln_cosh(float z)
{
    float a = fabsf(z);
    return a + log1pf(expf(-2.0f * a)) - 0.6931471805599453f;
}

TS_INLINE float ce2_biquad_process(float x, float b0, float b1, float b2, float a1, float a2, float *v1, float *v2)
{
    float y = b0 * x + *v1;
    *v1 = b1 * x - a1 * y + *v2;
    *v2 = b2 * x - a2 * y;
    return y;
}

TS_INLINE float ce2_process(Ce2State *s, const Ce2Coeffs *k, float x)
{
    float dry = x;

    /* 1. Pre-emphasis */
    float bbdIn = ce2_biquad_process(dry, CE2_PRE_B0, CE2_PRE_B1, CE2_PRE_B2, CE2_PRE_A1, CE2_PRE_A2, &s->pre_v1, &s->pre_v2);

    /* 2. Anti-aliasing cascade */
    bbdIn = bbdIn - ts_onepole_lp(&s->aa_hp_s, CE2_AA_HP_G, bbdIn);
    bbdIn = ts_onepole_lp(&s->aa_lp1_s, CE2_AA_LP1_G, bbdIn);
    bbdIn = ce2_biquad_process(bbdIn, CE2_AA_LP2_B0, CE2_AA_LP2_B1, CE2_AA_LP2_B2, CE2_AA_LP2_A1, CE2_AA_LP2_A2, &s->aa_lp2_v1, &s->aa_lp2_v2);

    /* 3. MN3007 BBD soft saturation (ADAA tanh(0.7x)/0.7) */
    {
        float ad0 = ce2_ln_cosh(bbdIn * 0.7f) * (1.0f / 0.7f);
        float diff = bbdIn - s->sat_x1;
        float sat_out;
        if (fabsf(diff) > 1.0e-5f) {
            sat_out = (ad0 - s->sat_ad1) / diff;
        } else {
            sat_out = tanhf(0.5f * (bbdIn + s->sat_x1) * 0.7f);
        }
        s->sat_x1 = bbdIn;
        s->sat_ad1 = ad0;
        bbdIn = sat_out * (1.0f / 0.7f);
    }

    /* 4. Delay push */
    s->delay_buf[s->delay_wp] = bbdIn;
    s->delay_wp = (s->delay_wp + 1) & 1023;

    /* 5. Triangle LFO smoothed by 72 Hz one-pole */
    float phi = s->lfo_phase;
    float lfoTri = (phi < 0.5f) ? (phi * 2.0f) : (2.0f - phi * 2.0f);
    float lfoRaw = lfoTri * 2.0f - 1.0f;
    s->lfo_smoothed += CE2_LFO_SMOOTH_COEFF * (lfoRaw - s->lfo_smoothed);
    float lfoMod = s->lfo_smoothed;

    /* 6. BBD Delay read (Lagrange 3rd-order) */
    float delayMs = 12.8f + lfoMod * k->sweepMs;
    float delaySamples = delayMs * 44.1f;
    int M = (int)delaySamples;
    float mu = delaySamples - (float)M;

    /* Lagrange 3rd-order basis polynomials */
    float mu_m1 = mu - 1.0f;
    float mu_m2 = mu - 2.0f;
    float mu_p1 = mu + 1.0f;
    float Lm1 = -mu * mu_m1 * mu_m2 * (1.0f / 6.0f);
    float L0  =  mu_p1 * mu_m1 * mu_m2 * 0.5f;
    float L1  = -mu_p1 * mu * mu_m2 * 0.5f;
    float L2  =  mu_p1 * mu * mu_m1 * (1.0f / 6.0f);

    int wp = s->delay_wp;
    float pm1 = s->delay_buf[(wp - 1 - (M - 1) + 2048) & 1023];
    float p0  = s->delay_buf[(wp - 1 - M + 2048) & 1023];
    float p1  = s->delay_buf[(wp - 1 - (M + 1) + 2048) & 1023];
    float p2  = s->delay_buf[(wp - 1 - (M + 2) + 2048) & 1023];
    float wet = Lm1 * pm1 + L0 * p0 + L1 * p1 + L2 * p2;

    /* 7. CTI dynamic one-pole low pass */
    float bbdClockNorm = ts_clamp((17.8f - delayMs) * 0.1f, 0.0f, 1.0f);
    float ctiFc = 3000.0f + bbdClockNorm * 4000.0f;
    float ctiCoeff = 1.0f - expf(-2.0f * 3.14159265358979323846f * ctiFc * (1.0f / 44100.0f));
    s->cti_state += ctiCoeff * (wet - s->cti_state);
    wet = s->cti_state;

    /* 8. Reconstruction cascade */
    wet = wet - ts_onepole_lp(&s->recon_hp_s, CE2_RECON_HP_G, wet);
    wet = ts_onepole_lp(&s->recon_lp1_s, CE2_RECON_LP1_G, wet);
    wet = ce2_biquad_process(wet, CE2_RECON_LP2_B0, CE2_RECON_LP2_B1, CE2_RECON_LP2_B2, CE2_RECON_LP2_A1, CE2_RECON_LP2_A2, &s->recon_lp2_v1, &s->recon_lp2_v2);

    /* 9. De-emphasis */
    wet = ce2_biquad_process(wet, CE2_DE_B0, CE2_DE_B1, CE2_DE_B2, CE2_DE_A1, CE2_DE_A2, &s->de_v1, &s->de_v2);

    /* 10. Dry / wet mix */
    float out = dry * 0.5f + wet * k->wetGain;

    /* Advance LFO phase */
    s->lfo_phase += k->phaseInc;
    if (s->lfo_phase >= 1.0f) s->lfo_phase -= 1.0f;

    return out;
}

#endif /* CE2_G1_H */

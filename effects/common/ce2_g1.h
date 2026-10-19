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
#include "ce2_sat_table.h"

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

/* 72 Hz LFO smoothing coefficient: 1 - exp(-2*pi*72/44100) */
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
    float a = z < 0.0f ? -z : z;
    float a_tab = (a < CE2_SAT_ZMAX) ? a : 0.0f;
    float p = a_tab * CE2_SAT_INV_DZ;
    int idx = (int)p;
    idx = (idx > 255) ? 255 : idx;
    float t = p - (float)idx;
    const float *c = ce2_sat_table[idx];
    float y_table = c[0] + t * (c[1] + t * (c[2] + t * c[3]));
    float y_asymp = a - CE2_SAT_LN2;
    return (a >= CE2_SAT_ZMAX) ? y_asymp : y_table;
}

TS_INLINE float ce2_tanh(float z)
{
    float a = z < 0.0f ? -z : z;
    float a_tab = (a < CE2_SAT_ZMAX) ? a : 0.0f;
    float p = a_tab * CE2_SAT_INV_DZ;
    int idx = (int)p;
    idx = (idx > 255) ? 255 : idx;
    float t = p - (float)idx;
    const float *c = ce2_sat_table[idx];
    float der = (c[1] + t * (2.0f * c[2] + t * (3.0f * c[3]))) * CE2_SAT_INV_DZ;
    float y_table = (z < 0.0f) ? -der : der;
    float y_asymp = (z < 0.0f) ? -1.0f : 1.0f;
    return (a >= CE2_SAT_ZMAX) ? y_asymp : y_table;
}

TS_INLINE float ce2_biquad_process(float x, float b0, float b1, float b2, float a1, float a2, float *v1, float *v2)
{
    float y = b0 * x + *v1;
    *v1 = b1 * x - a1 * y + *v2;
    *v2 = b2 * x - a2 * y;
    return y;
}

/* The per-sample work in steps that take each state value by pointer: the
 * per-sample path (ce2_process) passes the state fields, the block path
 * (ce2_block) passes scalar locals; the arithmetic is written once and both
 * are bit-identical (tests/host/ce2_block_test.cpp). */

/* 1 + 2. Pre-emphasis (+15 dB high shelf at 979 Hz), anti-aliasing cascade
 * (48 Hz HPF + 6.6 kHz 3-pole LP) */
TS_INLINE float ce2_in_step(float *pv1, float *pv2, float *hp, float *lp1, float *l2v1, float *l2v2, float dry)
{
    float bbdIn = ce2_biquad_process(dry, CE2_PRE_B0, CE2_PRE_B1, CE2_PRE_B2, CE2_PRE_A1, CE2_PRE_A2, pv1, pv2);
    bbdIn = bbdIn - ts_onepole_lp(hp, CE2_AA_HP_G, bbdIn);
    bbdIn = ts_onepole_lp(lp1, CE2_AA_LP1_G, bbdIn);
    return ce2_biquad_process(bbdIn, CE2_AA_LP2_B0, CE2_AA_LP2_B1, CE2_AA_LP2_B2, CE2_AA_LP2_A1, CE2_AA_LP2_A2, l2v1, l2v2);
}

/* 3. MN3007 BBD soft saturation (ADAA tanh(0.7x)/0.7); its two table
 * evaluations are pure, so the block path runs them as passes */
TS_INLINE float ce2_sat_ad(float bbdIn) { return ce2_ln_cosh(bbdIn * 0.7f) * (1.0f / 0.7f); }
TS_INLINE float ce2_sat_mid(float bbdIn, float x1) { return ce2_tanh(0.5f * (bbdIn + x1) * 0.7f); }
TS_INLINE float ce2_sat_mix(float bbdIn, float x1, float ad0, float ad1, float sat_fallback)
{
    float diff = bbdIn - x1;
    float abs_diff = diff < 0.0f ? -diff : diff;
    float safe_diff = (abs_diff < 1.0e-5f) ? 1.0e-5f : diff;
    float sat_quot = (ad0 - ad1) * ts_rcp(safe_diff);
    float sat_out = (abs_diff < 1.0e-5f) ? sat_fallback : sat_quot;
    return sat_out * (1.0f / 0.7f);
}

/* 5. Triangle LFO smoothed by 72 Hz one-pole, from the phase before it advances */
TS_INLINE float ce2_lfo_step(float *smoothed, float phi)
{
    float lfoTri = (phi < 0.5f) ? (phi * 2.0f) : (2.0f - phi * 2.0f);
    float lfoRaw = lfoTri * 2.0f - 1.0f;
    *smoothed += CE2_LFO_SMOOTH_COEFF * (lfoRaw - *smoothed);
    return *smoothed;
}

/* Advance the LFO phase */
TS_INLINE float ce2_phase_step(float *ph, const Ce2Coeffs *k)
{
    float p = *ph + k->phaseInc;
    p -= (p >= 1.0f) ? 1.0f : 0.0f;
    *ph = p;
    return p;
}

/* 6 + 7a. BBD delay read (Lagrange 3rd-order fractional read; wp = the write
 * position after this sample's push) and the CTI coefficient: pure. The delay
 * is 7.8..17.8 ms, so a read never reaches the current block's later pushes. */
TS_INLINE float ce2_read(const float *buf, int wp, const Ce2Coeffs *k, float lfoMod, float *ctiCoeffOut)
{
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

    float pm1 = buf[(wp - 1 - (M - 1) + 2048) & 1023];
    float p0  = buf[(wp - 1 - M + 2048) & 1023];
    float p1  = buf[(wp - 1 - (M + 1) + 2048) & 1023];
    float p2  = buf[(wp - 1 - (M + 2) + 2048) & 1023];
    float wet = Lm1 * pm1 + L0 * p0 + L1 * p1 + L2 * p2;

    /* 7. CTI dynamic one-pole low pass (swept 3 kHz..7 kHz with BBD clock) */
    float bbdClockNorm = ts_clamp((17.8f - delayMs) * 0.1f, 0.0f, 1.0f);
    /* Degree-6 polynomial fit for 1 - exp(-2*pi*(3000 + 4000*b)/44100) on b in [0, 1] */
    float ctiCoeff = -2.3402821807e-05f;
    ctiCoeff = ctiCoeff * bbdClockNorm + 3.1669828878e-04f;
    ctiCoeff = ctiCoeff * bbdClockNorm - 2.8597907957e-03f;
    ctiCoeff = ctiCoeff * bbdClockNorm + 2.0117343879e-02f;
    ctiCoeff = ctiCoeff * bbdClockNorm - 1.0591106449e-01f;
    ctiCoeff = ctiCoeff * bbdClockNorm + 3.7168222915e-01f;
    ctiCoeff = ctiCoeff * bbdClockNorm + 3.4781536380e-01f;
    *ctiCoeffOut = ctiCoeff;
    return wet;
}

TS_INLINE float ce2_cti_step(float *cti, float ctiCoeff, float wet)
{
    *cti += ctiCoeff * (wet - *cti);
    return *cti;
}

/* 8-10. Reconstruction cascade (14.6 Hz HPF + 6.9 kHz 3-pole LP), de-emphasis
 * (-15 dB high shelf at 979 Hz), dry/wet mix */
TS_INLINE float ce2_out_step(float *hp, float *lp1, float *l2v1, float *l2v2, float *dv1, float *dv2,
                             const Ce2Coeffs *k, float wet, float dry)
{
    wet = wet - ts_onepole_lp(hp, CE2_RECON_HP_G, wet);
    wet = ts_onepole_lp(lp1, CE2_RECON_LP1_G, wet);
    wet = ce2_biquad_process(wet, CE2_RECON_LP2_B0, CE2_RECON_LP2_B1, CE2_RECON_LP2_B2, CE2_RECON_LP2_A1, CE2_RECON_LP2_A2, l2v1, l2v2);
    wet = ce2_biquad_process(wet, CE2_DE_B0, CE2_DE_B1, CE2_DE_B2, CE2_DE_A1, CE2_DE_A2, dv1, dv2);
    return dry * 0.5f + wet * k->wetGain;
}

TS_INLINE float ce2_process(Ce2State *s, const Ce2Coeffs *k, float x)
{
    float dry = x, ctiCoeff;
    float bbdIn = ce2_in_step(&s->pre_v1, &s->pre_v2, &s->aa_hp_s, &s->aa_lp1_s, &s->aa_lp2_v1, &s->aa_lp2_v2, dry);

    {
        float ad0 = ce2_sat_ad(bbdIn);
        float out = ce2_sat_mix(bbdIn, s->sat_x1, ad0, s->sat_ad1, ce2_sat_mid(bbdIn, s->sat_x1));
        s->sat_x1 = bbdIn;
        s->sat_ad1 = ad0;
        bbdIn = out;
    }

    /* 4. Delay push */
    s->delay_buf[s->delay_wp] = bbdIn;
    s->delay_wp = (s->delay_wp + 1) & 1023;

    float lfoMod = ce2_lfo_step(&s->lfo_smoothed, s->lfo_phase);
    float wet = ce2_read(s->delay_buf, s->delay_wp, k, lfoMod, &ctiCoeff);
    wet = ce2_cti_step(&s->cti_state, ctiCoeff, wet);
    float out = ce2_out_step(&s->recon_hp_s, &s->recon_lp1_s, &s->recon_lp2_v1, &s->recon_lp2_v2,
                             &s->de_v1, &s->de_v2, k, wet, dry);
    ce2_phase_step(&s->lfo_phase, k);
    return out;
}

/* Block form for the C6745 (docs/C6745_DESIGN.md): the same arithmetic over
 * n <= 16 samples, stage-major. A chorus has no feedback: the block's pushes
 * depend on the input only and come first; every read then sees what it saw
 * per sample (the delay is at least 344 samples, the buffer 1024). */
#define CE2_BLK_MAX 16
#if defined(__TI_COMPILER_VERSION__)
#define CE2_RESTRICT restrict
#define CE2_LOOP _Pragma("MUST_ITERATE(1, CE2_BLK_MAX)")
#else
#define CE2_RESTRICT __restrict
#define CE2_LOOP
#endif
TS_INLINE void ce2_block(Ce2State *CE2_RESTRICT s, const Ce2Coeffs *CE2_RESTRICT k,
                         const float *CE2_RESTRICT in, float *CE2_RESTRICT out, int n)
{
    float bbd[CE2_BLK_MAX], ad[CE2_BLK_MAX], mid[CE2_BLK_MAX], lfo[CE2_BLK_MAX];
    float wet[CE2_BLK_MAX], cc[CE2_BLK_MAX];
    int wp0 = s->delay_wp, i;
    {   /* pre-emphasis and anti-aliasing (four short recurrences) */
        float pv1 = s->pre_v1, pv2 = s->pre_v2, hp = s->aa_hp_s, lp1 = s->aa_lp1_s;
        float l2v1 = s->aa_lp2_v1, l2v2 = s->aa_lp2_v2;
        CE2_LOOP
        for (i = 0; i < n; ++i)
            bbd[i] = ce2_in_step(&pv1, &pv2, &hp, &lp1, &l2v1, &l2v2, in[i]);
        s->pre_v1 = pv1; s->pre_v2 = pv2; s->aa_hp_s = hp; s->aa_lp1_s = lp1;
        s->aa_lp2_v1 = l2v1; s->aa_lp2_v2 = l2v2;
    }
    {   /* BBD saturation: pure passes, then the mix and the pushes */
        float x1 = s->sat_x1, ad1 = s->sat_ad1;
        CE2_LOOP
        for (i = 0; i < n; ++i)
            ad[i] = ce2_sat_ad(bbd[i]);
        CE2_LOOP
        for (i = 0; i < n; ++i)
            mid[i] = ce2_sat_mid(bbd[i], i ? bbd[i - 1] : x1);
        CE2_LOOP
        for (i = 0; i < n; ++i) {
            float b = bbd[i];
            s->delay_buf[(wp0 + i) & 1023] = ce2_sat_mix(b, x1, ad[i], ad1, mid[i]);
            x1 = b;
            ad1 = ad[i];
        }
        s->sat_x1 = x1; s->sat_ad1 = ad1;
        s->delay_wp = (wp0 + n) & 1023;
    }
    {   /* LFO: smoothing of the phase before each advance */
        float sm = s->lfo_smoothed, ph = s->lfo_phase;
        CE2_LOOP
        for (i = 0; i < n; ++i) {
            lfo[i] = ce2_lfo_step(&sm, ph);
            ce2_phase_step(&ph, k);
        }
        s->lfo_smoothed = sm; s->lfo_phase = ph;
    }
    CE2_LOOP
    for (i = 0; i < n; ++i)                 /* reads and CTI coefficients: pure */
        wet[i] = ce2_read(s->delay_buf, (wp0 + i + 1) & 1023, k, lfo[i], &cc[i]);
    {
        float cti = s->cti_state;
        CE2_LOOP
        for (i = 0; i < n; ++i)
            wet[i] = ce2_cti_step(&cti, cc[i], wet[i]);
        s->cti_state = cti;
    }
    {
        float hp = s->recon_hp_s, lp1 = s->recon_lp1_s, l2v1 = s->recon_lp2_v1, l2v2 = s->recon_lp2_v2;
        float dv1 = s->de_v1, dv2 = s->de_v2;
        CE2_LOOP
        for (i = 0; i < n; ++i)
            out[i] = ce2_out_step(&hp, &lp1, &l2v1, &l2v2, &dv1, &dv2, k, wet[i], in[i]);
        s->recon_hp_s = hp; s->recon_lp1_s = lp1; s->recon_lp2_v1 = l2v1; s->recon_lp2_v2 = l2v2;
        s->de_v1 = dv1; s->de_v2 = dv2;
    }
}

#endif /* CE2_G1_H */

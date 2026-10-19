/* rat_g1.h - CF RAT core for the G1X Four (ProCo RAT, port of Comet Flower's
 * RatProcessor). Shared by the pedal kernel (effects/ratx/ratx.c) and the PC
 * bench (tests/host/rat_accuracy.cpp).
 *
 * CONTRACT (the bench and the kernel depend on exactly this; do not change):
 *   typedef struct { ... } RatState;    zero-initialised = silent start
 *   typedef struct { ... } RatCoeffs;
 *   void  rat_coeffs(RatCoeffs *k, float dist, float filter, float vol);
 *         dist   0..10  (Comet Flower "Distortion")
 *         filter 0..1   (Comet Flower "Filter", up = brighter)
 *         vol    linear output gain, applied after the 1.67 makeup
 *         Called once per 16-sample block; may be costly-ish but no loops
 *         over more than a few dozen items.
 *   float rat_process(RatState *s, const RatCoeffs *k, float x);
 *         one 44.1 kHz input sample (volts) -> one output sample
 */
#ifndef RAT_G1_H
#define RAT_G1_H

#include "ts808_core.h"         /* TS_INLINE, ts_clamp, ts_rcp */
#include "os_hbiir.h"           /* HbiState1, HbiState2 */
#include "rat_blob.h"           /* rat_dtab, rat_g_fb, rat_g_opa, rat_Rf, rat_g_tone */

#define RAT_G_AC 8.903948232e-05f
#define RAT_G_LEGHI 1.351996004e-02f
#define RAT_G_LEGLO 5.384468064e-04f
#define RAT_MAX_DELTA 0.850340136f
typedef struct {
    HbiState1 up1;
    HbiState1 down1;
    HbiState2 up2;
    HbiState2 down2;
    HbiState2 up3;
    HbiState2 down3;
    float s_ac;
    float s_leghi;
    float s_leglo;
    float svf_fb_1;
    float svf_fb_2;
    float svf_opa_1;
    float svf_opa_2;
    float svf_tone_1;
    float svf_tone_2;
    float slew;
    float s_dc;
} RatState;

typedef struct {
    float vol;
    float g_fb;
    float h_fb;
    float g_opa;
    float h_opa;
    float g_tone;
    float h_tone;
    float boost_mult_hi;
    float boost_mult_lo;
} RatCoeffs;

TS_INLINE void rat_coeffs(RatCoeffs *k, float dist, float filter, float vol)
{
    k->vol = vol;
    
    float d = ts_clamp(dist, 0.0f, 10.0f);
    float f = ts_clamp(filter, 0.0f, 1.0f);
    
    float p_d = d * 25.5f;
    int idx_d = (int)p_d;
    if (idx_d > 254) idx_d = 254;
    if (idx_d < 0) idx_d = 0;
    float frac_d = p_d - (float)idx_d;
    
    k->g_fb = rat_g_fb[idx_d] + frac_d * (rat_g_fb[idx_d + 1] - rat_g_fb[idx_d]);
    k->h_fb = ts_rcp(1.0f + 1.41421356f * k->g_fb + k->g_fb * k->g_fb);
    
    k->g_opa = rat_g_opa[idx_d] + frac_d * (rat_g_opa[idx_d + 1] - rat_g_opa[idx_d]);
    k->h_opa = ts_rcp(1.0f + 1.41421356f * k->g_opa + k->g_opa * k->g_opa);
    
    float rf = rat_Rf[idx_d] + frac_d * (rat_Rf[idx_d + 1] - rat_Rf[idx_d]);
    k->boost_mult_hi = rf * 0.02127659574f; /* 1/47 */
    k->boost_mult_lo = rf * 0.00178571428f; /* 1/560 */

    float p_f = f * 255.0f;
    int idx_f = (int)p_f;
    if (idx_f > 254) idx_f = 254;
    if (idx_f < 0) idx_f = 0;
    float frac_f = p_f - (float)idx_f;
    
    k->g_tone = rat_g_tone[idx_f] + frac_f * (rat_g_tone[idx_f + 1] - rat_g_tone[idx_f]);
    k->h_tone = ts_rcp(1.0f + 1.41421356f * k->g_tone + k->g_tone * k->g_tone);
}

TS_INLINE float rat_core_stage(RatState *s, const RatCoeffs *k, float x)
{
    float v_ac = (x - s->s_ac) * RAT_G_AC;
    float lp_ac = v_ac + s->s_ac;
    s->s_ac = lp_ac + v_ac;
    x = x - lp_ac;

    float v_hi = (x - s->s_leghi) * RAT_G_LEGHI;
    float lp_hi = v_hi + s->s_leghi;
    s->s_leghi = lp_hi + v_hi;
    float hi = x - lp_hi;

    float v_lo = (x - s->s_leglo) * RAT_G_LEGLO;
    float lp_lo = v_lo + s->s_leglo;
    s->s_leglo = lp_lo + v_lo;
    float lo = x - lp_lo;

    float boost = k->boost_mult_hi * hi + k->boost_mult_lo * lo;

    float hp_fb = k->h_fb * (boost - s->svf_fb_1 * (k->g_fb + 1.41421356f) - s->svf_fb_2);
    float bp_fb = hp_fb * k->g_fb + s->svf_fb_1;
    s->svf_fb_1 = hp_fb * k->g_fb + bp_fb;
    float lp_fb = bp_fb * k->g_fb + s->svf_fb_2;
    s->svf_fb_2 = bp_fb * k->g_fb + lp_fb;

    x += lp_fb;

    float d = ts_clamp(x - s->slew, -RAT_MAX_DELTA, RAT_MAX_DELTA);
    x = s->slew + d;
    s->slew = x;

    float hp_opa = k->h_opa * (x - s->svf_opa_1 * (k->g_opa + 1.41421356f) - s->svf_opa_2);
    float bp_opa = hp_opa * k->g_opa + s->svf_opa_1;
    s->svf_opa_1 = hp_opa * k->g_opa + bp_opa;
    float lp_opa = bp_opa * k->g_opa + s->svf_opa_2;
    s->svf_opa_2 = bp_opa * k->g_opa + lp_opa;
    x = lp_opa;

    /* 5 Hz DC block (added by Gemini; not in the desktop model or the bench
     * reference). Physically plausible: the RAT couples the op-amp output to
     * the diodes through a capacitor. Affects only the deep-slew tests. */
    float v_dc = (x - s->s_dc) * 4.45197e-05f; /* 5 Hz at 352.8 kHz */
    float lp_dc = v_dc + s->s_dc;
    s->s_dc = lp_dc + v_dc;
    x = x - lp_dc;

    x = ts_clamp(x, -4.0f, 4.0f);

    union { float f; unsigned u; } b;
    b.f = x;
    unsigned sgn = b.u & 0x80000000u;
    b.u = b.u & 0x7fffffffu;
    float abs_x = b.f;
    
    float p = abs_x * RAT_DTAB_SCALE;
    int idx = (int)p;
    if (idx > RAT_DTAB_N - 2) {
        idx = RAT_DTAB_N - 2;
    }
    float frac = p - (float)idx;
    float v = rat_dtab[idx] + frac * (rat_dtab[idx + 1] - rat_dtab[idx]);
    
    b.f = v;
    b.u = b.u | sgn;
    x = b.f;

    float hp_tone = k->h_tone * (x - s->svf_tone_1 * (k->g_tone + 1.41421356f) - s->svf_tone_2);
    float bp_tone = hp_tone * k->g_tone + s->svf_tone_1;
    s->svf_tone_1 = hp_tone * k->g_tone + bp_tone;
    float lp_tone = bp_tone * k->g_tone + s->svf_tone_2;
    s->svf_tone_2 = bp_tone * k->g_tone + lp_tone;
    x = lp_tone;

    return x * 1.67f;
}

TS_INLINE float rat_process(RatState *s, const RatCoeffs *k, float x)
{
    float a1, b1, a2, b2, c2, d2, y8[8], y4[4], y2[2];
    
    hbi_up1(&s->up1, x, &a1, &b1);
    hbi_up2(&s->up2, a1, &a2, &b2);
    hbi_up2(&s->up2, b1, &c2, &d2);
    hbi_up2(&s->up3, a2, &y8[0], &y8[1]);
    hbi_up2(&s->up3, b2, &y8[2], &y8[3]);
    hbi_up2(&s->up3, c2, &y8[4], &y8[5]);
    hbi_up2(&s->up3, d2, &y8[6], &y8[7]);

    int i;
    for (i = 0; i < 8; ++i) {
        y8[i] = rat_core_stage(s, k, y8[i]);
    }

    y4[0] = hbi_down2(&s->down3, y8[0], y8[1]);
    y4[1] = hbi_down2(&s->down3, y8[2], y8[3]);
    y4[2] = hbi_down2(&s->down3, y8[4], y8[5]);
    y4[3] = hbi_down2(&s->down3, y8[6], y8[7]);

    y2[0] = hbi_down2(&s->down2, y4[0], y4[1]);
    y2[1] = hbi_down2(&s->down2, y4[2], y4[3]);
    x = hbi_down1(&s->down1, y2[0], y2[1]);

    return x * k->vol;
}

TS_INLINE void rat_block16(RatState *s, const RatCoeffs *k, const float *in, float *out)
{
    float b_a[128];
    float b_b[128];
    int i;

    /* 8x Upsampling: 16 -> 32 -> 64 -> 128 */
    hbi1_up_blk(&s->up1, in, b_a, 16);
    hbi2_up_blk(&s->up2, b_a, b_b, 32);
    hbi2_up_blk(&s->up3, b_b, b_a, 64);

    /* Pass 1: AC, Hi, Lo highpass filters + Boost + Feedback SVF lowpass */
    {
        float s_ac = s->s_ac;
        float s_hi = s->s_leghi;
        float s_lo = s->s_leglo;
        float fb1  = s->svf_fb_1;
        float fb2  = s->svf_fb_2;
        float g_fb = k->g_fb;
        float h_fb = k->h_fb;
        float g_fb_r2 = g_fb + 1.41421356f;
        float b_hi = k->boost_mult_hi;
        float b_lo = k->boost_mult_lo;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float x = b_a[i];

            float v_ac = (x - s_ac) * RAT_G_AC;
            float lp_ac = v_ac + s_ac;
            s_ac = lp_ac + v_ac;
            x = x - lp_ac;

            float v_hi = (x - s_hi) * RAT_G_LEGHI;
            float lp_hi = v_hi + s_hi;
            s_hi = lp_hi + v_hi;
            float hi = x - lp_hi;

            float v_lo = (x - s_lo) * RAT_G_LEGLO;
            float lp_lo = v_lo + s_lo;
            s_lo = lp_lo + v_lo;
            float lo = x - lp_lo;

            float boost = b_hi * hi + b_lo * lo;

            float hp_fb = h_fb * (boost - fb1 * g_fb_r2 - fb2);
            float bp_fb = hp_fb * g_fb + fb1;
            fb1 = hp_fb * g_fb + bp_fb;
            float lp_fb = bp_fb * g_fb + fb2;
            fb2 = bp_fb * g_fb + lp_fb;

            b_a[i] = x + lp_fb;
        }
        s->s_ac = s_ac;
        s->s_leghi = s_hi;
        s->s_leglo = s_lo;
        s->svf_fb_1 = fb1;
        s->svf_fb_2 = fb2;
    }

    /* Pass 2: Slew Limiter, Op-Amp SVF lowpass, DC blocking filter */
    {
        float slew = s->slew;
        float opa1 = s->svf_opa_1;
        float opa2 = s->svf_opa_2;
        float s_dc = s->s_dc;
        float g_opa = k->g_opa;
        float h_opa = k->h_opa;
        float g_opa_r2 = g_opa + 1.41421356f;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float x = b_a[i];

            float d = ts_clamp(x - slew, -RAT_MAX_DELTA, RAT_MAX_DELTA);
            slew = slew + d;

            float hp_opa = h_opa * (slew - opa1 * g_opa_r2 - opa2);
            float bp_opa = hp_opa * g_opa + opa1;
            opa1 = hp_opa * g_opa + bp_opa;
            float lp_opa = bp_opa * g_opa + opa2;
            opa2 = bp_opa * g_opa + lp_opa;

            float v_dc = (lp_opa - s_dc) * 4.45197e-05f;
            float lp_dc = v_dc + s_dc;
            s_dc = lp_dc + v_dc;

            b_a[i] = lp_opa - lp_dc;
        }
        s->slew = slew;
        s->svf_opa_1 = opa1;
        s->svf_opa_2 = opa2;
        s->s_dc = s_dc;
    }

    /* Pass 3: Clamp & 1N914 Diode Clipping Table Non-Linearity */
    {
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float x = ts_clamp(b_a[i], -4.0f, 4.0f);

            union { float f; unsigned u; } b;
            b.f = x;
            unsigned sgn = b.u & 0x80000000u;
            b.u = b.u & 0x7fffffffu;
            float abs_x = b.f;
            
            float p = abs_x * RAT_DTAB_SCALE;
            int idx = (int)p;
            if (idx > RAT_DTAB_N - 2) {
                idx = RAT_DTAB_N - 2;
            }
            float frac = p - (float)idx;
            float v = rat_dtab[idx] + frac * (rat_dtab[idx + 1] - rat_dtab[idx]);
            
            b.f = v;
            b.u = b.u | sgn;
            b_a[i] = b.f;
        }
    }

    /* Pass 4: Tone Filter SVF & Makeup Gain (1.67x) */
    {
        float tn1 = s->svf_tone_1;
        float tn2 = s->svf_tone_2;
        float g_tn = k->g_tone;
        float h_tn = k->h_tone;
        float g_tn_r2 = g_tn + 1.41421356f;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float x = b_a[i];

            float hp_tone = h_tn * (x - tn1 * g_tn_r2 - tn2);
            float bp_tone = hp_tone * g_tn + tn1;
            tn1 = hp_tone * g_tn + bp_tone;
            float lp_tone = bp_tone * g_tn + tn2;
            tn2 = bp_tone * g_tn + lp_tone;

            b_a[i] = lp_tone * 1.67f;
        }
        s->svf_tone_1 = tn1;
        s->svf_tone_2 = tn2;
    }

    /* 8x Downsampling: 128 -> 64 -> 32 -> 16 */
    hbi2_down_blk(&s->down3, b_a, b_b, 64);
    hbi2_down_blk(&s->down2, b_b, b_a, 32);
    hbi1_down_blk(&s->down1, b_a, out, 16);

    /* Output volume */
    {
        float vol = k->vol;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(16, 16, 16)
#endif
        for (i = 0; i < 16; ++i) {
            out[i] *= vol;
        }
    }
}

TS_INLINE void rat_block(RatState *s, const RatCoeffs *k, const float *in, float *out, int n)
{
    while (n >= 16) {
        rat_block16(s, k, in, out);
        in += 16;
        out += 16;
        n -= 16;
    }
    while (n > 0) {
        *out++ = rat_process(s, k, *in++);
        n--;
    }
}

#endif

/* muff_g1.h - CF Muff core for the G1X Four ('74 Violet Ram's Head, port of
 * Comet Flower's FuzzMobileCore / OCMuffProcessor with solver v2). Shared by
 * the pedal kernel (effects/muffx/muffx.c) and the PC bench
 * (tests/host/muff_accuracy.cpp).
 *
 * CONTRACT (the bench and the kernel depend on exactly this; do not change):
 *   typedef struct { ... } MuffState;   zero-initialised = silent start
 *   typedef struct { ... } MuffCoeffs;
 *   void  muff_coeffs(MuffCoeffs *k, float sustain, float tone, float volume);
 *         sustain, tone, volume 0..1 (Comet Flower's knob ranges; volume is
 *         the core's linear output gain). Called once per 16-sample block.
 *   float muff_process(MuffState *s, const MuffCoeffs *k, float x);
 *         one 44.1 kHz input sample (volts) -> one output sample
 */
#ifndef MUFF_G1_H
#define MUFF_G1_H

#include "ts808_core.h"         /* TS_INLINE */
#include "os_hbiir.h"           /* HbiState1, HbiState2 */
#include "muff_blob.h"

typedef struct {
    HbiState1 up1;
    HbiState1 down1;
    HbiState2 up2;
    HbiState2 down2;
    float in_hp_s;
    float in_lp_s;
    float clip1_hp_s;
    float clip2_hp_s;
    float rec_hp_s;
    float c1_vo, c1_prev_u, c1_prev_w, c1_prev_rhs, c1_prev_v, c1_prev_VI;
    float c2_vo, c2_prev_u, c2_prev_w, c2_prev_rhs, c2_prev_v, c2_prev_VI;
    float t_z1, t_z2;
} MuffState;

typedef struct {
    float vol;
    float stage1Gain;
    float drive;
    float stage3Gain;
    float clip1_hp_g;
    float t_b0, t_b1, t_b2, t_a1, t_a2;
} MuffCoeffs;

TS_INLINE float muff_lerp(const float *tab, int n, float scale, float x)
{
    float pos = x * scale;
    int i = (int)pos;
    int i_cl = i < 0 ? 0 : (i >= n - 1 ? n - 2 : i);
    float fr = pos - (float)i_cl;
    fr = fr < 0.0f ? 0.0f : (fr > 1.0f ? 1.0f : fr);
    return tab[i_cl] + (tab[i_cl + 1] - tab[i_cl]) * fr;
}

TS_INLINE void muff_coeffs(MuffCoeffs *k, float sustain, float tone, float volume)
{
    k->vol = volume;
    k->stage1Gain = 6.83911647f; /* pow(10, 16.7/20) */
    k->stage3Gain = 47.0f;       /* kRhoQ3 */

    float s = ts_clamp(sustain, 0.0f, 1.0f);
    k->drive = (0.05f + 0.95f * s) * 39.0f; /* kRhoQ2 */
    
    k->clip1_hp_g = muff_lerp(MUFF_SUS_G, 129, 128.0f, s);

    float t = ts_clamp(tone, 0.0f, 1.0f);
    float t_pos = t * 128.0f;
    int t_i = (int)t_pos;
    int t_i_cl = t_i < 0 ? 0 : (t_i > 127 ? 127 : t_i);
    float t_fr = t_pos - (float)t_i_cl;
    t_fr = t_fr < 0.0f ? 0.0f : (t_fr > 1.0f ? 1.0f : t_fr);
    const float* tone_tab = MUFF_TONE + t_i_cl * 5;
    k->t_b0 = tone_tab[0] + (tone_tab[5] - tone_tab[0]) * t_fr;
    k->t_b1 = tone_tab[1] + (tone_tab[6] - tone_tab[1]) * t_fr;
    k->t_b2 = tone_tab[2] + (tone_tab[7] - tone_tab[2]) * t_fr;
    k->t_a1 = tone_tab[3] + (tone_tab[8] - tone_tab[3]) * t_fr;
    k->t_a2 = tone_tab[4] + (tone_tab[9] - tone_tab[4]) * t_fr;
}

/* Base-rate integration equivalents of filters:
   4 Hz @ 176.4k: tan(pi * 4 / 176400) = 7.122646e-5
   1200 Hz @ 176.4k: tan(pi * 1200 / 176400) = 0.0213753
   94 Hz @ 176.4k: tan(pi * 94 / 176400) = 0.00167414
   g = tan / (1 + tan)
*/
#define MUFF_G_IN_HP 7.122139e-5f
#define MUFF_G_IN_LP 0.0209276f
#define MUFF_G_C2_HP 0.001671342f
#define MUFF_G_REC_HP 7.122139e-5f

TS_INLINE float muff_onepole_lp(float *s, float g, float x)
{
    float v = (x - *s) * g;
    float y = v + *s;
    *s = y + v;
    return y;
}

TS_INLINE void muff_clip_lookup(const float* tab, float rhsMax, float invDr,
    float vEnd, float wEnd, float VEnd, float dvdrEnd, float dwdrEnd,
    float rhs, float* v, float* w, float* VI)
{
    float ar = rhs < 0.0f ? -rhs : rhs;
    
    // Extrapolated values
    float e = ar - rhsMax;
    float e_cl = e < 0.0f ? 0.0f : e;
    
    float v_ext = vEnd + dvdrEnd * e_cl;
    float w_ext = wEnd + dwdrEnd * e_cl;
    float VI_ext = VEnd + vEnd * e_cl + 0.5f * dvdrEnd * e_cl * e_cl;
    
    // Interpolated values
    float t = ar * invDr;
    int i = (int)t;
    int i_cl = i < 0 ? 0 : (i > 254 ? 254 : i);
    
    float h = ar - (float)i_cl * (1.0f / invDr);
    float fr = h * invDr;
    const float* c0 = tab + i_cl * 3;
    const float* c1 = c0 + 3;
    float dv = c1[0] - c0[0];
    float slope = dv * invDr;
    
    float v_int = c0[0] + dv * fr;
    float w_int = c0[1] + (c1[1] - c0[1]) * fr;
    float VI_int = c0[2] + c0[0] * h + 0.5f * slope * h * h;
    
    // Select
    int is_ext = ar >= rhsMax;
    float v_abs = is_ext ? v_ext : v_int;
    float w_abs = is_ext ? w_ext : w_int;
    *VI = is_ext ? VI_ext : VI_int;
    
    *v = rhs < 0.0f ? -v_abs : v_abs;
    *w = rhs < 0.0f ? -w_abs : w_abs;
}

TS_INLINE float muff_stage(MuffState *st, const MuffCoeffs *k, float v)
{
    float in_hp = v - muff_onepole_lp(&st->in_hp_s, MUFF_G_IN_HP, v);
    float in_lp = muff_onepole_lp(&st->in_lp_s, MUFF_G_IN_LP, in_hp);
    float x = in_lp * k->stage1Gain;
    
    // Rail limiter
    float px = x * 0.5f;
    float nx = -x * 0.142857143f;
    float px_cl = ts_clamp(px, 0.0f, 8.5f);
    float p_out = 2.0f * muff_lerp(MUFF_TANH_TAB, 257, 256.0f / 8.5f, px_cl);
    float nx_cl = ts_clamp(nx, 0.0f, 8.5f);
    float n_out = -7.0f * muff_lerp(MUFF_TANH_TAB, 257, 256.0f / 8.5f, nx_cl);
    x = x >= 0.0f ? p_out : n_out;
    
    // Clip stage 1
    float c1_hp = x - muff_onepole_lp(&st->clip1_hp_s, k->clip1_hp_g, x);
    float u1 = c1_hp * k->drive;
    float rhs1 = st->c1_vo + MUFF_CLIP1_C * (u1 + st->c1_prev_u - MUFF_CLIP1_G * st->c1_vo - st->c1_prev_w);
    
    float v1, w1, VI1;
    muff_clip_lookup(MUFF_CLIP1_TAB, MUFF_CLIP1_MAX, MUFF_CLIP1_INV_DR, MUFF_CLIP1_V_END, MUFF_CLIP1_W_END,
                     MUFF_CLIP1_V_INT_END, MUFF_CLIP1_DVDR_END, MUFF_CLIP1_DWDR_END, rhs1, &v1, &w1, &VI1);
    
    float d1 = rhs1 - st->c1_prev_rhs;
    float ad1 = d1 < 0.0f ? -d1 : d1;
    float out1 = ad1 > 1.0e-4f ? (VI1 - st->c1_prev_VI) * ts_rcp(d1) : 0.5f * (v1 + st->c1_prev_v);
    st->c1_prev_rhs = rhs1; st->c1_prev_v = v1; st->c1_prev_VI = VI1;
    st->c1_prev_u = u1; st->c1_prev_w = w1; st->c1_vo = v1;
    x = out1;
    
    // Clip stage 2
    float c2_hp = x - muff_onepole_lp(&st->clip2_hp_s, MUFF_G_C2_HP, x);
    float u2 = c2_hp * k->stage3Gain;
    float rhs2 = st->c2_vo + MUFF_CLIP2_C * (u2 + st->c2_prev_u - MUFF_CLIP2_G * st->c2_vo - st->c2_prev_w);
    
    float v2, w2, VI2;
    muff_clip_lookup(MUFF_CLIP2_TAB, MUFF_CLIP2_MAX, MUFF_CLIP2_INV_DR, MUFF_CLIP2_V_END, MUFF_CLIP2_W_END,
                     MUFF_CLIP2_V_INT_END, MUFF_CLIP2_DVDR_END, MUFF_CLIP2_DWDR_END, rhs2, &v2, &w2, &VI2);
                     
    float d2 = rhs2 - st->c2_prev_rhs;
    float ad2 = d2 < 0.0f ? -d2 : d2;
    float out2 = ad2 > 1.0e-4f ? (VI2 - st->c2_prev_VI) * ts_rcp(d2) : 0.5f * (v2 + st->c2_prev_v);
    st->c2_prev_rhs = rhs2; st->c2_prev_v = v2; st->c2_prev_VI = VI2;
    st->c2_prev_u = u2; st->c2_prev_w = w2; st->c2_vo = v2;
    x = out2;
    
    // Tone biquad
    float t_out = k->t_b0 * x + st->t_z1;
    st->t_z1 = k->t_b1 * x - k->t_a1 * t_out + st->t_z2;
    st->t_z2 = k->t_b2 * x - k->t_a2 * t_out;
    x = t_out;
    
    // Recovery
    float rec_hp = x - muff_onepole_lp(&st->rec_hp_s, MUFF_G_REC_HP, x);
    return rec_hp * 4.5f * k->vol;
}

TS_INLINE float muff_process(MuffState *st, const MuffCoeffs *k, float x)
{
    float a0, b0, a1, b1, b2, b3;
    
    hbi_up1(&st->up1, x, &a0, &a1);
    
    hbi_up2(&st->up2, a0, &b0, &b1);
    hbi_up2(&st->up2, a1, &b2, &b3);
    
    b0 = muff_stage(st, k, b0);
    b1 = muff_stage(st, k, b1);
    b2 = muff_stage(st, k, b2);
    b3 = muff_stage(st, k, b3);
    
    float c0 = hbi_down2(&st->down2, b0, b1);
    float c1 = hbi_down2(&st->down2, b2, b3);
    
    return hbi_down1(&st->down1, c0, c1);
}

#endif /* MUFF_G1_H */

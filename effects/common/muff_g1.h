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
    /* prev_w slots are reserved; the algebraic recurrence no longer uses w. */
    float c1_vo, c1_prev_u, c1_prev_w, c1_prev_rhs, c1_prev_v, c1_prev_VI;
    float c2_vo, c2_prev_u, c2_prev_w, c2_prev_rhs, c2_prev_v, c2_prev_VI;
    float t_z1, t_z2;
    float input_pending; /* overlap linear input work with both nonlinear stages */
    float clip1_pending; /* one oversample of latency permits parallel clip stages */
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

/* Clip-table lookup on the solver's feedback chain, shaped for the C6745
 * (docs/C6745_DESIGN.md): the cell index is masked to 0..255 instead of
 * clamped (one AND, no compare/select), which keeps c1 = cell + 1 inside the
 * 257-cell table for any input (huge, inf or NaN rhs saturate SPTRUNC or give
 * NaN: never an out-of-range read); the extrapolated value is chosen on the
 * same t (t >= 256, the table's span 256 * dr = rhsMax), so every
 * interpolated result comes from a true cell; the fraction is t - cell
 * (one multiply less than via h). Cells: {v, w, VI}. */
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
    int i_cl = (int)t & 0xFF;
    float fr = t - (float)i_cl;
    float h = fr * (1.0f / invDr);
    const float* c0 = tab + i_cl * 3;
    const float* c1 = c0 + 3;
    float dv = c1[0] - c0[0];
    float slope = dv * invDr;

    float v_int = c0[0] + dv * fr;
    float w_int = c0[1] + (c1[1] - c0[1]) * fr;
    float VI_int = c0[2] + c0[0] * h + 0.5f * slope * h * h;

    // Select
    int is_ext = t >= 256.0f;
    float v_abs = is_ext ? v_ext : v_int;
    float w_abs = is_ext ? w_ext : w_int;
    *VI = is_ext ? VI_ext : VI_int;

    *v = rhs < 0.0f ? -v_abs : v_abs;
    *w = rhs < 0.0f ? -w_abs : w_abs;
}

/* Retimed feed-forward chain: input at n, clip 1 at n-1, clip 2 at n-2.
 * Two oversamples (11.34 us) of added latency break the serial dependence
 * between stages while preserving each stage's own feedback recurrence.
 * Pipeline state persists across the four-sample groups and block boundaries.
 *
 * The implicit solution obeys v*(1+c*g)+c*w=rhs. Substituting this into
 * next_rhs = v+c*(u+prev_u-g*v-w) gives 2*v-rhs+c*(u+prev_u).
 * Thus the w lookup/store is unnecessary; its unused outputs are eliminated
 * by inlining, and the original blob layout is kept intact.
 */
/* The stage in parts that take each state value by its own pointer: the
 * per-sample path (muff_stage) passes the MuffState fields, the block path
 * (muff_block) passes scalar locals the compiler keeps in registers. One
 * definition of the arithmetic, so both paths are bit-identical. */

/* input filters, rail tanh, clip-1 high-pass and drive */
TS_INLINE float muff_in(float *hp_s, float *lp_s, float *c1hp_s, const MuffCoeffs *k, float v)
{
    float in_hp = v - muff_onepole_lp(hp_s, MUFF_G_IN_HP, v);
    float in_lp = muff_onepole_lp(lp_s, MUFF_G_IN_LP, in_hp);
    float x = in_lp * k->stage1Gain;

    /* Choose the rail scale before the single tanh lookup. */
    float rail = x >= 0.0f ? 2.0f : -7.0f;
    float invrail = x >= 0.0f ? 0.5f : -0.142857143f;
    float pos = ts_clamp(x * invrail, 0.0f, 8.5f) * (256.0f / 8.5f);
    int ri = (int)pos;
    ri = ri > 255 ? 255 : ri;
    float rf = pos - (float)ri;
    x = rail * (MUFF_TANH_TAB[ri] + (MUFF_TANH_TAB[ri+1] - MUFF_TANH_TAB[ri]) * rf);

    // Clip stage 1 high-pass
    float c1_hp = x - muff_onepole_lp(c1hp_s, k->clip1_hp_g, x);
    return c1_hp * k->drive;
}

/* one clip stage's implicit solve (stage N = 1 or 2 selects its table and
 * constants); u = this oversample's input */
#define MUFF_CLIP_STEP(N, vo, prev_u, prev_rhs, prev_v, prev_VI, u, out) do {                  \
    /* only vo is late on the chain: 2 vo + (everything else, ready earlier) */                 \
    float rhs_ = (*(vo) + *(vo)) + (MUFF_CLIP##N##_C * ((u) + *(prev_u)) - *(prev_rhs));       \
    float v_, w_, VI_;                                                                          \
    muff_clip_lookup(MUFF_CLIP##N##_TAB, MUFF_CLIP##N##_MAX, MUFF_CLIP##N##_INV_DR,             \
                     MUFF_CLIP##N##_V_END, MUFF_CLIP##N##_W_END, MUFF_CLIP##N##_V_INT_END,      \
                     MUFF_CLIP##N##_DVDR_END, MUFF_CLIP##N##_DWDR_END, rhs_, &v_, &w_, &VI_);   \
    float d_ = rhs_ - *(prev_rhs);                                                              \
    float ad_ = d_ < 0.0f ? -d_ : d_;                                                           \
    (out) = ad_ > 1.0e-4f ? (VI_ - *(prev_VI)) * ts_rcp(d_) : 0.5f * (v_ + *(prev_v));          \
    *(prev_rhs) = rhs_; *(prev_v) = v_; *(prev_VI) = VI_;                                       \
    *(prev_u) = (u); *(vo) = v_;                                                                \
} while (0)

/* tone biquad and recovery */
TS_INLINE float muff_out(float *z1, float *z2, float *rec_s, const MuffCoeffs *k, float x)
{
    float t_out = k->t_b0 * x + *z1;
    *z1 = k->t_b1 * x - k->t_a1 * t_out + *z2;
    *z2 = k->t_b2 * x - k->t_a2 * t_out;
    x = t_out;

    float rec_hp = x - muff_onepole_lp(rec_s, MUFF_G_REC_HP, x);
    return rec_hp * 4.5f * k->vol;
}

TS_INLINE float muff_stage(MuffState *st, const MuffCoeffs *k, float v)
{
    float d = muff_in(&st->in_hp_s, &st->in_lp_s, &st->clip1_hp_s, k, v);
    float u1 = st->input_pending, out1, x, u2, out2;
    st->input_pending = d;
    MUFF_CLIP_STEP(1, &st->c1_vo, &st->c1_prev_u, &st->c1_prev_rhs, &st->c1_prev_v, &st->c1_prev_VI, u1, out1);
    x = st->clip1_pending;
    st->clip1_pending = out1;

    // Clip stage 2
    u2 = (x - muff_onepole_lp(&st->clip2_hp_s, MUFF_G_C2_HP, x)) * k->stage3Gain;
    MUFF_CLIP_STEP(2, &st->c2_vo, &st->c2_prev_u, &st->c2_prev_rhs, &st->c2_prev_v, &st->c2_prev_VI, u2, out2);

    return muff_out(&st->t_z1, &st->t_z2, &st->rec_hp_s, k, out2);
}

TS_INLINE float muff_process(MuffState *st, const MuffCoeffs *k, float x)
{
    float a0, b0, a1, b1, b2, b3;
    
    hbi_up1(&st->up1, x, &a0, &a1);
    
    hbi_up2(&st->up2, a0, &b0, &b1);
    hbi_up2(&st->up2, a1, &b2, &b3);
    
    float y[4];
    int i;
    y[0] = b0; y[1] = b1; y[2] = b2; y[3] = b3;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(4, 4, 4)
#pragma UNROLL(1)
#endif
    for (i = 0; i < 4; ++i)
        y[i] = muff_stage(st, k, y[i]);
    b0 = y[0]; b1 = y[1]; b2 = y[2]; b3 = y[3];
    
    float c0 = hbi_down2(&st->down2, b0, b1);
    float c1 = hbi_down2(&st->down2, b2, b3);
    
    return hbi_down1(&st->down1, c0, c1);
}

/* Block form for the C6745 (docs/C6745_DESIGN.md): the same arithmetic as
 * muff_process over n input samples, bit-identical, but stage-major. The
 * oversamplers run as block passes and the stage as three passes over the
 * 4n oversamples, every state value in its own scalar local. With the state
 * behind st, the compiler had to assume its stores may alias the blob
 * tables, chaining each oversample to the previous one through memory (dep
 * bound 116, not pipelined); a struct copy stayed in memory too, and paired
 * loads/stores of neighbouring fields merged independent filters into one
 * chain. n <= MUFF_BLK_MAX. */
#define MUFF_BLK_MAX 16
TS_INLINE void muff_block(MuffState *st, const MuffCoeffs *k, const float *in, float *out, int n)
{
    float b1[2 * MUFF_BLK_MAX], b2[4 * MUFF_BLK_MAX];
    int i;

    hbi1_up_blk(&st->up1, in, b1, n);
    hbi2_up_blk(&st->up2, b1, b2, 2 * n);
    {   /* pass 1: input part */
        float hp = st->in_hp_s, lp = st->in_lp_s, c1hp = st->clip1_hp_s;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(4, 4 * MUFF_BLK_MAX, 4)
#pragma UNROLL(1)
#endif
        for (i = 0; i < 4 * n; ++i)
            b2[i] = muff_in(&hp, &lp, &c1hp, k, b2[i]);
        st->in_hp_s = hp; st->in_lp_s = lp; st->clip1_hp_s = c1hp;
    }
    {   /* pass 2: clip stage 1 (its output delayed one oversample, as in muff_stage) */
        float pend = st->input_pending, c1pend = st->clip1_pending;
        float vo1 = st->c1_vo, pu1 = st->c1_prev_u, pr1 = st->c1_prev_rhs, pv1 = st->c1_prev_v, pV1 = st->c1_prev_VI;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(4, 4 * MUFF_BLK_MAX, 4)
#pragma UNROLL(1)
#endif
        for (i = 0; i < 4 * n; ++i) {
            float u1 = pend, out1;
            pend = b2[i];
            MUFF_CLIP_STEP(1, &vo1, &pu1, &pr1, &pv1, &pV1, u1, out1);
            b2[i] = c1pend;
            c1pend = out1;
        }
        st->input_pending = pend; st->clip1_pending = c1pend;
        st->c1_vo = vo1; st->c1_prev_u = pu1; st->c1_prev_rhs = pr1; st->c1_prev_v = pv1; st->c1_prev_VI = pV1;
    }
    {   /* pass 3: clip stage 2 */
        float c2hp = st->clip2_hp_s, g3 = k->stage3Gain;
        float vo2 = st->c2_vo, pu2 = st->c2_prev_u, pr2 = st->c2_prev_rhs, pv2 = st->c2_prev_v, pV2 = st->c2_prev_VI;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(4, 4 * MUFF_BLK_MAX, 4)
#pragma UNROLL(1)
#endif
        for (i = 0; i < 4 * n; ++i) {
            float x = b2[i], u2, out2;
            u2 = (x - muff_onepole_lp(&c2hp, MUFF_G_C2_HP, x)) * g3;
            MUFF_CLIP_STEP(2, &vo2, &pu2, &pr2, &pv2, &pV2, u2, out2);
            b2[i] = out2;
        }
        st->clip2_hp_s = c2hp;
        st->c2_vo = vo2; st->c2_prev_u = pu2; st->c2_prev_rhs = pr2; st->c2_prev_v = pv2; st->c2_prev_VI = pV2;
    }
    {   /* pass 4: tone and recovery */
        float z1 = st->t_z1, z2 = st->t_z2, rec = st->rec_hp_s;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(4, 4 * MUFF_BLK_MAX, 4)
#pragma UNROLL(1)
#endif
        for (i = 0; i < 4 * n; ++i)
            b2[i] = muff_out(&z1, &z2, &rec, k, b2[i]);
        st->t_z1 = z1; st->t_z2 = z2; st->rec_hp_s = rec;
    }
    hbi2_down_blk(&st->down2, b2, b1, 2 * n);
    hbi1_down_blk(&st->down1, b1, out, n);
}

#endif /* MUFF_G1_H */

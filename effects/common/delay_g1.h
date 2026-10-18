/* delay_g1.h - CF Delay core for the G1X Four: a port of Comet Flower's
 * DelayMobileCore (VirtualPedalBoardEngine/Source/MobileDsp/DelayMobileCore.h,
 * MobilePrimitives.h). Shared by the pedal kernel (effects/delayx) and the PC
 * bench (tests/host/delay_accuracy.cpp), which runs the original core as the
 * reference.
 *
 * Same as the original, step for step: 300 ms tape-style glide of the read
 * head toward the Time setting (no swoop on load: the first block snaps),
 * main tap + a second tap 20 ms later for stereo width (linear interpolation),
 * repeats darkened by a fixed 3.5 kHz TPT one-pole and saturated by tanh with
 * first-order ADAA on the write node, 2 s maximum, power-of-two line (131072
 * floats) that is never cleared: `written` counts pushes since the reset and
 * older cells read as zero, so a load costs nothing.
 *
 * One change: the original's ADAA keeps its antiderivative in double (float
 * crackles). The C674x is slow at double, so the average of tanh over a step
 * is computed in float without cancellation: atanh(tanh(mid) tanh(h)) / h for
 * steps under 0.25 (the identity behind CF Watt's hw_mean_tanh), the plain
 * ln cosh difference above that (no cancellation at those steps). tanh / ln cosh
 * from the CF CE-2 table (ce2_sat_table.h: cubic Hermite on [0, 8]).
 *
 * CONTRACT:
 *   DelayState  (in the slot work buffer, ~512 KB) all-zero = a reset line
 *   void  delay_coeffs(DelayCoeffs *k, float time_ms, float feedback, float mix);
 *   void  delay_snap(DelayState *s, const DelayCoeffs *k);   first block after a reset
 *   void  delay_process(DelayState *s, const DelayCoeffs *k, float x, float *l, float *r);
 */
#ifndef DELAY_G1_H
#define DELAY_G1_H

#include <stdint.h>
#include "ce2_g1.h"             /* ce2_ln_cosh, ce2_tanh, TS_INLINE, ts_clamp */

#define DL_FS          44100.0f
#define DL_N           131072u                 /* >= 2 s + 4, power of two */
#define DL_MASK        (DL_N - 1u)
#define DL_MAX         88200.0f                /* 2 s */
#define DL_SPREAD      882.0f                  /* 20 ms second tap */
#define DL_LP_G        0.20295308f             /* TPT one-pole, 3.5 kHz at 44.1 kHz: t/(1+t), t = tan(pi fc/fs) */
#define DL_GLIDE       7.557869e-05f           /* 1.0f - expf(-1 / (0.300 s * 44100)) in float, as the original computes it */

typedef struct {
    float buf[DL_N];
    uint32_t wp, written;
    float cur;                  /* read head, samples */
    float lp;                   /* feedback tone state */
    float x1;                   /* ADAA: previous input to the saturator */
} DelayState;

typedef struct {
    float target, fb, wet, dry;
} DelayCoeffs;

TS_INLINE void delay_coeffs(DelayCoeffs *k, float time_ms, float feedback, float mix)
{
    float t = time_ms * (DL_FS / 1000.0f);
    float fb = ts_clamp(feedback, 0.0f, 0.95f);
    float m = ts_clamp(mix, 0.0f, 1.0f);
    k->target = ts_clamp(t, 1.0f, DL_MAX - 2.0f);
    k->fb = fb;
    k->wet = m;
    k->dry = 1.0f - m;
}

TS_INLINE void delay_snap(DelayState *s, const DelayCoeffs *k)
{
    s->cur = k->target;
}

/* tanh: odd polynomial below 0.25 (relative accuracy for small signals), else the CE-2 table */
TS_INLINE float dl_tanh(float m)
{
    float a = m < 0.0f ? -m : m, m2 = m * m, m4 = m2 * m2;
    float p = m * ((1.0f - m2 * (1.0f / 3)) + m4 * ((2.0f / 15 - m2 * (17.0f / 315)) + m4 * (62.0f / 2835)));
    return a < 0.25f ? p : ce2_tanh(m);
}

/* mean of tanh over [x1, x] = (ln cosh x - ln cosh x1) / (x - x1), float-safe */
TS_INLINE float dl_mean_tanh(float x, float x1)
{
    float d = x - x1, ad = d < 0.0f ? -d : d;
    float h = 0.5f * d, h2 = h * h;
    /* small step: atanh(tanh(c) tanh(h)) / h, series in z (|z| < tanh(1/8)) */
    float tc = dl_tanh(x1 + h);
    float thh = 1.0f - h2 * (1.0f / 3 - h2 * (2.0f / 15 - h2 * (17.0f / 315 - h2 * (62.0f / 2835))));
    float z = tc * h * thh, z2 = z * z, z4 = z2 * z2;
    float small = tc * thh * ((1.0f + z2 * (1.0f / 3)) + z4 * (1.0f / 5 + z2 * (1.0f / 7)));
    float big = (ce2_ln_cosh(x) - ce2_ln_cosh(x1)) * ts_rcp(ad < 0.25f ? 1.0f : d);
    return ad < 0.25f ? small : big;
}

TS_INLINE float dl_read(const DelayState *s, float d)
{
    int di = (int)d;
    float fr = d - (float)di;
    uint32_t i0 = (s->wp - (uint32_t)di) & DL_MASK;
    uint32_t i1 = (s->wp - (uint32_t)di - 1u) & DL_MASK;
    float a = (uint32_t)di < s->written ? s->buf[i0] : 0.0f;
    float b = (uint32_t)di + 1u < s->written ? s->buf[i1] : 0.0f;
    return a + (b - a) * fr;
}

TS_INLINE void delay_process(DelayState *s, const DelayCoeffs *k, float x, float *outL, float *outR)
{
    float main_, wide, rd, v, y, w;

    s->cur += DL_GLIDE * (k->target - s->cur);
    main_ = dl_read(s, s->cur);
    rd = s->cur + DL_SPREAD;
    rd = rd > DL_MAX - 2.0f ? DL_MAX - 2.0f : rd;
    wide = dl_read(s, rd);

    v = (main_ - s->lp) * DL_LP_G;          /* OnePoleTPT::processLP */
    y = v + s->lp;
    s->lp = y + v;

    w = x + y * k->fb;                      /* write node: ADAA tanh */
    s->wp = (s->wp + 1u) & DL_MASK;
    s->buf[s->wp] = dl_mean_tanh(w, s->x1);
    s->x1 = w;
    s->written += s->written <= DL_MASK;

    *outL = x * k->dry + main_ * k->wet;
    *outR = x * k->dry + wide * k->wet;
}

#endif /* DELAY_G1_H */

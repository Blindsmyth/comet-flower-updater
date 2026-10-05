/* ts808_exact.h - circuit-exact TS808 for the Zoom G1 Four ("Green 808X").
 *
 * The clipping stage is solved from the component physics every sample at
 * 8x oversampling (352.8 kHz):
 *   ground leg R4 + C3 (720 Hz)          trapezoidal companion
 *   feedback: Rf || C4 (51 pF) || D1/D2   v(1/Rf + 2C4/T) + 2 Is sinh(v/nVt) = i_g + hist
 *   Vout = Vin + v
 * with Rf = R6 + P1 (51k + 500k * wiper^2, audio taper) and 1N4148/MA150
 * silicon (Is 2.52 nA, n 1.752). Three Newton steps per sample, warm-started.
 * Around it: C1/R2 and C2/R5 input couplings (15.6 / 15.9 Hz), R7/C5 723 Hz
 * pole, the pole-zero tone network (from Comet Flower's DriveMobileCore,
 * computed at 8x), 5 Hz output coupling.
 *
 * Scored against a 32x double-precision reference of the same circuit
 * (tests/host/ts808_accuracy.cpp): worst harmonic error 1.6 dB (passband
 * droop of the first half-band near 20 kHz), <= 0.03 dB below 1 kHz,
 * aliasing <= -55 dB.
 *
 * Oversampling: 2x half-band FIR with 6 tap pairs (as Oversampler2x), then two
 * 2x stages with 3 pairs (the transition band is wide at 4x/8x).
 * State: 75 floats = 300 bytes, all zero = reset.
 */
#ifndef TS808_EXACT_H
#define TS808_EXACT_H

#include "ts808_sd.h"

#ifndef SD_ITERS_EXACT
#define SD_ITERS_EXACT 3
#endif

#define X_KC3            30.153905868530273f
#define X_INV_R4KC3      0.00021140961325727403f
#define X_GC4            3.5985598515253514e-05f
#define X_G_POST8        0.006397031247615814f
#define X_TONE_K8        705600.0f
#define X_TONE_INV_A0_8  0.028462735936045647f
#define X_TONE_A1_8      (-0.9430745244026184f)
#define X_G_IN1          0.0011103219585493207f
#define X_G_IN2          0.0011325032683089375f

#define OS3_C0  0.28437113761901855f
#define OS3_C1 -0.03608988597989082f
#define OS3_C2  0.0017187680350616574f

typedef struct { float xh[12], eh[7], oh[13]; } TsxHB6;   /* 32 floats */
typedef struct { float xh[6], eh[4], oh[7]; } TsxHB3;     /* 17 floats */

typedef struct {
    TsxHB6 s1;
    TsxHB3 s2, s3;
    float hp1, hp2;                 /* input coupling one-poles */
    float vc3, igp, v, ic4;         /* clipping stage: C3 voltage, i_g, diode v, C4 current */
    float spost, ztone, sdc;        /* R7/C5, tone, output coupling */
} TsxState;                         /* 75 floats = 300 B */

typedef struct { float rf, a, gc4rf, lin, b0, b1, gain; } TsxCoeffs;

TS_INLINE void tsx_coeffs(TsxCoeffs *k, float drive, float tone, float gain)
{
    float d = ts_clamp(drive, 0.0f, 10.0f) * 0.1f;
    float t = ts_clamp(tone, 0.0f, 1.0f);
    float fz, kwz;
    k->rf = 51000.0f + d * d * 500000.0f;
    k->a = 2.0f * SD_IS * k->rf;
    k->gc4rf = X_GC4 * k->rf;
    k->lin = 1.0f + k->gc4rf;
    fz = 723.0f * ts_exp_pos((1.0f - t) * TS_LN_RATIO);
    kwz = X_TONE_K8 * ts_rcp(6.2831853f * fz);
    k->b0 = (1.0f + kwz) * X_TONE_INV_A0_8;
    k->b1 = (1.0f - kwz) * X_TONE_INV_A0_8;
    k->gain = gain;
}

TS_INLINE void tsx_up6(TsxHB6 *h, float x, float *a, float *b)
{
    int i;
    for (i = 11; i > 0; --i) h->xh[i] = h->xh[i - 1];
    h->xh[0] = x;
    *a = h->xh[6];
    *b = 2.0f * (OS_C0 * (h->xh[6] + h->xh[5]) + OS_C1 * (h->xh[7] + h->xh[4])
               + OS_C2 * (h->xh[8] + h->xh[3]) + OS_C3 * (h->xh[9] + h->xh[2])
               + OS_C4 * (h->xh[10] + h->xh[1]) + OS_C5 * (h->xh[11] + h->xh[0]));
}

TS_INLINE float tsx_down6(TsxHB6 *h, float a, float b)
{
    int i;
    for (i = 6; i > 0; --i) h->eh[i] = h->eh[i - 1];
    h->eh[0] = a;
    for (i = 12; i > 0; --i) h->oh[i] = h->oh[i - 1];
    h->oh[0] = b;
    return 0.5f * h->eh[6]
        + OS_C0 * (h->oh[7] + h->oh[6]) + OS_C1 * (h->oh[8] + h->oh[5])
        + OS_C2 * (h->oh[9] + h->oh[4]) + OS_C3 * (h->oh[10] + h->oh[3])
        + OS_C4 * (h->oh[11] + h->oh[2]) + OS_C5 * (h->oh[12] + h->oh[1]);
}

TS_INLINE void tsx_up3(TsxHB3 *h, float x, float *a, float *b)
{
    int i;
    for (i = 5; i > 0; --i) h->xh[i] = h->xh[i - 1];
    h->xh[0] = x;
    *a = h->xh[3];
    *b = 2.0f * (OS3_C0 * (h->xh[3] + h->xh[2]) + OS3_C1 * (h->xh[4] + h->xh[1])
               + OS3_C2 * (h->xh[5] + h->xh[0]));
}

TS_INLINE float tsx_down3(TsxHB3 *h, float a, float b)
{
    int i;
    for (i = 3; i > 0; --i) h->eh[i] = h->eh[i - 1];
    h->eh[0] = a;
    for (i = 6; i > 0; --i) h->oh[i] = h->oh[i - 1];
    h->oh[0] = b;
    return 0.5f * h->eh[3]
        + OS3_C0 * (h->oh[4] + h->oh[3]) + OS3_C1 * (h->oh[5] + h->oh[2])
        + OS3_C2 * (h->oh[6] + h->oh[1]);
}

/* one 8x sample through the circuit */
TS_INLINE float tsx_stage(TsxState *s, const TsxCoeffs *k, float x)
{
    float ig = (x - s->vc3 - X_KC3 * s->igp) * X_INV_R4KC3;
    float rhs, vn, y, o;
    int it;
    s->vc3 += X_KC3 * (ig + s->igp);
    s->igp = ig;
    rhs = k->rf * (ig + s->ic4) + k->gc4rf * s->v;
    vn = s->v;
    for (it = 0; it < SD_ITERS_EXACT; ++it) {
        float e = sd_expf(vn * SD_INVNVT), ei = sd_expf(-vn * SD_INVNVT);
        float f = k->lin * vn + k->a * 0.5f * (e - ei) - rhs;
        float df = k->lin + k->a * SD_INVNVT * 0.5f * (e + ei);
        float st = f * ts_rcp(df);
        if (st > 0.1f) st = 0.1f;
        if (st < -0.1f) st = -0.1f;
        vn -= st;
    }
    s->ic4 = X_GC4 * (vn - s->v) - s->ic4;
    s->v = vn;
    y = ts_onepole_lp(&s->spost, X_G_POST8, x + vn);
    o = k->b0 * y + s->ztone;
    s->ztone = k->b1 * y - X_TONE_A1_8 * o;
    return o;
}

TS_INLINE float tsx_process(TsxState *s, const TsxCoeffs *k, float x)
{
    float a1, b1, a2, b2, c2, d2, y4[4], y8[8];
    int i;
    x = x - ts_onepole_lp(&s->hp1, X_G_IN1, x);
    x = x - ts_onepole_lp(&s->hp2, X_G_IN2, x);

    tsx_up6(&s->s1, x, &a1, &b1);
    tsx_up3(&s->s2, a1, &a2, &b2);
    tsx_up3(&s->s2, b1, &c2, &d2);
    {   /* 4x stream a2 b2 c2 d2 -> 8x */
        float in4[4];
        in4[0] = a2; in4[1] = b2; in4[2] = c2; in4[3] = d2;
        for (i = 0; i < 4; ++i)
            tsx_up3(&s->s3, in4[i], &y8[2 * i], &y8[2 * i + 1]);
    }
    for (i = 0; i < 8; ++i)
        y8[i] = tsx_stage(s, k, y8[i]);
    for (i = 0; i < 4; ++i)
        y4[i] = tsx_down3(&s->s3, y8[2 * i], y8[2 * i + 1]);
    a1 = tsx_down3(&s->s2, y4[0], y4[1]);
    b1 = tsx_down3(&s->s2, y4[2], y4[3]);
    x = tsx_down6(&s->s1, a1, b1);

    x = x - ts_onepole_lp(&s->sdc, TS_G_DC, x);
    return x * k->gain;
}

#endif /* TS808_EXACT_H */

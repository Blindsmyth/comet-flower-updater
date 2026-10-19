/* ts808_exact.h - circuit-exact TS808 for the Zoom G1 Four ("Green 808X").
 *
 * The clipping stage is solved from the component physics every sample at
 * 8x oversampling (352.8 kHz):
 *   ground leg R4 + C3 (720 Hz)          trapezoidal companion
 *   feedback: Rf || C4 (51 pF) || D1/D2   v(1/Rf + 2C4/T) + 2 Is sinh(v/nVt) = i_g + hist
 *   Vout = Vin + v
 * with Rf = R6 + P1 (51k + 500k * wiper^2, audio taper) and 1N4148/MA150
 * silicon (Is 2.52 nA, n 1.752). The diode equation is solved by table:
 * normalised to c*u + sinh(u) = r (u = v/nVt, c set by Drive), u(c, r) is
 * precomputed in double (tools/gen_diode_table.py -> ts808_dtab.h, 27 KB) as
 * cubic Hermite segments on a pseudo-log |r| grid, blended across four c rows.
 * Table error <= 4e-6 V; no iteration, so the per-sample dependency chain is
 * short. (The first 808X ran three warm-started Newton steps: ~74k cycles per
 * block against ~15k now, and it was less converged at high drive.)
 * Around it: C1/R2 and C2/R5 input couplings (15.6 / 15.9 Hz), R7/C5 723 Hz
 * pole, the pole-zero tone network (from Comet Flower's DriveMobileCore,
 * computed at 8x), 5 Hz output coupling.
 *
 * Scored against a 32x double-precision reference of the same circuit
 * (tests/host/ts808_accuracy.cpp): worst harmonic error 1.75 dB (passband
 * droop of the first half-band near 20 kHz), <= 0.04 dB below 1 kHz,
 * aliasing <= -58 dB.
 *
 * Oversampling: 2x half-band FIR with 6 tap pairs (as Oversampler2x), then two
 * 2x stages with 3 pairs (the transition band is wide at 4x/8x).
 * State: 75 floats = 300 bytes, all zero = reset.
 */
#ifndef TS808_EXACT_H
#define TS808_EXACT_H

#include "ts808_sd.h"
#include "ts808_dtab.h"
#include "os_halfband.h"

/* TSX_NEWTON 1 adds one exact Newton step after the table (bench check). */
#ifndef TSX_NEWTON
#define TSX_NEWTON 0
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

/* Normalised clipping stage. With u = v/nVt, Rf || C4 || diodes is
 *   c*u + sinh(u) = r,   c = X_C_SCALE * (1/Rf + gC4),
 *   r = X_R_IG * (i_g + i_C4,hist) + X_ALPHA * u_prev,
 * and the C4 companion history folds into one float q:
 *   r_n = (X_R_IG * i_g,n - q) + 2 X_ALPHA u_(n-1),   q' = 2 X_ALPHA u_(n-1) - q. */
#define X_R_IG    (1.0f / (2.0f * SD_IS))
#define X_ALPHA   (X_GC4 * SD_NVT / (2.0f * SD_IS))
#define X_C_SCALE (SD_NVT / (2.0f * SD_IS))

typedef struct {
    TsxHB6 s1;
    TsxHB3 s2, s3;
    float hp1, hp2;                 /* input coupling one-poles */
    float vc3, igp, u, q;           /* clipping stage: C3 voltage, i_g, diode v/nVt, C4 history */
    float spost, ztone, sdc;        /* R7/C5, tone, output coupling */
} TsxState;                         /* 75 floats = 300 B */

typedef struct {
    float b0, b1, gain;
    float c, inv_c1;                /* diode solve: c, 1/(c+1) */
    float w0, w1, w2, w3;           /* cubic Lagrange weights of the four c rows */
    const float *dt;                /* first of the four table rows */
} TsxCoeffs;

TS_INLINE void tsx_coeffs(TsxCoeffs *k, float drive, float tone, float gain)
{
    float d = ts_clamp(drive, 0.0f, 10.0f) * 0.1f;
    float t = ts_clamp(tone, 0.0f, 1.0f);
    float fz, kwz, rf, fc, x;
    int j0;
    rf = 51000.0f + d * d * 500000.0f;
    k->c = X_C_SCALE * (ts_rcp(rf) + X_GC4);
    k->inv_c1 = ts_rcp(k->c + 1.0f);
    fc = (k->c - TSX_DT_CMIN) * ((TSX_DT_NC - 1) / (TSX_DT_CMAX - TSX_DT_CMIN));
    fc = ts_clamp(fc, 0.0f, (float)(TSX_DT_NC - 1));
    j0 = (int)fc - 1;
    if (j0 < 0) j0 = 0;
    if (j0 > TSX_DT_NC - 4) j0 = TSX_DT_NC - 4;
    x = fc - (float)j0;                         /* position among rows j0..j0+3 */
    k->w0 = -(x - 1.0f) * (x - 2.0f) * (x - 3.0f) * (1.0f / 6.0f);
    k->w1 = x * (x - 2.0f) * (x - 3.0f) * 0.5f;
    k->w2 = -x * (x - 1.0f) * (x - 3.0f) * 0.5f;
    k->w3 = x * (x - 1.0f) * (x - 2.0f) * (1.0f / 6.0f);
    k->dt = tsx_dtab + j0 * (TSX_DT_NSEG * 4);
    fz = 723.0f * ts_exp_pos((1.0f - t) * TS_LN_RATIO);
    kwz = X_TONE_K8 * ts_rcp(6.2831853f * fz);
    k->b0 = (1.0f + kwz) * X_TONE_INV_A0_8;
    k->b1 = (1.0f - kwz) * X_TONE_INV_A0_8;
    k->gain = gain;
}

/* u(c, r) from the table: pseudo-log segment and position t from the float
 * bits of |r|, the four c rows blended, cubic in t (Estrin). Odd in r. */
TS_INLINE float tsx_dtable(const TsxCoeffs *k, float r)
{
    union { float f; unsigned u; } b;
    const unsigned top = ((127u + TSX_DT_HI) << 23) - 1u;
    const int sh = 23 - TSX_DT_LOG2K;
    const int S = TSX_DT_NSEG * 4;
    unsigned sgn, m, low;
    int seg;
    const float *p;
    float t, t2, c0, c1, c2, c3, u, ar;
    b.f = r;
    sgn = b.u & 0x80000000u;
    m = b.u & 0x7fffffffu;
    b.u = m;
    ar = b.f;
    if (m > top) m = top;
    seg = ((int)m - (int)((127u + TSX_DT_LO) << 23)) >> sh;
    t = (float)(int)(m & ((1u << sh) - 1u)) * (1.0f / (float)(1u << sh));
    low = (unsigned)(seg >> 31);               /* all ones below 2^LO */
    seg &= ~(int)low;
    p = k->dt + seg * 4;
    c0 = (k->w0 * p[0] + k->w1 * p[S + 0]) + (k->w2 * p[2 * S + 0] + k->w3 * p[3 * S + 0]);
    c1 = (k->w0 * p[1] + k->w1 * p[S + 1]) + (k->w2 * p[2 * S + 1] + k->w3 * p[3 * S + 1]);
    c2 = (k->w0 * p[2] + k->w1 * p[S + 2]) + (k->w2 * p[2 * S + 2] + k->w3 * p[3 * S + 2]);
    c3 = (k->w0 * p[3] + k->w1 * p[S + 3]) + (k->w2 * p[2 * S + 3] + k->w3 * p[3 * S + 3]);
    t2 = t * t;
    u = (c0 + t * c1) + t2 * (c2 + t * c3);
    /* below 2^LO the diodes are off: u = r/(c+1). Bit select, so the loop
     * stays branch-free and software-pipelines. */
    b.f = ar * k->inv_c1;
    m = b.u & low;
    b.f = u;
    b.u = (b.u & ~low) | m | sgn;
    return b.f;
}

/* one 8x sample through the circuit */
TS_INLINE float tsx_stage(TsxState *s, const TsxCoeffs *k, float x)
{
    float ig = (x - s->vc3 - X_KC3 * s->igp) * X_INV_R4KC3;
    float hu = (2.0f * X_ALPHA) * s->u;
    float r, u, y, o;
    s->vc3 += X_KC3 * (ig + s->igp);
    s->igp = ig;
    r = (X_R_IG * ig - s->q) + hu;
    s->q = hu - s->q;
    u = tsx_dtable(k, r);
#if TSX_NEWTON
    {
        float e = sd_expf(u), ei = sd_expf(-u);
        u -= (k->c * u + 0.5f * (e - ei) - r) * ts_rcp(k->c + 0.5f * (e + ei));
    }
#endif
    s->u = u;
    y = ts_onepole_lp(&s->spost, X_G_POST8, x + SD_NVT * u);
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

TS_INLINE void tsx_block16(TsxState *s, const TsxCoeffs *k, const float *in, float *out)
{
    float b_a[128];
    float b_b[128];
    int i;

    /* Step 0: Input HP filters (16 samples) */
    {
        float hp1 = s->hp1, hp2 = s->hp2;
#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(16, 16, 16)
#endif
        for (i = 0; i < 16; ++i) {
            float x = in[i];
            float v1 = (x - hp1) * X_G_IN1;
            float lp1 = v1 + hp1;
            hp1 = lp1 + v1;
            x = x - lp1;

            float v2 = (x - hp2) * X_G_IN2;
            float lp2 = v2 + hp2;
            hp2 = lp2 + v2;
            b_a[i] = x - lp2;
        }
        s->hp1 = hp1;
        s->hp2 = hp2;
    }

    /* Step 1: 8x Upsampling: 16 -> 32 -> 64 -> 128 */
    tsx_up6_blk(&s->s1, b_a, b_b, 16);  /* 16 -> 32 in b_b */
    tsx_up3_blk(&s->s2, b_b, b_a, 32);  /* 32 -> 64 in b_a */
    tsx_up3_blk(&s->s3, b_a, b_b, 64);  /* 64 -> 128 in b_b */

    /* Step 2: Diode Clipping Stage (128 samples, Pass 1) */
    {
        float vc3 = s->vc3;
        float igp = s->igp;
        float q   = s->q;
        float u   = s->u;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float x = b_b[i];
            float ig = (x - vc3 - X_KC3 * igp) * X_INV_R4KC3;
            float hu = (2.0f * X_ALPHA) * u;
            float r;
            vc3 += X_KC3 * (ig + igp);
            igp = ig;
            r = (X_R_IG * ig - q) + hu;
            q = hu - q;
            u = tsx_dtable(k, r);
#if TSX_NEWTON
            {
                float e = sd_expf(u), ei = sd_expf(-u);
                u -= (k->c * u + 0.5f * (e - ei) - r) * ts_rcp(k->c + 0.5f * (e + ei));
            }
#endif
            b_a[i] = x + SD_NVT * u;
        }
        s->vc3 = vc3;
        s->igp = igp;
        s->q = q;
        s->u = u;
    }

    /* Step 3: Post Filter & Tone Network (128 samples, Pass 2) */
    {
        float spost = s->spost;
        float ztone = s->ztone;
        float b0 = k->b0, b1 = k->b1;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(128, 128, 16)
#endif
        for (i = 0; i < 128; ++i) {
            float in_val = b_a[i];
            float v = (in_val - spost) * X_G_POST8;
            float y = v + spost;
            spost = y + v;

            float o = b0 * y + ztone;
            ztone = b1 * y - X_TONE_A1_8 * o;

            b_b[i] = o;
        }
        s->spost = spost;
        s->ztone = ztone;
    }

    /* Step 4: Downsampling: 128 -> 64 -> 32 -> 16 */
    tsx_down3_blk(&s->s3, b_b, b_a, 64); /* 128 -> 64 in b_a */
    tsx_down3_blk(&s->s2, b_a, b_b, 32); /* 64 -> 32 in b_b */
    tsx_down6_blk(&s->s1, b_b, b_a, 16); /* 32 -> 16 in b_a */

    /* Step 5: Output DC block & Gain (16 samples) */
    {
        float sdc = s->sdc;
        float gain = k->gain;

#if defined(__TI_COMPILER_VERSION__)
#pragma MUST_ITERATE(16, 16, 16)
#endif
        for (i = 0; i < 16; ++i) {
            float x = b_a[i];
            float v = (x - sdc) * TS_G_DC;
            float lp = v + sdc;
            sdc = lp + v;
            out[i] = (x - lp) * gain;
        }
        s->sdc = sdc;
    }
}

TS_INLINE void tsx_block(TsxState *s, const TsxCoeffs *k, const float *in, float *out, int n)
{
    while (n >= 16) {
        tsx_block16(s, k, in, out);
        in += 16;
        out += 16;
        n -= 16;
    }
    while (n > 0) {
        *out++ = tsx_process(s, k, *in++);
        n--;
    }
}

#endif /* TS808_EXACT_H */


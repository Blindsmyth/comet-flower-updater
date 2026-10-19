/* ra200_g1.h - CF RA-200: Alembic F-2B preamp into a Yamaha RA-200 rotating-speaker cabinet pair, the
 * second half of Gilmour's 1979 rig (docs/RA200_F2B_DESIGN_2026-10-19.md). Mono in, stereo out (L/R = the
 * two miked cabinets). Written for the C6745 from the start (docs/C6745_DESIGN.md): stage-major passes over
 * the 16-frame block, state in scalar locals, no feedback in the rotary (writes first, then the reads).
 *
 * F-2B (R.G. Keen's schematic, geofex.com): V1b 12AX7 (68k stopper, 1M leak, 100k plate, 1.5k || 50u),
 * Fender AB763 stack (250p, 100k slope, 0.1u, 0.047u; Treble 250k, Bass 250k, Mid 10k), 1M Volume with a
 * 120p bright cap, V1a 12AX7 (100k, 1.5k || 50u), 0.1u into 1M. The triodes are CF Watt's 12AX7 stage
 * model (hw_tube_fast / hw_tube_adaa: tanh with bias and asymmetry, ADAA), at 1x; the networks are exact
 * linear circuits (mna_ss.h), the plate as mu * grid behind ra with the bypassed cathode folded in, as CF
 * Watt's V1 net. Stage clip point RA_H scaled to the 1.5k cathode bias.
 *
 * RA-200 (structure from the data sheet and listings; speeds, crossover and geometry unpublished, so the
 * values below are Leslie-like starting points): active crossover (LR4, RA_XO Hz), lows to four fixed 12"
 * (band-limited), highs to three speakers rotating together on one rotor. Per cabinet and speaker k the mic
 * hears the highs delayed by D0 + R (1 - cos a_k) samples (Doppler) and weighted (1 + beta cos a_k) / (1 +
 * beta) (the cone turning toward and away), a_k = rotor angle + 2 pi k / 3. Two cabinets, two rotors (motors
 * differ slightly), one mic each. Slow speed adjustable, fast fixed, inertia per direction.
 */
#ifndef RA200_G1_H
#define RA200_G1_H

#ifndef HW_OS
#define HW_OS 2                 /* only to configure hiwatt_amp.h; this effect runs at 1x */
#endif
#include "hiwatt_amp.h"         /* hw_tube_fast/adaa, hw_fast_ok, hw_atap, mna_ss, TS_INLINE, ts_rcp */

#define RA_FS      44100.0f
#define RA_NB      16
#define RA_H       1.6f         /* 12AX7 stage input clip point, Vpk (1.5k cathode: bias ~1.1 V) */
#define RA_PRE_OUT 0.05f        /* preamp output volts -> line level (host bench: ~unity at noon) */

/* rotary */
#define RA_XO      800.0f       /* crossover, Hz */
#define RA_R       19.29f       /* rotor radius 0.15 m in samples: 0.15 * 44100 / 343 */
#define RA_D0      2.0f         /* shortest delay (Lagrange needs one sample each side) */
#define RA_BETA    0.7f         /* directivity: cone toward / away from the mic */
#define RA_FAST    6.6f         /* fast rotor speed, Hz (fixed on the RA-200) */
#define RA_SLOW_LO 0.4f         /* slow speed knob range, Hz */
#define RA_SLOW_HI 3.0f
#define RA_SPREAD  1.035f       /* second cabinet's motor runs a little faster */
#define RA_TAU_UP  0.9f         /* spin-up / spin-down time constants, s */
#define RA_TAU_DN  1.6f
#define RA_LINE    128u         /* delay line (power of two); longest delay D0 + 2R + 2 < 42 */
#define RA_LMASK   (RA_LINE - 1u)

#define RA_N1_SZ   MNA_SS_SIZE(5, 1)    /* V1b + stack + volume + bright: 5 states */
#define RA_N2_SZ   MNA_SS_SIZE(2, 1)    /* V1a + output coupling: 2 states */

typedef struct {
    float n1[RA_N1_SZ], n2[RA_N2_SZ];
    float gx;                   /* rotation off (1) .. on (0): highs to the fixed speakers */
    float dphi[2];              /* rotor angle step per sample, per cabinet */
    float out;                  /* output gain */
} RaCoeffs;

typedef struct {
    float ax[2];                /* ADAA: previous input of V1b, V1a */
    float x1[5], u1;            /* network 1 states, previous input */
    float x2[2], u2;
    float xo[8];                /* crossover: 2 LR4 halves x 2 SVF states */
    float eq[6];                /* speaker EQ: fixed HP + LP, rotating LP (SVF states) */
    float rate[2], phi[2];      /* rotor speed (Hz) and angle (rad, -pi..pi) per cabinet */
    float line[RA_LINE];
    unsigned int wp;
} RaState;                      /* zero = silent start, rotors at rest */

/* ---- coefficients (per block; the networks only when the knobs moved) ---------------------------------- */

/* 12AX7 plate network: mu * grid behind ra, bypassed cathode folded, plate load (as hw_v1net) */
MNA_INLINE void ra_plate(MnaNet *m, int M, int P)
{
    mna_r(m, M, -1, HW_RA3);
    mna_b(m, M, 0, 1.0f / HW_RA3);
    mna_r(m, M, P, (HW_MU3 + 1.0f) * 1.5e3f);
    mna_c(m, M, P, 50e-6f / (HW_MU3 + 1.0f));
    mna_r(m, P, -1, 100e3f);
}

/* V1b + AB763 stack + Volume (+ Bright): knobs 0..1, pots audio taper (hw_atap), output the Volume wiper */
MNA_INLINE void ra_net1(MnaNet *m, float *w, float vol, float tre, float mid, float bas, int bright)
{
    enum { M = 0, P, A, W, B, X, MD, V };
    float t = hw_atap(tre), b = hw_atap(bas), md = hw_atap(mid), v = hw_atap(vol);
    int i;
    mna_init(m, 8, 1);
    ra_plate(m, M, P);
    mna_c(m, P, A, 250e-12f);                               /* treble cap */
    mna_r(m, A, W, hw_maxf((1.0f - t) * 250e3f, HW_RWIPR));  /* treble pot, wiper W */
    mna_r(m, W, B, hw_maxf(t * 250e3f, HW_RWIPR));
    mna_r(m, P, X, 100e3f);                                 /* slope resistor */
    mna_c(m, X, B, 0.1e-6f);                                /* bass cap */
    mna_c(m, X, MD, 0.047e-6f);                             /* mid cap */
    mna_r(m, B, MD, hw_maxf(b * 250e3f, HW_RWIPR));          /* bass (rheostat) */
    mna_r(m, MD, -1, hw_maxf(md * 10e3f, HW_RWIPR));          /* mid (rheostat) */
    mna_r(m, W, V, hw_maxf((1.0f - v) * 1e6f, HW_RWIPR));    /* volume 1M */
    mna_r(m, V, -1, hw_maxf(v * 1e6f, HW_RWIPR));
    if (bright)
        mna_c(m, W, V, 120e-12f);                           /* bright: the fifth state */
    for (i = 0; i < MNA_MAXN; ++i) w[i] = 0.0f;
    w[V] = 1.0f;
}

/* V1a + 0.1u into 1M */
MNA_INLINE void ra_net2(MnaNet *m, float *w)
{
    enum { M = 0, P, O };
    int i;
    mna_init(m, 3, 1);
    ra_plate(m, M, P);
    mna_c(m, P, O, 0.1e-6f);
    mna_r(m, O, -1, 1e6f);
    for (i = 0; i < MNA_MAXN; ++i) w[i] = 0.0f;
    w[O] = 1.0f;
}

/* the networks through one mna_derive site (code size: it is inlined, and the G1's code region is 30 KB):
 * which 1 = V1b + stack, padded to 5 states (bright off: 4 states, the fifth stays zero); which 2 = V1a */
MNA_INLINE void ra_derive(float *n1, float *n2, int which, float vol, float tre, float mid, float bas, int bright)
{
    MnaNet m;
    float w[MNA_MAXN], tmp[RA_N1_SZ];
    int k, i, j, pass;
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
    for (pass = 1; pass <= 2; ++pass) {
        if (!(which & pass))
            continue;
        if (pass == 1)
            ra_net1(&m, w, vol, tre, mid, bas, bright);
        else
            ra_net2(&m, w);
        k = m.k;
        mna_derive(&m, w, RA_FS, tmp);
        if (pass == 2) {
            for (i = 0; i < RA_N2_SZ; ++i) n2[i] = tmp[i];
            continue;
        }
        for (i = 0; i < RA_N1_SZ; ++i) n1[i] = 0.0f;
        for (i = 0; i < k; ++i) {
            for (j = 0; j < k; ++j) MNA_DA(n1, 5, 1, i, j) = MNA_DA(tmp, k, 1, i, j);
            MNA_DB(n1, 5, 1, i, 0) = MNA_DB(tmp, k, 1, i, 0);
            MNA_CY(n1, 5, 1, i) = MNA_CY(tmp, k, 1, i);
        }
        MNA_DY(n1, 5, 1, 0) = MNA_DY(tmp, k, 1, 0);
    }
}

/* per-block rotor and routing: rotor 0 off, 1 slow, 2 fast; speed 0..1 sets the slow speed */
TS_INLINE void ra_rotor_coeffs(RaCoeffs *k, RaState *s, float speed, int rotor)
{
    float slow = RA_SLOW_LO + (RA_SLOW_HI - RA_SLOW_LO) * ts_clamp(speed, 0.0f, 1.0f);
    float target = rotor >= 2 ? RA_FAST : slow;
    float up = 1.0f - sd_expf(-RA_NB / (RA_FS * RA_TAU_UP)), dn = 1.0f - sd_expf(-RA_NB / (RA_FS * RA_TAU_DN));
    int c;
    k->gx += 0.05f * ((rotor == 0 ? 1.0f : 0.0f) - k->gx);
    for (c = 0; c < 2; ++c) {
        float tg = target * (c ? RA_SPREAD : 1.0f), r = s->rate[c];
        r += (tg > r ? up : dn) * (tg - r);
        s->rate[c] = r;
        k->dphi[c] = r * (6.28318530717958647692f / RA_FS);
    }
}

/* ---- per-sample pieces ---------------------------------------------------------------------------------- */

/* fixed Butterworth biquads (RBJ, bilinear at 44.1 kHz, computed in double): b0 b1 b2 a1 a2. Transposed
 * direct form II: a ~12-cycle feedback chain (a TPT SVF's was 28) */
#define RA_XO_LP  3.002885980e-03f, 6.005771960e-03f, 3.002885980e-03f, -1.839116797e+00f, 8.511283412e-01f
#define RA_XO_HP  9.225612846e-01f, -1.845122569e+00f, 9.225612846e-01f, -1.839116797e+00f, 8.511283412e-01f
#define RA_FX_HP  9.929726129e-01f, -1.985945226e+00f, 9.929726129e-01f, -1.985895841e+00f, 9.859946106e-01f
#define RA_FX_LP  6.978089420e-02f, 1.395617884e-01f, 6.978089420e-02f, -1.126428906e+00f, 4.055524827e-01f
#define RA_RT_LP  1.434934669e-01f, 2.869869337e-01f, 1.434934669e-01f, -6.807407017e-01f, 2.547145691e-01f
TS_INLINE float ra_bq(float *s1, float *s2, float b0, float b1, float b2, float a1, float a2, float x)
{
    float y = b0 * x + *s1;
    *s1 = (b1 * x - a1 * y) + *s2;
    *s2 = b2 * x - a2 * y;
    return y;
}
#define RA_BQ(s1, s2, C, x) ra_bq(s1, s2, C, x)

/* cos and sin of a in [-pi, pi]: even/odd polynomials, |error| < 2e-6 (no table, no branch) */
TS_INLINE void ra_cossin(float a, float *c, float *s)
{
    float h = 0.5f * a, h2 = h * h;
    /* half angle: cos h, sin h on [-pi/2, pi/2], then double */
    float ch = 1.0f + h2 * (-0.5f + h2 * (1.0f / 24 + h2 * (-1.0f / 720 + h2 * (1.0f / 40320 - h2 * (1.0f / 3628800)))));
    float sh = h * (1.0f + h2 * (-1.0f / 6 + h2 * (1.0f / 120 + h2 * (-1.0f / 5040 + h2 * (1.0f / 362880)))));
    *c = ch * ch - sh * sh;
    *s = 2.0f * sh * ch;
}

/* Lagrange 3rd-order read d samples behind position wp (d >= 1) */
TS_INLINE float ra_read(const float *line, unsigned int wp, float d)
{
    int M = (int)d;
    float mu = d - (float)M;
    float m1 = mu - 1.0f, m2 = mu - 2.0f, p1 = mu + 1.0f;
    float Lm1 = -mu * m1 * m2 * (1.0f / 6.0f), L0 = p1 * m1 * m2 * 0.5f;
    float L1 = -p1 * mu * m2 * 0.5f, L2 = p1 * mu * m1 * (1.0f / 6.0f);
    unsigned int i0 = wp - (unsigned int)M;
    return Lm1 * line[(i0 + 1u) & RA_LMASK] + L0 * line[i0 & RA_LMASK]
         + L1 * line[(i0 - 1u) & RA_LMASK] + L2 * line[(i0 - 2u) & RA_LMASK];
}

/* the mic of one cabinet: three speakers at 120 degrees, rotor angle (c, s) */
#define RA_C120 (-0.5f)
#define RA_S120 0.86602540f
TS_INLINE float ra_mic(const float *line, unsigned int wp, float c, float s)
{
    float c1 = c * RA_C120 - s * RA_S120, c2 = c * RA_C120 + s * RA_S120;
    float g = 1.0f / (3.0f * (1.0f + RA_BETA));
    float y0 = ra_read(line, wp, RA_D0 + RA_R * (1.0f - c)) * (1.0f + RA_BETA * c);
    float y1 = ra_read(line, wp, RA_D0 + RA_R * (1.0f - c1)) * (1.0f + RA_BETA * c1);
    float y2 = ra_read(line, wp, RA_D0 + RA_R * (1.0f - c2)) * (1.0f + RA_BETA * c2);
    return (y0 + y1 + y2) * g;
}

/* ---- the block ------------------------------------------------------------------------------------------ */

/* one 12AX7 stage over the block (x in clip units) -> y, as hw_tube_block at 1x: a pipelined fast pass, then
 * the rare exact ADAA fix-ups listed by a cheap test pass */
TS_INLINE void ra_tube_block(const float *HW_RESTRICT x, float *HW_RESTRICT y, float *x1)
{
    float prev = *x1;
    unsigned char idx[RA_NB];
    int n, ok, cnt = 0, i;
    for (n = 0; n < RA_NB; ++n) {
        float xp = n == 0 ? prev : x[n - 1];
        y[n] = hw_tube_fast(x[n], xp, HW_B1, HW_K1, 1.0f, HW_I1, &ok);
    }
    for (n = 0; n < RA_NB; ++n) {
        float xp = n == 0 ? prev : x[n - 1];
        idx[cnt] = (unsigned char)n;
        cnt += !hw_fast_ok(x[n], xp, HW_B1, 1.0f);
    }
    for (i = 0; i < cnt; ++i) {
        float t;
        n = idx[i];
        t = n == 0 ? prev : x[n - 1];
        y[n] = hw_tube_adaa(x[n], &t, HW_B1, HW_K1, 1.0f, HW_I1);
    }
    *x1 = x[RA_NB - 1];
}

/* the 5-state network over the block, delta form (as hw_net5_block, one input) */
TS_INLINE void ra_net5_block(const float *HW_RESTRICT m, float *HW_RESTRICT xs, float *HW_RESTRICT up,
                             const float *HW_RESTRICT v, float g, float *HW_RESTRICT y)
{
#define A(i, j) MNA_DA(m, 5, 1, i, j)
#define ROW(i) ((MNA_DB(m, 5, 1, i, 0) * su + A(i, 0) * x0) \
                + ((A(i, 1) * x1 + A(i, 2) * x2) + (A(i, 3) * x3 + A(i, 4) * x4)))
    float x0 = xs[0], x1 = xs[1], x2 = xs[2], x3 = xs[3], x4 = xs[4], ul = *up;
    int n;
    for (n = 0; n < RA_NB; ++n) {
        float u = g * v[n], su = u + ul;
        float d0 = ROW(0), d1 = ROW(1), d2 = ROW(2), d3 = ROW(3), d4 = ROW(4);
        x0 += d0; x1 += d1; x2 += d2; x3 += d3; x4 += d4;
        ul = u;
        y[n] = MNA_DY(m, 5, 1, 0) * u + ((MNA_CY(m, 5, 1, 0) * x0 + MNA_CY(m, 5, 1, 1) * x1)
               + (MNA_CY(m, 5, 1, 2) * x2 + (MNA_CY(m, 5, 1, 3) * x3 + MNA_CY(m, 5, 1, 4) * x4)));
    }
    xs[0] = x0; xs[1] = x1; xs[2] = x2; xs[3] = x3; xs[4] = x4; *up = ul;
#undef ROW
#undef A
}

/* the 2-state network over the block (as hw_net2_block, which runs HW_NB = 16 * HW_OS samples) */
TS_INLINE void ra_net2_block(const float *HW_RESTRICT m, float *HW_RESTRICT xs, float *HW_RESTRICT up,
                             const float *HW_RESTRICT v, float g, float *HW_RESTRICT y)
{
    float x0 = xs[0], x1 = xs[1], ul = *up;
    const float a00 = MNA_DA(m, 2, 1, 0, 0), a01 = MNA_DA(m, 2, 1, 0, 1);
    const float a10 = MNA_DA(m, 2, 1, 1, 0), a11 = MNA_DA(m, 2, 1, 1, 1);
    const float b0 = MNA_DB(m, 2, 1, 0, 0), b1 = MNA_DB(m, 2, 1, 1, 0);
    const float c0 = MNA_CY(m, 2, 1, 0), c1 = MNA_CY(m, 2, 1, 1), e = MNA_DY(m, 2, 1, 0);
    int n;
    for (n = 0; n < RA_NB; ++n) {
        float u = g * v[n], su = u + ul;
        float d0 = (b0 * su + a00 * x0) + a01 * x1;
        float d1 = (b1 * su + a11 * x1) + a10 * x0;
        x0 += d0;
        x1 += d1;
        ul = u;
        y[n] = e * u + (c0 * x0 + c1 * x1);
    }
    xs[0] = x0; xs[1] = x1; *up = ul;
}

/* in: 16 jack-volt samples; outL/outR: the two cabinets */
TS_INLINE void ra_block(RaState *HW_RESTRICT s, const RaCoeffs *HW_RESTRICT k, const float *HW_RESTRICT in,
                        float *HW_RESTRICT outL, float *HW_RESTRICT outR)
{
    float a[RA_NB], b[RA_NB], lo[RA_NB], cs[2][2][RA_NB];
    const float gxo = 0.05978856f;      /* tan(pi 800 / 44100) */
    const float gfh = 0.00498622f;      /* fixed speakers: 70 Hz high-pass, 4.5 kHz low-pass */
    const float gfl = 0.33276213f;
    const float grl = 0.53452248f;      /* rotating speakers: 7 kHz low-pass */
    unsigned int wp0 = s->wp;
    int n, c;

    {   /* F-2B: V1b -> stack + volume -> V1a -> output coupling; one inlined copy of the tube code */
        int st;
        for (n = 0; n < RA_NB; ++n) a[n] = in[n] * (HW_IN_SCALE / RA_H);
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
        for (st = 0; st < 2; ++st) {
            ra_tube_block(a, b, &s->ax[st]);
            if (st == 0) {
                ra_net5_block(k->n1, s->x1, &s->u1, b, HW_MU3 * RA_H, a);
                for (n = 0; n < RA_NB; ++n) a[n] *= 1.0f / RA_H;
            } else {
                ra_net2_block(k->n2, s->x2, &s->u2, b, HW_MU3 * RA_H, a);
            }
        }
    }

    {   /* crossover (LR4 = two Butterworth biquads per side), the rotating speakers' low-pass, the writes of
         * their feed: five independent short recurrences in one loop */
        float x0 = s->xo[0], x1 = s->xo[1], x2 = s->xo[2], x3 = s->xo[3];
        float x4 = s->xo[4], x5 = s->xo[5], x6 = s->xo[6], x7 = s->xo[7];
        float e0 = s->eq[4], e1 = s->eq[5], gx = k->gx;
        for (n = 0; n < RA_NB; ++n) {
            float v = a[n] * RA_PRE_OUT;
            float l2 = RA_BQ(&x2, &x3, RA_XO_LP, RA_BQ(&x0, &x1, RA_XO_LP, v));
            float hi = RA_BQ(&x6, &x7, RA_XO_HP, RA_BQ(&x4, &x5, RA_XO_HP, v));
            lo[n] = l2 + gx * hi;                   /* rotation off: the highs to the fixed speakers */
            s->line[(wp0 + (unsigned int)n) & RA_LMASK] = RA_BQ(&e0, &e1, RA_RT_LP, (1.0f - gx) * hi);
        }
        s->xo[0] = x0; s->xo[1] = x1; s->xo[2] = x2; s->xo[3] = x3;
        s->xo[4] = x4; s->xo[5] = x5; s->xo[6] = x6; s->xo[7] = x7;
        s->eq[4] = e0; s->eq[5] = e1;
        s->wp = (wp0 + RA_NB) & RA_LMASK;
    }
    {   /* fixed speakers: 70 Hz high-pass, 4.5 kHz low-pass */
        float f0 = s->eq[0], f1 = s->eq[1], f2 = s->eq[2], f3 = s->eq[3];
        for (n = 0; n < RA_NB; ++n)
            lo[n] = RA_BQ(&f2, &f3, RA_FX_LP, RA_BQ(&f0, &f1, RA_FX_HP, lo[n]));
        s->eq[0] = f0; s->eq[1] = f1; s->eq[2] = f2; s->eq[3] = f3;
    }
    for (c = 0; c < 2; ++c) {           /* rotor angles: pure per sample from the block's start angle */
        float p0 = s->phi[c], dp = k->dphi[c];
        for (n = 0; n < RA_NB; ++n) {
            float p = p0 + dp * (float)(n + 1);
            p -= p > 3.14159265f ? 6.28318531f : 0.0f;
            ra_cossin(p, &cs[c][0][n], &cs[c][1][n]);
        }
        p0 += dp * (float)RA_NB;
        p0 -= p0 > 3.14159265f ? 6.28318531f : 0.0f;
        s->phi[c] = p0;
    }
#if defined(__TI_COMPILER_VERSION__)
#pragma UNROLL(1)
#endif
    for (c = 0; c < 2; ++c) {           /* the mics, one cabinet per pass: reads of the line, written already */
        const float *HW_RESTRICT line = s->line;
        float *HW_RESTRICT o = c ? outR : outL;
        float g = k->out;
        for (n = 0; n < RA_NB; ++n) {
            unsigned int wp = (wp0 + (unsigned int)n) & RA_LMASK;
            o[n] = g * (lo[n] + ra_mic(line, wp, cs[c][0][n], cs[c][1][n]));
        }
    }
}

#endif /* RA200_G1_H */

/* os_hbiir.h - polyphase IIR half-band 2x stages (two allpass paths), for
 * amp models: far better image/alias rejection per state float than the FIR
 * half-bands in os_halfband.h, at the price of a non-linear phase (inaudible
 * for an amp; Comet Flower's desktop amps use JUCE's polyphase-IIR
 * oversampler for the same reason).
 *
 * Coefficients: tools/gen_halfband_iir.py (elliptic design, passband 20 kHz).
 *   stage 1 (44.1 <-> 88.2 kHz):  10 coefficients, >= 24.1 kHz down 106 dB
 *   stage 2 (88.2 <-> 176.4 kHz):  5 coefficients, >= 68.2 kHz down ~100 dB
 * Each first-order allpass section (c + z^-1)/(1 + c z^-1) runs at the low
 * rate in direct form II, one state float: w = x - c s, y = c w + s, s = w.
 * Path 0 takes coefficients 0, 2, 4..; path 1 takes 1, 3, 5...
 *   up:   x -> (path0(x), path1(x))
 *   down: (a, b) -> (path0(b) + path1(a)) / 2
 */
#ifndef OS_HBIIR_H
#define OS_HBIIR_H

#include "ts808_core.h"         /* TS_INLINE */

#define HBI1_N 10
#define HBI2_N 5
static const float hbi1_c[HBI1_N] = { 0.0355729863f, 0.132792136f, 0.268223042f, 0.415490783f, 0.554392021f, 0.674172988f, 0.772192382f, 0.850958174f, 0.915586681f, 0.972370293f };
static const float hbi2_c[HBI2_N] = { 0.0437516289f, 0.165966744f, 0.346406253f, 0.569034401f, 0.837719989f };

typedef struct { float s[HBI1_N]; } HbiState1;   /* one direction of stage 1 */
typedef struct { float s[HBI2_N]; } HbiState2;   /* one direction of stage 2 */

/* run path p (0 or 1) of an n-coefficient filter over x */
TS_INLINE float hbi_path(const float *c, float *s, int n, int p, float x)
{
    int i;
    for (i = p; i < n; i += 2) {
        float w = x - c[i] * s[i];
        x = c[i] * w + s[i];
        s[i] = w;
    }
    return x;
}

TS_INLINE void hbi_up1(HbiState1 *h, float x, float *a, float *b)
{
    *a = hbi_path(hbi1_c, h->s, HBI1_N, 0, x);
    *b = hbi_path(hbi1_c, h->s, HBI1_N, 1, x);
}

TS_INLINE float hbi_down1(HbiState1 *h, float a, float b)
{
    return 0.5f * (hbi_path(hbi1_c, h->s, HBI1_N, 0, b) + hbi_path(hbi1_c, h->s, HBI1_N, 1, a));
}

TS_INLINE void hbi_up2(HbiState2 *h, float x, float *a, float *b)
{
    *a = hbi_path(hbi2_c, h->s, HBI2_N, 0, x);
    *b = hbi_path(hbi2_c, h->s, HBI2_N, 1, x);
}

TS_INLINE float hbi_down2(HbiState2 *h, float a, float b)
{
    return 0.5f * (hbi_path(hbi2_c, h->s, HBI2_N, 0, b) + hbi_path(hbi2_c, h->s, HBI2_N, 1, a));
}

/* Block forms, stage-major: one stage over a whole buffer, the state held in
 * locals so the C6x compiler can software-pipeline across samples (each
 * section only depends on its own state: ~8-cycle recurrence). Sample-major
 * calls of the single-sample forms serialise every section of both stages
 * (DR103: ~220 cycles per input sample for up1 + 2 x up2). Same arithmetic,
 * same order per section, so the output is bit-identical.
 *   up:   y[2i], y[2i+1] = paths of x[i], i < n
 *   down: y[i] = (path0(x[2i+1]) + path1(x[2i])) / 2, i < n */
#define HBI_BLOCK_FN(name, N, C, HT)                                          \
TS_INLINE void name##_up_blk(HT *h, const float *x, float *y, int n)         \
{                                                                             \
    float st[N];                                                              \
    int i, k;                                                                 \
    for (k = 0; k < N; ++k) st[k] = h->s[k];                                  \
    for (i = 0; i < n; ++i) {                                                 \
        float a = x[i], b = x[i];                                             \
        for (k = 0; k < N; k += 2) {                                          \
            float w = a - C[k] * st[k];                                       \
            a = C[k] * w + st[k];                                             \
            st[k] = w;                                                        \
        }                                                                     \
        for (k = 1; k < N; k += 2) {                                          \
            float w = b - C[k] * st[k];                                       \
            b = C[k] * w + st[k];                                             \
            st[k] = w;                                                        \
        }                                                                     \
        y[2 * i] = a;                                                         \
        y[2 * i + 1] = b;                                                     \
    }                                                                         \
    for (k = 0; k < N; ++k) h->s[k] = st[k];                                  \
}                                                                             \
TS_INLINE void name##_down_blk(HT *h, const float *x, float *y, int n)       \
{                                                                             \
    float st[N];                                                              \
    int i, k;                                                                 \
    for (k = 0; k < N; ++k) st[k] = h->s[k];                                  \
    for (i = 0; i < n; ++i) {                                                 \
        float a = x[2 * i + 1], b = x[2 * i];                                 \
        for (k = 0; k < N; k += 2) {                                          \
            float w = a - C[k] * st[k];                                       \
            a = C[k] * w + st[k];                                             \
            st[k] = w;                                                        \
        }                                                                     \
        for (k = 1; k < N; k += 2) {                                          \
            float w = b - C[k] * st[k];                                       \
            b = C[k] * w + st[k];                                             \
            st[k] = w;                                                        \
        }                                                                     \
        y[i] = 0.5f * (a + b);                                                \
    }                                                                         \
    for (k = 0; k < N; ++k) h->s[k] = st[k];                                  \
}
HBI_BLOCK_FN(hbi1, HBI1_N, hbi1_c, HbiState1)
HBI_BLOCK_FN(hbi2, HBI2_N, hbi2_c, HbiState2)

#endif /* OS_HBIIR_H */

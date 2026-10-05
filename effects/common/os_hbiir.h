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

#endif /* OS_HBIIR_H */

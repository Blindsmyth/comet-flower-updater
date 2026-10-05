/* os_halfband.h - polyphase half-band FIR 2x up/down stages (moved out of
 * ts808_exact.h unchanged; shared by Green 808X and the Hiwatt).
 *   TsxHB6: 6 tap pairs (OS_C0..5 from ts808_core.h, as Comet Flower's
 *           Oversampler2x), for the 1x <-> 2x stage
 *   TsxHB3: 3 tap pairs, for the 2x <-> 4x and 4x <-> 8x stages, where the
 *           transition band is wide
 * up: one input sample -> two output samples (a then b); down: two -> one.
 */
#ifndef OS_HALFBAND_H
#define OS_HALFBAND_H

#include "ts808_core.h"

#define OS3_C0  0.28437113761901855f
#define OS3_C1 -0.03608988597989082f
#define OS3_C2  0.0017187680350616574f

typedef struct { float xh[12], eh[7], oh[13]; } TsxHB6;   /* 32 floats */
typedef struct { float xh[6], eh[4], oh[7]; } TsxHB3;     /* 17 floats */

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

#endif /* OS_HALFBAND_H */

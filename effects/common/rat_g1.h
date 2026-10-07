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
 *
 * PLACEHOLDER: this version passes the input through, so the kit builds and
 * the bench reports FAIL. The real model replaces the bodies below.
 */
#ifndef RAT_G1_H
#define RAT_G1_H

#include "ts808_core.h"         /* TS_INLINE */

typedef struct { float dummy; } RatState;
typedef struct { float vol; } RatCoeffs;

TS_INLINE void rat_coeffs(RatCoeffs *k, float dist, float filter, float vol)
{
    (void)dist; (void)filter;
    k->vol = vol;
}

TS_INLINE float rat_process(RatState *s, const RatCoeffs *k, float x)
{
    (void)s;
    return x * k->vol;
}

#endif

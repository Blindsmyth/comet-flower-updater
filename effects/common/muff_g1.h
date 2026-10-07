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
 *
 * PLACEHOLDER: passes the input through, so the kit builds and the bench
 * reports FAIL. The real model replaces the bodies below.
 */
#ifndef MUFF_G1_H
#define MUFF_G1_H

#include "ts808_core.h"         /* TS_INLINE */

typedef struct { float dummy; } MuffState;
typedef struct { float vol; } MuffCoeffs;

TS_INLINE void muff_coeffs(MuffCoeffs *k, float sustain, float tone, float volume)
{
    (void)sustain; (void)tone;
    k->vol = volume;
}

TS_INLINE float muff_process(MuffState *s, const MuffCoeffs *k, float x)
{
    (void)s;
    return x * k->vol;
}

#endif
